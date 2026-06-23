# Manual Bulk GRN Creation + Review Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace PR #18's auto-on-submit background GRN job with a synchronous, all-or-nothing, permission-checked "Create Purchase Receipt" button (clicked by a stores user), and fold in the code-review fixes.

**Architecture:** A whitelisted `create_purchase_receipts(gate_pass_name)` builds one draft PR per pending invoice inside a DB savepoint — committing all or rolling the batch back on any failure. The `on_submit` enqueue, `generate_purchase_receipts` job, and realtime notification are removed. The migration patch is fixed to update submitted legacy docs. Everything else from PR #18 (invoice-grouped UI, `grn_status` lifecycle, cancel/amend, report/link fixes) is unchanged.

**Tech Stack:** Frappe/ERPNext v15 + v16, Python, Frappe DocType JSON, vanilla JS, `FrappeTestCase`.

Spec: [`docs/superpowers/specs/2026-06-23-manual-bulk-grn-and-review-fixes-design.md`](../specs/2026-06-23-manual-bulk-grn-and-review-fixes-design.md). Builds on PR #18 (branch `issue-17-multi-invoice-grn`).

## Global Constraints

- **Dual-version (HARD):** must work on Frappe/ERPNext **v15 (15.102.1)** and **v16 (16.13.0)**. Every test runs on BOTH benches.
- **Verification environments** — `bench --site gate.localhost <cmd>` below is shorthand for running on BOTH (the checkout is symlinked into both benches on branch `issue-17-multi-invoice-grn`):
  - v15: `cd /Users/gurudattkulkarni/Workspace/bench15 && bench --site development.localhost <cmd>`
  - v16: `cd /Users/gurudattkulkarni/Workspace/bench16 && bench --site frappe16.localhost <cmd>`
  - **NOTE:** bench16's web server 404s (dead `default_site`) and `bench serve` must be restarted after symlink changes — these only affect *browser* use; CLI `run-tests` works on both.
- **Module path:** `gate_entry.gate_entry.doctype.gate_pass.test_gate_pass`.
- **All-or-nothing** PR creation uses a **DB savepoint** (`frappe.db.savepoint` / `frappe.db.rollback(save_point=...)`), NOT a bare `frappe.db.rollback()` — a bare rollback would nuke the caller's/test's whole transaction.
- PRs are created as **drafts** (`pr.insert()`, never submit).
- Match existing code style (tabs in Python).

---

## File structure

| File | Change |
|---|---|
| `gate_entry/gate_entry/doctype/gate_pass/gate_pass.py` | Remove `on_submit` enqueue, `generate_purchase_receipts`, `_notify_grn_generation`; add whitelisted `create_purchase_receipts`; reword one validation message. Keep `_build_purchase_receipt`, `on_purchase_receipt_submit`, `_clear_invoice_row_for_pr`, validation, cancel/amend. |
| `gate_entry/gate_entry/doctype/gate_pass/gate_pass.js` | Re-add a PO-flow bulk "Create Purchase Receipt" button + per-invoice View links in `setup_receipt_buttons`; add `create_purchase_receipts` JS; remove the now-dead realtime listener in `onload`. |
| `gate_entry/gate_entry/doctype/gate_pass/test_gate_pass.py` | Replace the auto-GRN test with `create_purchase_receipts` tests; update the `_submitted_po_gate_pass` helper; add the migration-mechanism test. |
| `gate_entry/patches/v1_1/migrate_single_pr_to_invoices.py` | Add `flags.ignore_validate_update_after_submit = True` before `save()`. |
| `README.md`, `USER_GUIDE.md`, `CHANGELOG.md` | Update the flow: stores user clicks Create Purchase Receipt (not auto-on-submit). |

---

## Task 1: Backend — synchronous bulk `create_purchase_receipts` (TDD)

**Files:**
- Modify: `gate_entry/gate_entry/doctype/gate_pass/gate_pass.py`
- Test: `gate_entry/gate_entry/doctype/gate_pass/test_gate_pass.py`

