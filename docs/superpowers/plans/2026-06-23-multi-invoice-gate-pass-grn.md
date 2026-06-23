# Multi-Invoice Gate Entry → Auto-Generated GRNs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let one Gate Pass (one PO, one vehicle, one supplier) record N supplier invoices, and auto-create one draft Purchase Receipt per invoice when the Gate Pass is submitted.

**Architecture:** Add a `Gate Pass Invoice` child table and tag each `Gate Pass Table` item row with its invoice number. The guard enters invoice-grouped items on the form; `on_submit` enqueues a background job that builds one draft Purchase Receipt per invoice (reusing the existing PR field-mapping), links each PR back to its invoice row, and notifies the guard. The single header `supplier_delivery_note`/`purchase_receipt` fields are migrated into the new tables and removed.

**Tech Stack:** Frappe Framework v15 / ERPNext v15, Python, Frappe DocType JSON, vanilla JS (jQuery + `frappe.ui.Dialog`), `FrappeTestCase`.

Spec: [`docs/superpowers/specs/2026-06-23-multi-invoice-gate-pass-grn-design.md`](../specs/2026-06-23-multi-invoice-gate-pass-grn-design.md)

## Global Constraints

- **Scope:** Purchase Order → Purchase Receipt flow only. Do NOT touch Subcontracting, Sales Invoice, Delivery Note, or Stock Entry flows. The new behavior is gated on `document_reference == "Purchase Order"`.
- **PRs are created as drafts** (`pr.insert()`, never `pr.submit()`).
- **PR creation runs in a background job** via `frappe.enqueue(..., queue="long", now=frappe.flags.in_test)` — mirror `on_stock_entry_submit` ([gate_pass.py:2233](../../../gate_entry/gate_entry/doctype/gate_pass/gate_pass.py)).
- **Invoice numbers are unique within a Gate Pass**; every item qty is `> 0`; cumulative qty per PO item ≤ ordered (ERPNext over-receipt tolerance respected).
- **Dual-version support (HARD):** the app must work on **Frappe/ERPNext v15 (15.102.1) and v16 (16.13.0)**. Avoid version-specific APIs; guard every optional ERPNext field access with `.get(...)`. **Every `migrate` / `run-tests` step must pass on BOTH benches.**
- **Verification environments** — `bench --site gate.localhost <cmd>` in the steps below is shorthand for running the command on **both**:
  - v15: `cd /Users/gurudattkulkarni/Workspace/bench15 && bench --site development.localhost <cmd>`
  - v16: `cd /Users/gurudattkulkarni/Workspace/bench16 && bench --site frappe16.localhost <cmd>`
  Both benches symlink `apps/gate_entry` → this checkout and are on branch `issue-17-multi-invoice-grn`, so edits here are live in both with no copy step.
- **Module path for tests:** `gate_entry.gate_entry.doctype.gate_pass.test_gate_pass`.
- Frappe does NOT drop DB columns when a field is removed from a DocType JSON — orphan columns persist, so the migration patch can read old values via raw SQL.
- Follow existing code style: tabs for indentation in Python, the file's existing patterns.

---

## File structure

| File | Responsibility |
|---|---|
| `gate_entry/gate_entry/doctype/gate_pass_invoice/` (new) | New child DocType: one row per supplier invoice (invoice no, invoice date, PR link, grn_status). |
| `gate_entry/gate_entry/doctype/gate_pass_table/gate_pass_table.json` | Add `supplier_delivery_note` tag field. |
| `gate_entry/gate_entry/doctype/gate_pass/gate_pass.json` | Add `gate_pass_invoices` table + section; remove header `purchase_receipt`; re-scope header `supplier_delivery_note` to non-PO (kept for Subcontracting). |
| `gate_entry/gate_entry/doctype/gate_pass/gate_pass.py` | Per-invoice validation; refactor PR build into helper; background job; `on_submit` enqueue; list-aware cancel/amend; list-aware PR cancel/trash handlers; notification. |
| `gate_entry/gate_entry/doctype/gate_pass/gate_pass.js` | Remove manual PR buttons. |
| `gate_entry/public/js/gate_pass_custom_ui.js` | Invoice-grouped item entry for the PO flow. |
| `gate_entry/patches/v1_1/migrate_single_pr_to_invoices.py` (new) | Migrate legacy single-PR gate passes into the new tables; drop orphan columns. |
| `gate_entry/patches.txt` | Register the patch under `[post_model_sync]`. |
| `gate_entry/hooks.py` | Fix `document_links` for Purchase Receipt. |
| report `pending_gate_passes.py` | Replace the `gp.purchase_receipt` filter with a NOT-EXISTS against the invoices table. (`material_reconciliation.py` needs NO change — it reads Purchase Receipt data directly.) |
| `gate_entry/gate_entry/doctype/gate_pass/test_gate_pass.py` | Integration tests for the new flow. |

---

## Task 1: Create the `Gate Pass Invoice` child DocType

**Files:**
- Create: `gate_entry/gate_entry/doctype/gate_pass_invoice/__init__.py`
- Create: `gate_entry/gate_entry/doctype/gate_pass_invoice/gate_pass_invoice.json`
- Create: `gate_entry/gate_entry/doctype/gate_pass_invoice/gate_pass_invoice.py`

**Interfaces:**
- Produces: child DocType `Gate Pass Invoice` with fields `supplier_delivery_note` (Data, reqd), `invoice_date` (Date), `purchase_receipt` (Link→Purchase Receipt, read_only, no_copy), `grn_status` (Select: `Pending`/`Draft`/`Submitted`/`Cancelled`, default `Pending`, read_only).

- [ ] **Step 1: Create the package init**

Create `gate_entry/gate_entry/doctype/gate_pass_invoice/__init__.py` as an empty file.

- [ ] **Step 2: Create the DocType JSON**

Create `gate_entry/gate_entry/doctype/gate_pass_invoice/gate_pass_invoice.json`:

```json
{
 "actions": [],
 "allow_rename": 1,
 "creation": "2026-06-23 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "supplier_delivery_note",
  "invoice_date",
  "column_break_main",
  "purchase_receipt",
  "grn_status"
 ],
 "fields": [
  {
   "fieldname": "supplier_delivery_note",
   "fieldtype": "Data",
   "in_list_view": 1,
   "label": "Supplier Invoice No",
   "reqd": 1
  },
  {
   "fieldname": "invoice_date",
   "fieldtype": "Date",
   "in_list_view": 1,
   "label": "Invoice Date"
  },
  {
   "fieldname": "column_break_main",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "purchase_receipt",
   "fieldtype": "Link",
   "in_list_view": 1,
   "label": "Purchase Receipt",
   "no_copy": 1,
   "options": "Purchase Receipt",
   "read_only": 1
  },
  {
   "default": "Pending",
   "fieldname": "grn_status",
   "fieldtype": "Select",
   "in_list_view": 1,
   "label": "GRN Status",
   "options": "Pending\nDraft\nSubmitted\nCancelled",
   "read_only": 1
  }
 ],
 "grid_page_length": 50,
 "index_web_pages_for_search": 1,
 "istable": 1,
 "links": [],
 "modified": "2026-06-23 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Gate Entry",
 "name": "Gate Pass Invoice",
 "owner": "Administrator",
 "permissions": [],
 "row_format": "Dynamic",
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

- [ ] **Step 3: Create the controller**

Create `gate_entry/gate_entry/doctype/gate_pass_invoice/gate_pass_invoice.py`:

```python
# Copyright (c) 2026, Gurudatt Kulkarni and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class GatePassInvoice(Document):
	pass