**Interfaces:**
- Consumes: `_build_purchase_receipt(gate_pass, invoice_no, item_rows)` (existing — returns an inserted draft PR doc).
- Produces: whitelisted `create_purchase_receipts(gate_pass_name) -> {"created": [str], "skipped": [str], "message"?: str}`. Throws `frappe.PermissionError` without PR-create permission; throws `frappe.ValidationError` (all rolled back) if any invoice fails. Test helper `_build_submitted_gate_pass(po, invoices)` (builds + submits a PO gate pass, NO PRs).

- [ ] **Step 1: Remove the obsolete background-job code**

In `gate_pass.py`:
1. In `on_submit`, delete the block added by PR #18 (right after `self.update_stock_entry_reference()`):
```python
		if self.document_reference == "Purchase Order":
			frappe.enqueue(
				generate_purchase_receipts,
				gate_pass_name=self.name,
				enqueued_by=frappe.session.user,
				queue="long",
				now=frappe.flags.in_test,
			)
```
2. Delete the entire `def generate_purchase_receipts(gate_pass_name, enqueued_by=None):` function and the entire `def _notify_grn_generation(gate_pass, enqueued_by, created, failed):` function. Leave `_build_purchase_receipt` intact.

- [ ] **Step 2: Reword the validation message**

In `validate_purchase_invoices`, change:
```python
		frappe.throw(_("Add at least one supplier invoice before submitting."))
```
to:
```python
		frappe.throw(_("Add at least one supplier invoice before saving."))
```

- [ ] **Step 3: Write the failing tests**

In `test_gate_pass.py`, add the helper (next to the existing `_make_test_purchase_order`) and the test class. `_build_submitted_gate_pass` builds + submits a PO gate pass WITHOUT creating PRs (submit no longer auto-creates):

```python
def _build_submitted_gate_pass(po, invoices):
	import frappe

	gp = frappe.new_doc("Gate Pass")
	gp.document_reference = "Purchase Order"
	gp.reference_number = po.name
	gp.company = po.company
	gp.supplier = po.supplier
	gp.vehicle_number = "KA01AB1234"
	gp.driver_name = "Test Driver"
	for inv, qty in invoices:
		gp.append("gate_pass_invoices", {"supplier_delivery_note": inv})
		gp.append("gate_pass_table", {
			"item_code": po.items[0].item_code,
			"received_qty": qty,
			"order_item_name": po.items[0].name,
			"warehouse": po.items[0].warehouse,
			"supplier_delivery_note": inv,
		})
	gp.submit()
	return gp


class TestCreatePurchaseReceipts(FrappeTestCase):
	def test_creates_one_draft_pr_per_invoice(self):
		from gate_entry.gate_entry.doctype.gate_pass.gate_pass import create_purchase_receipts

		po = _make_test_purchase_order(qty=10)
		gp = _build_submitted_gate_pass(po, [("INV-A", 3), ("INV-B", 4)])

		result = create_purchase_receipts(gp.name)
		self.assertEqual(len(result["created"]), 2)

		gp.reload()
		prs = [r.purchase_receipt for r in gp.gate_pass_invoices]
		self.assertEqual(len([p for p in prs if p]), 2)
		self.assertTrue(all(r.grn_status == "Draft" for r in gp.gate_pass_invoices))
		for p in prs:
			self.assertEqual(frappe.db.get_value("Purchase Receipt", p, "docstatus"), 0)

	def test_all_or_nothing_rolls_back_on_failure(self):
		from gate_entry.gate_entry.doctype.gate_pass.gate_pass import create_purchase_receipts

		po = _make_test_purchase_order(qty=10)
		gp = _build_submitted_gate_pass(po, [("INV-A", 3), ("INV-B", 4)])
		# Make INV-B fail: point its item at a non-existent PO Item so _build_purchase_receipt raises
		for row in gp.gate_pass_table:
			if row.supplier_delivery_note == "INV-B":
				frappe.db.set_value("Gate Pass Table", row.name, "order_item_name", "NONEXISTENT", update_modified=False)

		with self.assertRaises(Exception):
			create_purchase_receipts(gp.name)

		gp.reload()
		self.assertTrue(all(not r.purchase_receipt for r in gp.gate_pass_invoices))
		self.assertEqual(frappe.db.count("Purchase Receipt", {"gate_pass": gp.name}), 0)

	def test_idempotent_recall_creates_nothing_new(self):
		from gate_entry.gate_entry.doctype.gate_pass.gate_pass import create_purchase_receipts

		po = _make_test_purchase_order(qty=10)
		gp = _build_submitted_gate_pass(po, [("INV-A", 3)])
		self.assertEqual(len(create_purchase_receipts(gp.name)["created"]), 1)
		self.assertEqual(len(create_purchase_receipts(gp.name)["created"]), 0)
		self.assertEqual(frappe.db.count("Purchase Receipt", {"gate_pass": gp.name}), 1)

	def test_requires_purchase_receipt_create_permission(self):
		from gate_entry.gate_entry.doctype.gate_pass.gate_pass import create_purchase_receipts

		po = _make_test_purchase_order(qty=10)
		gp = _build_submitted_gate_pass(po, [("INV-A", 3)])

		# A role-less user has no Purchase Receipt create permission. The endpoint's
		# permission check is its first line (before any get_doc), so this is enough.
		email = "grn_perm_test@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "NoPerm",
				"send_welcome_email": 0, "roles": [],
			}).insert(ignore_permissions=True)

		frappe.set_user(email)
		try:
			self.assertFalse(frappe.has_permission("Purchase Receipt", "create"))
			with self.assertRaises(frappe.PermissionError):
				create_purchase_receipts(gp.name)
		finally:
			frappe.set_user("Administrator")
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `bench --site gate.localhost run-tests --module gate_entry.gate_entry.doctype.gate_pass.test_gate_pass --test test_creates_one_draft_pr_per_invoice`
Expected: FAIL — `ImportError`/`AttributeError`: `create_purchase_receipts` not defined (and `_build_submitted_gate_pass` referencing the removed auto-create is fine since submit no longer creates PRs).

- [ ] **Step 5: Implement `create_purchase_receipts`**

Add to `gate_pass.py` (module level, where `generate_purchase_receipts` used to be):

```python
@frappe.whitelist()
def create_purchase_receipts(gate_pass_name):
	"""Create one draft Purchase Receipt per invoice row that has none yet.

	All-or-nothing: builds inside a DB savepoint and rolls the whole batch
	back if any invoice fails, so no partial set of receipts is left behind.
	Runs synchronously as the calling (stores) user, respecting permissions.
	"""
	if not frappe.has_permission("Purchase Receipt", "create"):
		frappe.throw(
			_("You don't have permission to create Purchase Receipt"), frappe.PermissionError
		)

	gate_pass = frappe.get_doc("Gate Pass", gate_pass_name)
	if gate_pass.docstatus != 1:
		frappe.throw(_("Gate Pass must be submitted before creating Purchase Receipts"))
	if gate_pass.document_reference != "Purchase Order":
		frappe.throw(_("This Gate Pass is not for a Purchase Order"))

	items_by_invoice = {}
	for item in gate_pass.get("gate_pass_table") or []:
		tag = (item.supplier_delivery_note or "").strip()
		if tag:
			items_by_invoice.setdefault(tag, []).append(item)

	invoice_rows = gate_pass.get("gate_pass_invoices") or []
	pending = [inv for inv in invoice_rows if not inv.purchase_receipt]
	skipped = [inv.supplier_delivery_note for inv in invoice_rows if inv.purchase_receipt]

	if not pending:
		return {"created": [], "skipped": skipped, "message": _("All GRNs have already been created.")}

	created = []
	current_invoice = None
	frappe.db.savepoint("create_grns")
	try:
		for inv in pending:
			current_invoice = (inv.supplier_delivery_note or "").strip()
			item_rows = items_by_invoice.get(current_invoice, [])
			if not item_rows:
				frappe.throw(_("Invoice {0} has no items.").format(current_invoice))
			pr = _build_purchase_receipt(gate_pass, current_invoice, item_rows)
			inv.db_set("purchase_receipt", pr.name, update_modified=False)
			inv.db_set("grn_status", "Draft", update_modified=False)
			created.append(pr.name)
	except Exception:
		frappe.db.rollback(save_point="create_grns")
		frappe.log_error(
			message=frappe.get_traceback(),
			title=_("Bulk GRN creation failed for Gate Pass {0}").format(gate_pass_name),
		)
		frappe.throw(
			_("Could not create Purchase Receipt for invoice {0} — no receipts were created. See Error Log.").format(
				current_invoice
			)
		)

	gate_pass.add_comment(
		"Comment",
		_("Created Purchase Receipts: {0} (by {1}).").format(", ".join(created), frappe.session.user),
	)
	return {"created": created, "skipped": skipped}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `bench --site gate.localhost run-tests --module gate_entry.gate_entry.doctype.gate_pass.test_gate_pass`