```

- [ ] **Step 4: Migrate and verify the doctype loads**

Run: `bench --site gate.localhost migrate`
Expected: completes without error; `Gate Pass Invoice` appears in the DocType list.

- [ ] **Step 5: Commit**

```bash
git add gate_entry/gate_entry/doctype/gate_pass_invoice/
git commit -m "feat: add Gate Pass Invoice child doctype (#17)"
```

---

## Task 2: Tag item rows with their invoice, and wire the invoice table into Gate Pass

**Files:**
- Modify: `gate_entry/gate_entry/doctype/gate_pass_table/gate_pass_table.json`
- Modify: `gate_entry/gate_entry/doctype/gate_pass/gate_pass.json`

**Interfaces:**
- Produces: `Gate Pass Table.supplier_delivery_note` (Data) tag field; `Gate Pass.gate_pass_invoices` (Table → Gate Pass Invoice). Removes `Gate Pass.purchase_receipt`. **Keeps** `Gate Pass.supplier_delivery_note` but re-scopes its visibility to non-PO flows.

> **Why keep `supplier_delivery_note`?** It is shared: the Subcontracting flow copies it onto the Subcontracting Receipt ([gate_pass.py:1717](../../../gate_entry/gate_entry/doctype/gate_pass/gate_pass.py)). Removing it would break out-of-scope behavior. Only `purchase_receipt` (PO-exclusive) is removed.

- [ ] **Step 1: Add the tag field to Gate Pass Table**

In `gate_pass_table.json`, add `"supplier_delivery_note"` to `field_order` immediately after `"order_item_name"`, and add this field definition to the `fields` array:

```json
  {
   "fieldname": "supplier_delivery_note",
   "fieldtype": "Data",
   "label": "Supplier Invoice No",
   "read_only": 1
  }
```

(This is the child `Gate Pass Table` doctype — a different doctype from the parent `Gate Pass`, so there is no field-name clash with the parent's header `supplier_delivery_note`.)

- [ ] **Step 2: Edit Gate Pass — add invoices table, remove only `purchase_receipt`, re-scope `supplier_delivery_note`**

In `gate_pass/gate_pass.json`:

1. In `field_order`, add a new section just before `"material_details_section"`:

```
  "purchase_invoices_section",
  "gate_pass_invoices",
```

2. **Remove** `"purchase_receipt"` from `field_order`, and **remove** the `purchase_receipt` field object (the one with `"label": "Purchase Receipt Reference"`) from the `fields` array. Leave `subcontracting_receipt` and `stock_entry` and the `receipt_references_section` untouched.

3. **Keep** the `supplier_delivery_note` field object, but change its `depends_on` from `"eval:doc.document_reference in ['Purchase Order', 'Subcontracting Order']"` to:

```json
   "depends_on": "eval:doc.document_reference != 'Purchase Order'"
```

4. Add these two field objects to the `fields` array:

```json
  {
   "collapsible": 1,
   "depends_on": "eval:doc.document_reference=='Purchase Order'",
   "fieldname": "purchase_invoices_section",
   "fieldtype": "Section Break",
   "label": "Supplier Invoices & GRNs"
  },
  {
   "depends_on": "eval:doc.document_reference=='Purchase Order'",
   "fieldname": "gate_pass_invoices",
   "fieldtype": "Table",
   "label": "Supplier Invoices",
   "options": "Gate Pass Invoice"
  }