Expected: the new `TestCreatePurchaseReceipts` tests PASS; existing tests still pass (the next step fixes the one helper they depend on).

- [ ] **Step 7: Update the `_submitted_po_gate_pass` helper used by the cancel/grn-status tests**

PR #18's `_submitted_po_gate_pass` called the removed `generate_purchase_receipts`. Repoint it to the new endpoint so the cancel/`grn_status` tests still get PRs created. Replace its body's PR-creation call:

```python
def _submitted_po_gate_pass(po, invoices):
	from gate_entry.gate_entry.doctype.gate_pass.gate_pass import create_purchase_receipts

	gp = _build_submitted_gate_pass(po, invoices)
	create_purchase_receipts(gp.name)
	gp.reload()
	return gp
```

(Delete the old `_submitted_po_gate_pass` definition that built the gate pass inline + called `generate_purchase_receipts`; it now delegates to `_build_submitted_gate_pass`.)

- [ ] **Step 8: Run the full module to confirm no regressions**

Run: `bench --site gate.localhost run-tests --module gate_entry.gate_entry.doctype.gate_pass.test_gate_pass`
Expected: all tests PASS on BOTH benches (the old `test_generate_purchase_receipts_*` test is replaced; cancel/grn-status tests pass via the updated helper).

- [ ] **Step 9: Commit**

```bash
git add gate_entry/gate_entry/doctype/gate_pass/gate_pass.py gate_entry/gate_entry/doctype/gate_pass/test_gate_pass.py
git commit -m "feat: synchronous all-or-nothing create_purchase_receipts; drop background GRN job (#17)"
```

---

## Task 2: Frontend — bulk "Create Purchase Receipt" button; remove dead realtime listener

**Files:**
- Modify: `gate_entry/gate_entry/doctype/gate_pass/gate_pass.js`

**Interfaces:**
- Consumes: `create_purchase_receipts` (Task 1).

- [ ] **Step 1: Remove the dead realtime listener**

In `gate_pass.js` `onload` ([lines 27-37](../../../gate_entry/gate_entry/doctype/gate_pass/gate_pass.js)), delete the entire `if (!frm._grn_listener_registered) { ... frappe.realtime.on("gate_pass_grn_generated", ...) ... }` block (there is no realtime event anymore).

- [ ] **Step 2: Add the PO branch to `setup_receipt_buttons`**

In `setup_receipt_buttons` (currently only handles Subcontracting Order), add a Purchase Order branch BEFORE the `if (frm.doc.document_reference === "Subcontracting Order")`:

```javascript
	if (frm.doc.document_reference === "Purchase Order") {
		if (frm.doc.docstatus !== 1) {
			return;
		}
		const invoices = frm.doc.gate_pass_invoices || [];
		const all_created = invoices.length > 0 && invoices.every((inv) => inv.purchase_receipt);
		if (!all_created) {
			frm.add_custom_button(__("Create Purchase Receipt"), function () {
				create_purchase_receipts(frm);
			}).addClass("btn-primary");
		}
		invoices
			.filter((inv) => inv.purchase_receipt)
			.forEach((inv) => {
				frm.add_custom_button(
					inv.purchase_receipt,
					function () {
						frappe.set_route("Form", "Purchase Receipt", inv.purchase_receipt);
					},
					__("View Purchase Receipts")
				);
			});
		return;
	}
```

- [ ] **Step 3: Add the `create_purchase_receipts` JS function**

Add near `create_subcontracting_receipt`:

```javascript
/**
 * Create all per-invoice draft Purchase Receipts for this Gate Pass (bulk, all-or-nothing).
 */
function create_purchase_receipts(frm) {
	frappe.confirm(
		__("Create draft Purchase Receipts for all invoices on this Gate Pass?"),
		function () {
			frappe.call({
				method: "gate_entry.gate_entry.doctype.gate_pass.gate_pass.create_purchase_receipts",
				args: { gate_pass_name: frm.doc.name },
				freeze: true,
				freeze_message: __("Creating Purchase Receipts..."),
				callback: function (r) {
					if (!r.message) {
						return;
					}
					if (r.message.created && r.message.created.length) {
						const links = r.message.created
							.map(
								(n) =>
									`<a href="/app/purchase-receipt/${encodeURIComponent(n)}">${frappe.utils.escape_html(n)}</a>`
							)
							.join(", ");
						frappe.msgprint({
							title: __("Purchase Receipts Created"),
							message: __("Created: {0}", [links]),
							indicator: "green",
						});
						frm.reload_doc();
					} else if (r.message.message) {
						frappe.msgprint(r.message.message);
					}
				},
			});
		}
	);
}
```

- [ ] **Step 4: Verify syntax + manual check**

Run: `node --check gate_entry/gate_entry/doctype/gate_pass/gate_pass.js` → expect exit 0.
Then (browser, deferred to user or driven separately): on a submitted PO gate pass, the "Create Purchase Receipt" button appears; clicking it creates the draft PRs and the button disappears (replaced by "View Purchase Receipts" links). The error path (force a failure) shows the thrown message and creates nothing.

- [ ] **Step 5: Commit**

```bash
git add gate_entry/gate_entry/doctype/gate_pass/gate_pass.js
git commit -m "feat: bulk Create Purchase Receipt button for PO gate passes; remove realtime listener (#17)"
```

---

## Task 3: Migration fix — allow updating submitted legacy gate passes (TDD)

**Files:**
- Modify: `gate_entry/patches/v1_1/migrate_single_pr_to_invoices.py`
- Test: `gate_entry/gate_entry/doctype/gate_pass/test_gate_pass.py`

**Interfaces:**
- Consumes: `_build_submitted_gate_pass` (Task 1).

- [ ] **Step 1: Write the failing test (the mechanism the migration relies on)**

Legacy gate passes with a PR are **submitted**; the patch's `save()` to append the invoice row would raise `UpdateAfterSubmitError` without the flag. Test that the flag enables it. Add to `test_gate_pass.py`:

```python
class TestSubmittedGatePassUpdate(FrappeTestCase):
	def test_can_append_invoice_row_to_submitted_gate_pass_with_flag(self):
		po = _make_test_purchase_order(qty=10)
		gp = _build_submitted_gate_pass(po, [("INV-A", 3)])  # docstatus 1

		gp.append("gate_pass_invoices", {"supplier_delivery_note": "INV-LATE", "grn_status": "Pending"})
		gp.flags.ignore_validate_update_after_submit = True
		gp.save(ignore_permissions=True)  # must NOT raise UpdateAfterSubmitError

		gp.reload()
		self.assertIn("INV-LATE", [r.supplier_delivery_note for r in gp.gate_pass_invoices])
```