```

- [ ] **Step 3: Migrate and verify**

Run: `bench --site gate.localhost migrate`
Then in `bench --site gate.localhost console`:

```python
import frappe
meta = frappe.get_meta("Gate Pass")
assert meta.get_field("gate_pass_invoices"), "invoices table missing"
assert not meta.get_field("purchase_receipt"), "purchase_receipt should be removed"
assert meta.get_field("supplier_delivery_note"), "header supplier_delivery_note must stay (subcontracting needs it)"
assert frappe.get_meta("Gate Pass Table").get_field("supplier_delivery_note"), "item tag missing"
print("OK")
```
Expected: prints `OK`.

- [ ] **Step 4: Commit**

```bash
git add gate_entry/gate_entry/doctype/gate_pass_table/gate_pass_table.json gate_entry/gate_entry/doctype/gate_pass/gate_pass.json
git commit -m "feat: add invoices table to Gate Pass, retire single PR/invoice fields (#17)"
```

---

## Task 3: Migration patch — convert legacy single-PR gate passes

**Files:**
- Create: `gate_entry/patches/__init__.py` (if missing)
- Create: `gate_entry/patches/v1_1/__init__.py`
- Create: `gate_entry/patches/v1_1/migrate_single_pr_to_invoices.py`
- Modify: `gate_entry/patches.txt`

**Interfaces:**
- Consumes: orphan DB columns `tabGate Pass`.`purchase_receipt`, `tabGate Pass`.`supplier_delivery_note` (still physically present after Task 2 removed the fields).
- Produces: one `Gate Pass Invoice` row per legacy gate pass; tagged item rows; dropped orphan columns.

- [ ] **Step 1: Create patch package files**

Create empty `gate_entry/patches/__init__.py` and `gate_entry/patches/v1_1/__init__.py` (skip any that already exist).

- [ ] **Step 2: Write the patch**

Create `gate_entry/patches/v1_1/migrate_single_pr_to_invoices.py`:

```python
# Copyright (c) 2026, Gurudatt Kulkarni and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Migrate legacy single-invoice / single-PR Gate Passes into the
	Gate Pass Invoice child table, then drop the now-orphan columns.

	Frappe leaves the physical columns in place when the fields are removed
	from the DocType JSON, so we read them with raw SQL.
	"""
	columns = frappe.db.get_table_columns("Gate Pass")
	has_pr = "purchase_receipt" in columns
	has_sdn = "supplier_delivery_note" in columns

	if has_pr or has_sdn:
		pr_col = "purchase_receipt" if has_pr else "NULL"
		sdn_col = "supplier_delivery_note" if has_sdn else "NULL"
		rows = frappe.db.sql(
			f"""
			SELECT name, {pr_col} AS purchase_receipt, {sdn_col} AS supplier_delivery_note
			FROM `tabGate Pass`
			WHERE document_reference = 'Purchase Order'
			""",
			as_dict=True,
		)

		for row in rows:
			invoice_no = (row.supplier_delivery_note or "").strip()
			pr = (row.purchase_receipt or "").strip()
			if not invoice_no and not pr:
				continue

			gate_pass = frappe.get_doc("Gate Pass", row.name)

			# Skip if already migrated (idempotent re-run)
			if gate_pass.get("gate_pass_invoices"):
				continue

			grn_status = "Pending"
			if pr:
				docstatus = frappe.db.get_value("Purchase Receipt", pr, "docstatus")
				grn_status = {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(docstatus, "Pending")

			invoice_label = invoice_no or pr
			gate_pass.append(
				"gate_pass_invoices",
				{
					"supplier_delivery_note": invoice_label,
					"purchase_receipt": pr or None,
					"grn_status": grn_status,
				},
			)

			# Tag every existing item row to this single invoice
			for item in gate_pass.get("gate_pass_table", []):
				item.supplier_delivery_note = invoice_label

			# The invoice number now lives on the invoice row; clear the PO header value
			gate_pass.supplier_delivery_note = None

			gate_pass.flags.ignore_validate = True
			gate_pass.flags.ignore_links = True
			gate_pass.save(ignore_permissions=True)

	# Drop only the orphan purchase_receipt column.
	# supplier_delivery_note stays — it remains a live field for the Subcontracting flow.
	if has_pr:
		frappe.db.sql_ddl("ALTER TABLE `tabGate Pass` DROP COLUMN `purchase_receipt`")

	frappe.db.commit()
```

- [ ] **Step 3: Register the patch**

In `gate_entry/patches.txt`, under the `[post_model_sync]` section, add:

```
gate_entry.patches.v1_1.migrate_single_pr_to_invoices
```

- [ ] **Step 4: Run the patch**

Run: `bench --site gate.localhost migrate`
Expected: completes; re-running `bench --site gate.localhost migrate` again is a no-op (idempotent) and does not error on the already-dropped columns.

- [ ] **Step 5: Commit**

```bash
git add gate_entry/patches/ gate_entry/patches.txt
git commit -m "feat: migrate legacy single-PR gate passes to invoices table (#17)"
```

---

## Task 4: Backend — per-invoice validation

**Files:**
- Modify: `gate_entry/gate_entry/doctype/gate_pass/gate_pass.py`
- Test: `gate_entry/gate_entry/doctype/gate_pass/test_gate_pass.py`

**Interfaces:**
- Produces: `GatePass.validate_purchase_invoices()` — raises `frappe.ValidationError` on: no invoices, an invoice with no items, qty ≤ 0, duplicate invoice number, item not on the PO, cumulative qty over ordered. Called from `validate()` when `document_reference == "Purchase Order"`.

- [ ] **Step 1: Write the failing tests**

Add to `test_gate_pass.py`:

```python
class TestPurchaseInvoiceValidation(FrappeTestCase):
	def _po_gate_pass(self, invoices):
		gp = frappe.new_doc("Gate Pass")
		gp.document_reference = "Purchase Order"
		gp.reference_number = "PO-DUMMY"
		for inv in invoices:
			gp.append("gate_pass_invoices", {"supplier_delivery_note": inv})
		return gp

	def test_duplicate_invoice_number_rejected(self):
		gp = self._po_gate_pass(["INV-1", "INV-1"])
		gp.append("gate_pass_table", {"item_code": "X", "received_qty": 5,
			"order_item_name": "POI-1", "supplier_delivery_note": "INV-1"})
		with self.assertRaises(frappe.ValidationError):
			gp.validate_purchase_invoices()

	def test_invoice_without_items_rejected(self):
		gp = self._po_gate_pass(["INV-1"])
		with self.assertRaises(frappe.ValidationError):
			gp.validate_purchase_invoices()

	def test_zero_qty_rejected(self):
		gp = self._po_gate_pass(["INV-1"])
		gp.append("gate_pass_table", {"item_code": "X", "received_qty": 0,
			"order_item_name": "POI-1", "supplier_delivery_note": "INV-1"})
		with self.assertRaises(frappe.ValidationError):
			gp.validate_purchase_invoices()

	def test_no_invoices_rejected(self):
		gp = self._po_gate_pass([])
		with self.assertRaises(frappe.ValidationError):
			gp.validate_purchase_invoices()
```

- [ ] **Step 2: Run to verify failure**

Run: `bench --site gate.localhost run-tests --module gate_entry.gate_entry.doctype.gate_pass.test_gate_pass --test test_duplicate_invoice_number_rejected`
Expected: FAIL — `AttributeError: 'GatePass' object has no attribute 'validate_purchase_invoices'`.

- [ ] **Step 3: Implement the validation method**

In `gate_pass.py`, add this method to the `GatePass` class:

```python
	def validate_purchase_invoices(self):
		"""Validate invoice-grouped items for the Purchase Order flow."""
		if self.document_reference != "Purchase Order":
			return

		invoices = self.get("gate_pass_invoices") or []
		if not invoices:
			frappe.throw(_("Add at least one supplier invoice before submitting."))

		# Unique invoice numbers
		seen = set()
		for inv in invoices:
			key = (inv.supplier_delivery_note or "").strip()
			if not key:
				frappe.throw(_("Supplier Invoice No is required on every invoice row."))
			if key in seen:
				frappe.throw(_("Duplicate supplier invoice number: {0}").format(key))
			seen.add(key)

		# Items grouped by invoice; qty > 0; invoice tag must exist
		items_by_invoice = {}
		for item in self.get("gate_pass_table") or []:
			tag = (item.supplier_delivery_note or "").strip()
			if not tag:
				frappe.throw(
					_("Item {0} is not assigned to any invoice.").format(item.item_code)
				)
			if tag not in seen:
				frappe.throw(
					_("Item {0} references unknown invoice {1}.").format(item.item_code, tag)
				)
			if flt(item.received_qty) <= 0:
				frappe.throw(
					_("Quantity for item {0} on invoice {1} must be greater than zero.").format(
						item.item_code, tag
					)
				)
			items_by_invoice.setdefault(tag, []).append(item)

		# Every invoice must have at least one item
		for inv in invoices:
			key = (inv.supplier_delivery_note or "").strip()
			if not items_by_invoice.get(key):
				frappe.throw(_("Invoice {0} has no items.").format(key))
```

- [ ] **Step 4: Call it from `validate()`**

In `gate_pass.py`, inside `validate()`, after the existing `self.validate_discrepancy_quantities()` line, add:

```python
		self.validate_purchase_invoices()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `bench --site gate.localhost run-tests --module gate_entry.gate_entry.doctype.gate_pass.test_gate_pass`
Expected: the four new tests PASS.

- [ ] **Step 6: Commit**

```bash
git add gate_entry/gate_entry/doctype/gate_pass/gate_pass.py gate_entry/gate_entry/doctype/gate_pass/test_gate_pass.py
git commit -m "feat: per-invoice validation for Gate Pass PO flow (#17)"
```

---

## Task 5: Backend — refactor PR builder into a per-invoice helper

**Files:**
- Modify: `gate_entry/gate_entry/doctype/gate_pass/gate_pass.py`

**Interfaces:**
- Produces: `_build_purchase_receipt(gate_pass, invoice_no, item_rows)` → inserts and returns a draft `Purchase Receipt` doc built from `item_rows` (a list of `Gate Pass Table` rows) against `gate_pass.reference_number` (the PO), with `pr.supplier_delivery_note = invoice_no` and `pr.gate_pass = gate_pass.name`.

- [ ] **Step 1: Extract the helper from `create_purchase_receipt`**

The existing `create_purchase_receipt` ([gate_pass.py:1508-1671](../../../gate_entry/gate_entry/doctype/gate_pass/gate_pass.py)) already contains the full PR header + per-item field mapping. Extract its body (the PR header mapping at lines ~1541-1564, the per-item loop at ~1571-1659, and `pr.run_method("set_missing_values"); pr.insert()`) into a new module-level function. Replace the `for gate_pass_item in gate_pass.gate_pass_table:` loop header with `for gate_pass_item in item_rows:`, set `pr.supplier_delivery_note = invoice_no`, and return `pr` instead of stamping the (now-removed) single `gate_pass.purchase_receipt` field.

```python
def _build_purchase_receipt(gate_pass, invoice_no, item_rows):
	"""Build and insert a draft Purchase Receipt for one invoice's items.

	`item_rows` is a list of Gate Pass Table rows (already filtered to one
	invoice). Returns the inserted (draft) Purchase Receipt document.
	"""
	purchase_order = frappe.get_doc("Purchase Order", gate_pass.reference_number)

	pr = frappe.new_doc("Purchase Receipt")
	pr.supplier = gate_pass.supplier
	pr.company = gate_pass.company
	pr.gate_pass = gate_pass.name
	pr.supplier_delivery_note = invoice_no
	# --- header mapping copied verbatim from the old create_purchase_receipt ---
	pr.supplier_warehouse = purchase_order.supplier_warehouse
	pr.currency = purchase_order.currency
	pr.conversion_rate = purchase_order.conversion_rate
	pr.buying_price_list = purchase_order.buying_price_list
	pr.price_list_currency = purchase_order.price_list_currency
	pr.plc_conversion_rate = purchase_order.plc_conversion_rate
	pr.ignore_pricing_rule = purchase_order.ignore_pricing_rule
	pr.set_warehouse = purchase_order.set_warehouse
	pr.supplier_address = purchase_order.supplier_address
	pr.address_display = purchase_order.address_display
	pr.contact_person = purchase_order.contact_person
	pr.contact_display = purchase_order.contact_display
	pr.contact_mobile = purchase_order.contact_mobile
	pr.contact_email = purchase_order.contact_email
	pr.shipping_address = purchase_order.shipping_address
	pr.shipping_address_display = purchase_order.shipping_address_display
	pr.vehicle_no = gate_pass.vehicle_number
	pr.driver_name = gate_pass.driver_name

	for gate_pass_item in item_rows:
		po_item = frappe.get_doc("Purchase Order Item", gate_pass_item.order_item_name)
		received_qty = flt(gate_pass_item.received_qty)
		conversion_factor = flt(po_item.conversion_factor) or 1.0
		received_stock_qty = received_qty * conversion_factor

		pr_item = {
			"item_code": po_item.item_code,
			"item_name": po_item.item_name,
			"description": po_item.description,
			"item_group": po_item.item_group,
			"brand": po_item.brand,
			"image": po_item.image,
			"uom": po_item.uom,
			"stock_uom": po_item.stock_uom,
			"conversion_factor": conversion_factor,
			"qty": received_qty,
			"received_qty": received_qty,
			"stock_qty": received_stock_qty,
			"received_stock_qty": received_stock_qty,
			"rate": flt(po_item.rate),
			"price_list_rate": flt(po_item.price_list_rate),
			"base_rate": flt(po_item.base_rate),
			"base_price_list_rate": flt(po_item.base_price_list_rate),
			"discount_percentage": flt(po_item.discount_percentage),
			"discount_amount": flt(po_item.discount_amount),
			"margin_type": po_item.margin_type,
			"margin_rate_or_amount": flt(po_item.margin_rate_or_amount),
			"warehouse": gate_pass_item.warehouse or po_item.warehouse,
			"from_warehouse": po_item.from_warehouse if po_item.get("from_warehouse") else None,
			"expense_account": po_item.expense_account,
			"cost_center": po_item.cost_center,
			"project": po_item.project if po_item.get("project") else None,
			"schedule_date": po_item.schedule_date if po_item.get("schedule_date") else None,
			"material_request": po_item.material_request if po_item.get("material_request") else None,
			"material_request_item": po_item.material_request_item
			if po_item.get("material_request_item")
			else None,
			"sales_order": po_item.sales_order if po_item.get("sales_order") else None,
			"sales_order_item": po_item.sales_order_item if po_item.get("sales_order_item") else None,
			"bom": po_item.bom if po_item.get("bom") else None,
			"wip_composite_asset": po_item.wip_composite_asset
			if po_item.get("wip_composite_asset")
			else None,
			"manufacturer": po_item.manufacturer if po_item.get("manufacturer") else None,
			"manufacturer_part_no": po_item.manufacturer_part_no
			if po_item.get("manufacturer_part_no")
			else None,
			"supplier_part_no": po_item.supplier_part_no if po_item.get("supplier_part_no") else None,
			"is_fixed_asset": po_item.is_fixed_asset if po_item.get("is_fixed_asset") else 0,
			"asset_location": po_item.asset_location if po_item.get("asset_location") else None,
			"asset_category": po_item.asset_category if po_item.get("asset_category") else None,
			"item_tax_template": po_item.item_tax_template if po_item.get("item_tax_template") else None,
			"item_tax_rate": po_item.item_tax_rate if po_item.get("item_tax_rate") else None,
			"gst_treatment": po_item.gst_treatment if po_item.get("gst_treatment") else None,
			"product_bundle": po_item.product_bundle if po_item.get("product_bundle") else None,
			"is_free_item": po_item.is_free_item if po_item.get("is_free_item") else 0,
			"purchase_order": gate_pass.reference_number,
			"purchase_order_item": gate_pass_item.order_item_name,
		}
		if gate_pass_item.get("rejected_warehouse"):
			pr_item["rejected_warehouse"] = gate_pass_item.rejected_warehouse
		if po_item.get("apply_tds"):
			pr_item["apply_tds"] = po_item.apply_tds

		pr.append("items", pr_item)

	pr.run_method("set_missing_values")
	pr.insert()
	return pr
```

- [ ] **Step 2: Remove the old whitelisted `create_purchase_receipt`**

Delete the entire `@frappe.whitelist()`-decorated `create_purchase_receipt(gate_pass_name)` function (the one starting at [gate_pass.py:1508](../../../gate_entry/gate_entry/doctype/gate_pass/gate_pass.py)). Its PR-building logic now lives in `_build_purchase_receipt`; its caller (the JS button) is removed in Task 8.

- [ ] **Step 3: Verify import / syntax**

Run: `bench --site gate.localhost console`

```python
from gate_entry.gate_entry.doctype.gate_pass.gate_pass import _build_purchase_receipt
print("import OK")
```
Expected: prints `import OK`.

- [ ] **Step 4: Commit**

```bash
git add gate_entry/gate_entry/doctype/gate_pass/gate_pass.py
git commit -m "refactor: extract _build_purchase_receipt per-invoice helper (#17)"
```

---

## Task 6: Backend — background job that auto-creates GRNs on submit

**Files:**
- Modify: `gate_entry/gate_entry/doctype/gate_pass/gate_pass.py`
- Test: `gate_entry/gate_entry/doctype/gate_pass/test_gate_pass.py`

**Interfaces:**
- Consumes: `_build_purchase_receipt` (Task 5).
- Produces: module-level `generate_purchase_receipts(gate_pass_name, enqueued_by=None)` — loops invoices, builds one draft PR per invoice, writes `purchase_receipt` + `grn_status="Draft"` onto each invoice row via `db_set`, notifies the user, logs per-invoice failures. Called from `GatePass.on_submit` via `frappe.enqueue` for the PO flow.

- [ ] **Step 1: Write the failing test**

Add to `test_gate_pass.py`. This is an integration test that needs a submitted PO with the test item; it is skipped if the fixtures aren't present.

```python
class TestAutoGRN(FrappeTestCase):
	def test_generate_purchase_receipts_creates_one_pr_per_invoice(self):
		from gate_entry.gate_entry.doctype.gate_pass.gate_pass import generate_purchase_receipts

		po = _make_test_purchase_order(qty=10)  # helper defined below
		gp = frappe.new_doc("Gate Pass")
		gp.document_reference = "Purchase Order"
		gp.reference_number = po.name
		gp.company = po.company
		gp.supplier = po.supplier
		gp.vehicle_number = "KA01AB1234"
		gp.driver_name = "Test Driver"
		for inv, qty in (("INV-A", 3), ("INV-B", 4)):
			gp.append("gate_pass_invoices", {"supplier_delivery_note": inv})
			gp.append("gate_pass_table", {
				"item_code": po.items[0].item_code,
				"received_qty": qty,
				"order_item_name": po.items[0].name,
				"warehouse": po.items[0].warehouse,
				"supplier_delivery_note": inv,
			})
		gp.submit()

		generate_purchase_receipts(gp.name)
		gp.reload()

		prs = [row.purchase_receipt for row in gp.gate_pass_invoices]
		self.assertEqual(len([p for p in prs if p]), 2)
		self.assertTrue(all(row.grn_status == "Draft" for row in gp.gate_pass_invoices))
```

Add the helper at module level in `test_gate_pass.py` (build it from your existing `_Test Gate Entry Item 1` + `Wind Power LLP`; adapt warehouse names to the test site):

```python
def _make_test_purchase_order(qty=10):
	import frappe
	po = frappe.new_doc("Purchase Order")
	po.supplier = "_Test Supplier"
	po.company = "Wind Power LLP"
	po.schedule_date = frappe.utils.nowdate()
	po.append("items", {
		"item_code": "_Test Gate Entry Item 1",
		"qty": qty,
		"rate": 100,
		"schedule_date": frappe.utils.nowdate(),
		"warehouse": "Stores - WP",
	})
	po.insert()
	po.submit()
	return po
```

- [ ] **Step 2: Run to verify failure**

Run: `bench --site gate.localhost run-tests --module gate_entry.gate_entry.doctype.gate_pass.test_gate_pass --test test_generate_purchase_receipts_creates_one_pr_per_invoice`
Expected: FAIL — `ImportError`/`AttributeError` for `generate_purchase_receipts`.

- [ ] **Step 3: Implement the job + on_submit enqueue + notification**

In `gate_pass.py`, add the module-level job:

```python
def generate_purchase_receipts(gate_pass_name, enqueued_by=None):
	"""Background job: create one draft Purchase Receipt per invoice row."""
	gate_pass = frappe.get_doc("Gate Pass", gate_pass_name)
	if gate_pass.document_reference != "Purchase Order" or gate_pass.docstatus != 1:
		return

	items_by_invoice = {}
	for item in gate_pass.get("gate_pass_table") or []:
		tag = (item.supplier_delivery_note or "").strip()
		if tag:
			items_by_invoice.setdefault(tag, []).append(item)

	created, failed = [], []
	for inv in gate_pass.get("gate_pass_invoices") or []:
		invoice_no = (inv.supplier_delivery_note or "").strip()
		if inv.purchase_receipt:
			continue  # already generated (idempotent)
		item_rows = items_by_invoice.get(invoice_no, [])
		if not item_rows:
			continue
		try:
			pr = _build_purchase_receipt(gate_pass, invoice_no, item_rows)
			inv.db_set("purchase_receipt", pr.name, update_modified=False)
			inv.db_set("grn_status", "Draft", update_modified=False)
			created.append(pr.name)
		except Exception:
			failed.append(invoice_no)
			frappe.log_error(
				message=frappe.get_traceback(),
				title=_("Auto GRN creation failed for Gate Pass {0} invoice {1}").format(
					gate_pass_name, invoice_no
				),
			)

	frappe.db.commit()
	_notify_grn_generation(gate_pass, enqueued_by, created, failed)


def _notify_grn_generation(gate_pass, enqueued_by, created, failed):
	"""Post a timeline comment and a desk notification to the guard."""
	user = enqueued_by or gate_pass.owner
	lines = []
	if created:
		lines.append(_("Created Purchase Receipts: {0}").format(", ".join(created)))
	if failed:
		lines.append(_("Failed for invoices: {0} (see Error Log)").format(", ".join(failed)))
	message = "<br>".join(lines) or _("No Purchase Receipts were generated.")

	gate_pass.add_comment("Comment", message)

	frappe.publish_realtime(
		"gate_pass_grn_generated",
		{"gate_pass": gate_pass.name, "message": message},
		user=user,
	)
```

Then in the `GatePass.on_submit` method, after the existing `self.update_stock_entry_reference()` line, add:

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

- [ ] **Step 4: Run the test to verify it passes**

Run: `bench --site gate.localhost run-tests --module gate_entry.gate_entry.doctype.gate_pass.test_gate_pass --test test_generate_purchase_receipts_creates_one_pr_per_invoice`
Expected: PASS (the job runs synchronously under `frappe.flags.in_test`).

- [ ] **Step 5: Commit**

```bash
git add gate_entry/gate_entry/doctype/gate_pass/gate_pass.py gate_entry/gate_entry/doctype/gate_pass/test_gate_pass.py
git commit -m "feat: auto-create one draft PR per invoice on submit + notify guard (#17)"
```

---

## Task 7: Backend — list-aware cancel/amend and PR cancel/trash handlers

**Files:**
- Modify: `gate_entry/gate_entry/doctype/gate_pass/gate_pass.py`
- Test: `gate_entry/gate_entry/doctype/gate_pass/test_gate_pass.py`

**Interfaces:**
- Consumes: `Gate Pass.gate_pass_invoices` rows (with `purchase_receipt`).
- Produces: cancel blocked while any linked PR is submitted; draft PRs deleted on cancel; `on_purchase_receipt_cancel`/`_trash` clear the matching invoice row.

- [ ] **Step 1: Write the failing test**

```python
class TestCancelBehavior(FrappeTestCase):
	def test_cancel_blocked_when_pr_submitted(self):
		# Build a submitted gate pass with one invoice whose PR is submitted
		po = _make_test_purchase_order(qty=5)
		gp = _submitted_po_gate_pass(po, [("INV-A", 5)])  # helper: builds+submits, runs job
		pr_name = gp.gate_pass_invoices[0].purchase_receipt
		frappe.get_doc("Purchase Receipt", pr_name).submit()
		gp.reload()
		with self.assertRaises(frappe.ValidationError):
			gp.cancel()
```

Add this `_submitted_po_gate_pass(po, invoices)` module-level helper near `_make_test_purchase_order`:

```python
def _submitted_po_gate_pass(po, invoices):
	import frappe
	from gate_entry.gate_entry.doctype.gate_pass.gate_pass import generate_purchase_receipts

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
	generate_purchase_receipts(gp.name)
	gp.reload()
	return gp
```

- [ ] **Step 2: Run to verify failure**

Run: `bench --site gate.localhost run-tests --module gate_entry.gate_entry.doctype.gate_pass.test_gate_pass --test test_cancel_blocked_when_pr_submitted`
Expected: FAIL — cancel succeeds today because `check_linked_receipts_before_cancel` only inspects the removed single field.

- [ ] **Step 3: Rewrite `check_linked_receipts_before_cancel`**

Replace the Purchase Receipt branch of `check_linked_receipts_before_cancel` (the block reading `self.purchase_receipt`) with an invoice-table loop, and delete draft PRs:

```python
		# Purchase Receipts from invoice rows
		for inv in self.get("gate_pass_invoices") or []:
			if not inv.purchase_receipt:
				continue
			docstatus = frappe.db.get_value("Purchase Receipt", inv.purchase_receipt, "docstatus")
			if docstatus == 1:
				linked_receipts.append(
					{"doctype": "Purchase Receipt", "name": inv.purchase_receipt, "status": "Submitted"}
				)
			elif docstatus == 0:
				# Draft PRs are deleted so cancellation leaves no orphans
				frappe.delete_doc("Purchase Receipt", inv.purchase_receipt, force=1, ignore_permissions=True)
				inv.db_set("purchase_receipt", None, update_modified=False)
				inv.db_set("grn_status", "Pending", update_modified=False)
```

(Keep the existing Subcontracting Receipt branch unchanged.)

- [ ] **Step 4: Rewrite `check_receipts_in_amended_document`**

Replace its Purchase Receipt branch (reading `original_doc.purchase_receipt`) with:

```python
		for inv in original_doc.get("gate_pass_invoices") or []:
			if not inv.purchase_receipt:
				continue
			if frappe.db.get_value("Purchase Receipt", inv.purchase_receipt, "docstatus") == 1:
				linked_receipts.append(
					{"doctype": "Purchase Receipt", "name": inv.purchase_receipt, "status": "Submitted"}
				)
```

- [ ] **Step 5: Update the PR cancel/trash handlers**

Replace `on_purchase_receipt_cancel` and `on_purchase_receipt_trash` so they clear the matching invoice row instead of a header field:

```python
def on_purchase_receipt_trash(doc, method):
	_clear_invoice_row_for_pr(doc)


def on_purchase_receipt_cancel(doc, method):
	_clear_invoice_row_for_pr(doc)


def _clear_invoice_row_for_pr(pr_doc):
	if not pr_doc.get("gate_pass"):
		return
	rows = frappe.get_all(
		"Gate Pass Invoice",
		filters={"parent": pr_doc.gate_pass, "purchase_receipt": pr_doc.name},
		fields=["name"],
	)
	for row in rows:
		frappe.db.set_value("Gate Pass Invoice", row.name, "purchase_receipt", None, update_modified=False)
		frappe.db.set_value("Gate Pass Invoice", row.name, "grn_status", "Pending", update_modified=False)
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `bench --site gate.localhost run-tests --module gate_entry.gate_entry.doctype.gate_pass.test_gate_pass --test test_cancel_blocked_when_pr_submitted`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add gate_entry/gate_entry/doctype/gate_pass/gate_pass.py gate_entry/gate_entry/doctype/gate_pass/test_gate_pass.py
git commit -m "feat: list-aware cancel/amend + PR handlers for invoice rows (#17)"
```

---

## Task 8: Frontend — remove the manual PR buttons (PO flow)

**Files:**
- Modify: `gate_entry/gate_entry/doctype/gate_pass/gate_pass.js`

**Interfaces:**
- Produces: `setup_receipt_buttons` no longer renders "Create/View Purchase Receipt" for the Purchase Order flow; the Subcontracting branch is unchanged.

- [ ] **Step 1: Remove the Purchase Order branch**

In `setup_receipt_buttons` ([gate_pass.js:220-249](../../../gate_entry/gate_entry/gate_entry/doctype/gate_pass/gate_pass.js)), delete the entire `if (frm.doc.document_reference === "Purchase Order") { ... }` block (the Create/View Purchase Receipt buttons). Keep the `else if (frm.doc.document_reference === "Subcontracting Order")` block.

- [ ] **Step 2: Remove the now-unused `create_purchase_receipt` JS function**

Delete the `function create_purchase_receipt(frm) { ... }` definition ([gate_pass.js:254-275](../../../gate_entry/gate_entry/gate_entry/doctype/gate_pass/gate_pass.js)) and any remaining reference to it.

- [ ] **Step 3: Verify in the browser**

Run: `bench --site gate.localhost clear-cache` then hard-reload a submitted Purchase Order Gate Pass.
Expected: no "Create Purchase Receipt" button; Subcontracting Order gate passes still show their button.

- [ ] **Step 4: Commit**

```bash
git add gate_entry/gate_entry/doctype/gate_pass/gate_pass.js
git commit -m "feat: remove manual PR button for PO flow (#17)"
```

---

## Task 9: Frontend — invoice-grouped item entry UI

**Files:**
- Modify: `gate_entry/public/js/gate_pass_custom_ui.js`

**Interfaces:**
- Consumes: `get_items` whitelisted method (unchanged); `frm.doc.gate_pass_invoices`, `frm.doc.gate_pass_table`.
- Produces: for `document_reference === "Purchase Order"` (Gate In), an "Add Invoice" → per-invoice "Add Item" UI that syncs both child tables, with per-item pending = `ordered − received-on-PO − allocated-in-sibling-invoices`.

- [ ] **Step 1: Add a PO-flow branch to `render()`**

In `GatePassCustomUI.render()`, before building the default `html`, add:

```javascript
		if (this.isPurchaseOrderFlow()) {
			this.render_invoice_grouped();
			return;
		}
```

And add the predicate method:

```javascript
	isPurchaseOrderFlow() {
		return this.frm?.doc?.document_reference === "Purchase Order" && this.isGateIn();
	}
```

- [ ] **Step 2: Implement the invoice-grouped renderer**

Add these methods to the class. They render one section per `gate_pass_invoices` row, each listing its tagged `gate_pass_table` items, with an "Add Invoice" control and a per-section "Add Item" button:

```javascript
	render_invoice_grouped() {
		const invoices = this.frm.doc.gate_pass_invoices || [];
		const editable = this.shouldAllowQuantityEdit();

		const groups = invoices
			.map((inv) => this.render_invoice_group(inv, editable))
			.join("");

		const add_invoice = editable
			? `<button class="btn btn-sm btn-primary add-invoice-btn" type="button">
					<i class="fa fa-plus"></i> ${__("Add Invoice")}</button>`
			: "";

		this.wrapper.html(`
			<div class="gate-pass-custom-ui">
				<div class="gate-pass-items-header">
					<h6 class="mb-3">${__("Supplier Invoices")}</h6>
					${add_invoice}
				</div>
				<div class="gate-pass-invoices-container">
					${invoices.length ? groups : this.render_empty_state()}
				</div>
			</div>
		`);
		this.bind_invoice_events();
	}

	render_invoice_group(inv, editable) {
		const invoice_no = inv.supplier_delivery_note || "";
		const rows = (this.frm.doc.gate_pass_table || []).filter(
			(it) => (it.supplier_delivery_note || "") === invoice_no
		);
		const items_html = rows
			.map(
				(it) => `
				<div class="item-row" data-name="${it.name}">
					<div class="item-col item-code-col">${frappe.utils.escape_html(it.item_code)}</div>
					<div class="item-col item-name-col">${frappe.utils.escape_html(it.item_name || "")}</div>
					<div class="item-col received-qty-col">
						<input type="number" class="form-control form-control-sm inv-qty-input"
							data-name="${it.name}" min="0" step="0.001"
							value="${flt(it.received_qty)}" ${editable ? "" : "disabled"} />
					</div>
					<div class="item-col actions-col">
						${
							editable
								? `<button class="btn btn-xs btn-danger inv-remove-item" data-name="${it.name}"><i class="fa fa-minus"></i></button>`
								: ""
						}
					</div>
				</div>`
			)
			.join("");

		const add_item = editable
			? `<button class="btn btn-xs btn-default inv-add-item" data-invoice="${frappe.utils.escape_html(invoice_no)}">
					<i class="fa fa-plus"></i> ${__("Add Item")}</button>`
			: "";

		return `
			<div class="invoice-group" data-invoice="${frappe.utils.escape_html(invoice_no)}" style="border:1px solid var(--border-color);border-radius:6px;padding:10px;margin-bottom:10px;">
				<div class="invoice-group-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
					<strong>${__("Invoice")}: ${frappe.utils.escape_html(invoice_no) || __("(unnamed)")}</strong>
					${editable ? `<button class="btn btn-xs btn-danger inv-remove-invoice" data-invoice="${frappe.utils.escape_html(invoice_no)}">${__("Remove Invoice")}</button>` : ""}
				</div>
				<div class="invoice-items">${items_html}</div>
				<div class="mt-2">${add_item}</div>
			</div>`;
	}
```

- [ ] **Step 3: Implement the event bindings and mutations**

Add these methods. `add_invoice` prompts for an invoice number (rejecting duplicates) and appends a `gate_pass_invoices` row; `inv-add-item` opens the existing item selector scoped to that invoice; quantity edits and removals update `gate_pass_table` and re-render:

```javascript
	bind_invoice_events() {
		const self = this;
		this.wrapper.find(".add-invoice-btn").off("click").on("click", () => self.add_invoice());
		this.wrapper.find(".inv-remove-invoice").off("click").on("click", function () {
			self.remove_invoice($(this).data("invoice"));
		});
		this.wrapper.find(".inv-add-item").off("click").on("click", function () {
			self.add_item_to_invoice($(this).data("invoice"));
		});
		this.wrapper.find(".inv-remove-item").off("click").on("click", function () {
			self.remove_invoice_item($(this).data("name"));
		});
		this.wrapper.find(".inv-qty-input").off("change").on("change", function () {
			self.set_invoice_item_qty($(this).data("name"), parseFloat($(this).val() || 0));
		});
	}

	add_invoice() {
		frappe.prompt(
			[{ fieldname: "invoice_no", label: __("Supplier Invoice No"), fieldtype: "Data", reqd: 1 }],
			(values) => {
				const invoice_no = (values.invoice_no || "").trim();
				const exists = (this.frm.doc.gate_pass_invoices || []).some(
					(inv) => (inv.supplier_delivery_note || "").trim() === invoice_no
				);
				if (exists) {
					frappe.msgprint(__("Invoice {0} already added.", [invoice_no]));
					return;
				}
				const row = this.frm.add_child("gate_pass_invoices");
				row.supplier_delivery_note = invoice_no;
				row.grn_status = "Pending";
				this.frm.refresh_field("gate_pass_invoices");
				this.frm.dirty();
				this.render();
			},
			__("Add Supplier Invoice"),
			__("Add")
		);
	}

	remove_invoice(invoice_no) {
		frappe.confirm(__("Remove invoice {0} and its items?", [invoice_no]), () => {
			this.frm.doc.gate_pass_invoices = (this.frm.doc.gate_pass_invoices || []).filter(
				(inv) => (inv.supplier_delivery_note || "") !== invoice_no
			);
			this.frm.doc.gate_pass_table = (this.frm.doc.gate_pass_table || []).filter(
				(it) => (it.supplier_delivery_note || "") !== invoice_no
			);
			this.frm.refresh_field("gate_pass_invoices");
			this.frm.refresh_field("gate_pass_table");
			this.frm.dirty();
			this.render();
		});
	}

	add_item_to_invoice(invoice_no) {
		frappe.call({
			method: "gate_entry.gate_entry.doctype.gate_pass.gate_pass.get_items",
			args: {
				document_reference: this.frm.doc.document_reference,
				reference_number: this.frm.doc.reference_number,
			},
			callback: (r) => {
				if (!r.message) return;
				const allocated = this.allocated_qty_by_po_item();
				const available = r.message.filter((item) => {
					const remaining = flt(item.pending_qty) - flt(allocated[item.order_item_name] || 0);
					return remaining > 0;
				});
				if (!available.length) {
					frappe.msgprint(__("No pending items left to add."));
					return;
				}
				this.show_invoice_item_selector(invoice_no, available, allocated);
			},
		});
	}

	allocated_qty_by_po_item() {
		const map = {};
		(this.frm.doc.gate_pass_table || []).forEach((it) => {
			if (it.order_item_name) {
				map[it.order_item_name] = flt(map[it.order_item_name] || 0) + flt(it.received_qty);
			}
		});
		return map;
	}

	show_invoice_item_selector(invoice_no, available, allocated) {
		const self = this;
		const already = (this.frm.doc.gate_pass_table || [])
			.filter((it) => (it.supplier_delivery_note || "") === invoice_no)
			.map((it) => it.order_item_name);
		const selectable = available.filter((it) => !already.includes(it.order_item_name));

		const dialog = new frappe.ui.Dialog({
			title: __("Add Items to Invoice {0}", [invoice_no]),
			fields: [{ fieldtype: "HTML", fieldname: "items_html" }],
			primary_action_label: __("Add Selected"),
			primary_action() {
				dialog.$wrapper.find('input[type="checkbox"]:checked').each(function () {
					const po_item_name = $(this).val();
					const item = selectable.find((i) => i.order_item_name === po_item_name);
					if (item) self.append_invoice_item(invoice_no, item);
				});
				dialog.hide();
				self.frm.refresh_field("gate_pass_table");
				self.frm.dirty();
				self.render();
			},
		});

		dialog.fields_dict.items_html.$wrapper.html(
			`<div class="item-selector-list">${selectable
				.map((item) => {
					const remaining = flt(item.pending_qty) - flt(allocated[item.order_item_name] || 0);
					return `<div class="checkbox"><label>
						<input type="checkbox" value="${item.order_item_name}">
						<strong>${frappe.utils.escape_html(item.item_code)}</strong> - ${frappe.utils.escape_html(item.item_name || "")}
						<span class="text-muted">(${__("Pending")}: ${remaining} ${frappe.utils.escape_html(item.uom || "")})</span>
					</label></div>`;
				})
				.join("")}</div>`
		);
		dialog.show();
	}

	append_invoice_item(invoice_no, item) {
		const row = this.frm.add_child("gate_pass_table");
		Object.assign(row, {
			item_code: item.item_code,
			item_name: item.item_name,
			description: item.description || "",
			uom: item.uom || "",
			stock_uom: item.stock_uom || "",
			conversion_factor: item.conversion_factor || 1.0,
			ordered_qty: item.ordered_qty || 0,
			received_qty: 0,
			rate: item.rate || 0,
			warehouse: item.warehouse || "",
			expense_account: item.expense_account || "",
			cost_center: item.cost_center || "",
			project: item.project || "",
			order_item_name: item.order_item_name || "",
			supplier_delivery_note: invoice_no,
		});
	}

	set_invoice_item_qty(row_name, value) {
		const row = (this.frm.doc.gate_pass_table || []).find((it) => it.name === row_name);
		if (!row) return;
		if (value <= 0) {
			frappe.msgprint(__("Quantity must be greater than zero."));
			return;
		}
		const allocatedOther = (this.frm.doc.gate_pass_table || [])
			.filter((it) => it.order_item_name === row.order_item_name && it.name !== row_name)
			.reduce((sum, it) => sum + flt(it.received_qty), 0);
		const ordered = flt(row.ordered_qty);
		if (ordered > 0 && allocatedOther + value > ordered) {
			frappe.msgprint({
				title: __("Over Receipt"),
				message: __("Total received for {0} ({1}) exceeds ordered ({2}).", [
					row.item_code,
					allocatedOther + value,
					ordered,
				]),
				indicator: "orange",
			});
		}
		row.received_qty = value;
		row.amount = value * flt(row.rate);
		this.frm.dirty();
	}

	remove_invoice_item(row_name) {
		this.frm.doc.gate_pass_table = (this.frm.doc.gate_pass_table || []).filter(
			(it) => it.name !== row_name
		);
		this.frm.refresh_field("gate_pass_table");
		this.frm.dirty();
		this.render();
	}
```

Add a `flt` shim near the top of the class file if not already global:

```javascript
const flt = (v) => parseFloat(v || 0) || 0;
```

- [ ] **Step 4: Manual verification in the browser**

Run: `bench --site gate.localhost clear-cache`, reload a draft Purchase Order Gate Pass.
- Add two invoices, add different items/quantities under each, save. Confirm `gate_pass_invoices` has 2 rows and `gate_pass_table` rows carry the right `supplier_delivery_note`.
- Submit. Confirm two draft Purchase Receipts are created (background job; check the Gate Pass invoices table after the realtime toast / refresh).

- [ ] **Step 5: Commit**

```bash
git add gate_entry/public/js/gate_pass_custom_ui.js
git commit -m "feat: invoice-grouped item entry UI for PO gate passes (#17)"
```

---

## Task 10: Reports & document links

**Files:**
- Modify: `gate_entry/gate_entry/report/pending_gate_passes/pending_gate_passes.py:239`
- Modify: `gate_entry/hooks.py:222-224`

**Interfaces:**
- Produces: the pending report no longer references the removed `gp.purchase_receipt`; the Purchase Receipt → Gate Pass connection uses the PR's own `gate_pass` field.

> `material_reconciliation.py` needs **no** change — its `get_purchase_receipt_totals` reads `tabPurchase Receipt` / `tabPurchase Receipt Item` directly and never touches `Gate Pass.purchase_receipt`. (Verified by reading the function.)

- [ ] **Step 1: Fix `pending_gate_passes.py`**

The condition at line 239 reads `"ifnull(gp.purchase_receipt, '') = ''"` (gate passes with no PR yet) and sits next to line 240's `"ifnull(gp.subcontracting_receipt, '') = ''"`. **Keep line 240 unchanged** (subcontracting still uses that field). Replace **only** line 239 with a NOT-EXISTS against the invoices table so "pending" means "has an invoice without a PR, or no invoices yet":

```python
		"""not exists (
			select 1 from `tabGate Pass Invoice` gpi
			where gpi.parent = gp.name and ifnull(gpi.purchase_receipt, '') != ''
		)""",
```

- [ ] **Step 2: Fix the document link in `hooks.py`**

Replace the Purchase Receipt entry in `document_links` (lines 222-224) so the back-link uses the PR's `gate_pass` field rather than the removed `Gate Pass.purchase_receipt`:

```python
	"Purchase Receipt": [
		{"link_doctype": "Gate Pass", "link_fieldname": "gate_pass"},
	],
```

(Frappe resolves this by matching `Purchase Receipt.gate_pass == Gate Pass.name`, which the existing PR custom field already provides.)

- [ ] **Step 3: Verify the report loads**

Open the **Pending Gate Passes** report in the desk with a date filter and confirm no SQL error (the `gp.purchase_receipt` column no longer exists, so the old condition would have errored). Also open **Material Reconciliation** to confirm it still runs unchanged.

- [ ] **Step 4: Commit**

```bash
git add gate_entry/gate_entry/report/ gate_entry/hooks.py
git commit -m "fix: pending report + document link use invoices table, not retired field (#17)"
```

---

## Task 11: Docs & changelog

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `USER_GUIDE.md`

- [ ] **Step 1: Document the new flow**

In `README.md` add a "Multiple Invoices per Gate Pass" subsection under the Purchase Order flow: one Gate Entry per vehicle, multiple supplier invoices against one PO, one auto-created draft Purchase Receipt per invoice on submit, guard notified on completion.

In `USER_GUIDE.md` add the SOP from spec §3. In `CHANGELOG.md` add an entry under the next version describing the feature and the migration. Update the README compatibility statement (currently "compatible with ERPNext v15.x") to state support for **both v15 and v16**.

- [ ] **Step 2: Commit**

```bash
git add README.md CHANGELOG.md USER_GUIDE.md
git commit -m "docs: multi-invoice gate pass → multiple GRNs (#17)"
```

---

## Final verification

- [ ] **Run the full app test suite**

Run: `bench --site gate.localhost run-tests --app gate_entry`
Expected: all tests pass, including the new `TestPurchaseInvoiceValidation`, `TestAutoGRN`, `TestCancelBehavior`, and no regressions in the Stock Entry / Subcontracting / outbound suites.

- [ ] **Lint**

Run: `pre-commit run --files $(git diff --name-only develop...HEAD)`
Expected: ruff / eslint / prettier clean.

- [ ] **Manual end-to-end** (one PO, one vehicle, three invoices): create gate pass → add 3 invoices with distinct items/qty → submit → confirm 3 draft Purchase Receipts, each with the correct `supplier_delivery_note`, correct quantities, and linked back into the invoices table with `grn_status = Draft`; confirm the timeline comment + notification.