- [ ] **Step 2: Run to verify it fails**

Run: `bench --site gate.localhost run-tests --module gate_entry.gate_entry.doctype.gate_pass.test_gate_pass --test test_can_append_invoice_row_to_submitted_gate_pass_with_flag`
First confirm it FAILS *without* the flag: temporarily comment the `gp.flags.ignore_validate_update_after_submit = True` line, run, expect `UpdateAfterSubmitError`; then restore the line. (This proves the flag is what makes the patch's save legal.)

- [ ] **Step 3: Add the flag to the migration patch**

In `migrate_single_pr_to_invoices.py`, in the per-row loop, set the flag alongside the existing flags before `save()`:

```python
			gate_pass.flags.ignore_validate = True
			gate_pass.flags.ignore_links = True
			gate_pass.flags.ignore_validate_update_after_submit = True
			gate_pass.save(ignore_permissions=True)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `bench --site gate.localhost run-tests --module gate_entry.gate_entry.doctype.gate_pass.test_gate_pass --test test_can_append_invoice_row_to_submitted_gate_pass_with_flag`
Expected: PASS on BOTH benches.

- [ ] **Step 5: Commit**

```bash
git add gate_entry/patches/v1_1/migrate_single_pr_to_invoices.py gate_entry/gate_entry/doctype/gate_pass/test_gate_pass.py
git commit -m "fix: migration can update submitted legacy gate passes (ignore_validate_update_after_submit) (#17)"
```

---

## Task 4: Docs — reflect the manual stores-triggered flow

**Files:**
- Modify: `README.md`, `USER_GUIDE.md`, `CHANGELOG.md`

- [ ] **Step 1: Update the docs**

Wherever PR #18's docs say the system *auto-creates* PRs on submit / the guard is *notified* when the background job finishes, replace with: after the guard submits the Gate Entry, a **stores/downstream user opens it and clicks "Create Purchase Receipt"**, which creates **all** per-invoice **draft** Purchase Receipts at once (all-or-nothing); the guard never creates or touches PRs. Specifically:
- **README.md** "Multiple Invoices per Gate Pass" subsection: replace the auto-on-submit sentence.
- **USER_GUIDE.md** SOP: the guard's steps end at *submit*; add a short "Stores: creating GRNs" note (open submitted gate pass → Create Purchase Receipt → draft PRs created).
- **CHANGELOG.md** [Unreleased]: under Changed, note "GRNs are now created by an explicit, all-or-nothing 'Create Purchase Receipt' action (stores-triggered) instead of an automatic background job on submit."

- [ ] **Step 2: Commit**

```bash
git add README.md USER_GUIDE.md CHANGELOG.md
git commit -m "docs: stores-triggered bulk GRN creation (#17)"
```

---

## Final verification

- [ ] **Full app suite on both versions**

Run on each: `bench --site development.localhost run-tests --app gate_entry` (bench15) and `bench --site frappe16.localhost run-tests --app gate_entry` (bench16).
Expected: all pass — `TestCreatePurchaseReceipts` (4), `TestSubmittedGatePassUpdate` (1), plus the retained cancel/`grn_status`/validation tests; no leftover references to `generate_purchase_receipts` / `_notify_grn_generation` / the realtime event.

- [ ] **Grep for dead references**

Run: `grep -rn "generate_purchase_receipts\|_notify_grn_generation\|gate_pass_grn_generated" gate_entry` → expect **no matches** (all removed).

- [ ] **Lint**

Run: `pre-commit run --files $(git diff --name-only develop...HEAD)` → ruff/eslint/prettier clean.

- [ ] **Owed before release:** dry-run the migration against a prod snapshot containing a *submitted* legacy PO gate pass (per spec §8).
