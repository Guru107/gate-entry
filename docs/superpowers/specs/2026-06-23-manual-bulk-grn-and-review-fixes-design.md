# Manual Bulk GRN Creation + Review Fixes

**Issue:** [#17](https://github.com/Guru107/gate_entry/issues/17) · **Amends:** PR [#18](https://github.com/Guru107/gate_entry/pull/18) and its spec `2026-06-23-multi-invoice-gate-pass-grn-design.md`
**Date:** 2026-06-23
**Status:** Design approved — pending implementation plan

---

## 1. Why this change

PR #18 auto-creates one draft Purchase Receipt per invoice in a **background job on Gate Pass submit**. A fresh code review found two production risks in that approach:

1. The background worker's permission/user context is unreliable — if the job doesn't run as a user with Purchase Receipt create permission, every PR silently fails (logged + a "failed" notice), and the guard has no recourse.
2. The asynchronous job hides failures from the person who could act on them.

This change replaces the auto-on-submit job with an **explicit, synchronous "Create Purchase Receipt" action triggered by a stores/downstream user**, and folds in the review's remaining fixes. The guard's responsibilities are unchanged (enter invoices + items, submit); PR creation moves to a permitted downstream user with immediate feedback.

---

## 2. Roles & flow

| Actor | Responsibility |
|---|---|
| **Security guard** | Creates the Gate Pass, records each invoice + its items (invoice-grouped UI — **unchanged**), submits. Never needs Purchase Receipt permission. |
| **Stores / downstream user** (has PR create permission) | Opens the submitted Gate Pass, clicks **"Create Purchase Receipt"** → **all** per-invoice draft PRs are created in one synchronous action, with immediate success/error feedback. Later submits those draft PRs (which advances `grn_status` to Submitted). |

---

## 3. PR creation — synchronous, all-or-nothing

Replace the background job (`generate_purchase_receipts` + `on_submit` enqueue + `_notify_grn_generation` realtime) with a whitelisted **synchronous** endpoint:

```
create_purchase_receipts(gate_pass_name) -> {"created": [pr_name, ...], "skipped": [invoice_no, ...]}
```

Behavior:
- **Permission:** `frappe.has_permission("Purchase Receipt", "create")` — throw if absent. The endpoint runs as the clicking (stores) user, so PR creation respects real permissions. *(This structurally resolves review finding #2 — no `ignore_permissions`, no worker-identity dependence.)*
- **Guards:** require `gate_pass.docstatus == 1` and `document_reference == "Purchase Order"`.
- **Scope:** process only invoice rows **without** a `purchase_receipt` yet (idempotent against re-entry / edge states). If none remain, return a "all GRNs already created" message and create nothing.
- **All-or-nothing:** build one draft PR per pending invoice (reusing the existing `_build_purchase_receipt`, which does `pr.insert()` → **draft**), then link each back (`purchase_receipt` + `grn_status="Draft"`). If **any** invoice fails, `frappe.db.rollback()` and `frappe.throw` a clear message naming the failing invoice and error — leaving **no** partially-created receipts. (Confirmed requirement: partial batches could let some invoices be silently missed.)
- **Audit:** on success, add a brief timeline comment to the Gate Pass: *"Created Purchase Receipts: PR-x, PR-y (by <user>)."*
- Returns the created PR names so the UI can link/redirect.

PRs are **drafts**; stores submits them downstream. `grn_status` lifecycle is unchanged: `Pending → Draft` (on create) `→ Submitted` (via `on_purchase_receipt_submit`); reset to `Pending` on PR cancel/trash.

### Removed
- `Gate Pass.on_submit` no longer enqueues anything for the PO flow.
- `generate_purchase_receipts` (background job) and `_notify_grn_generation` (realtime `publish_realtime` + its "No Purchase Receipts were generated." path) are removed; their logic is superseded by the synchronous endpoint + its return value/msgprint.

---

## 4. UI — re-add the button

On a **submitted** Purchase Order Gate Pass, `gate_pass.js` shows a **"Create Purchase Receipt"** button (primary) that calls `create_purchase_receipts`, then `frappe.msgprint`s the created PR names (as links) or surfaces the thrown error. The button is **hidden once every invoice row already has a `purchase_receipt`**; each invoice row offers a "View" link to its PR. The guard-facing invoice-grouped entry UI (`gate_pass_custom_ui.js`) is unchanged.

*(Note: this re-introduces a PO-flow receipt button that PR #18's Task 8 removed — but as a bulk, all-or-nothing, permission-checked action, not the old single-PR button.)*

---

## 5. Unchanged from PR #18
`Gate Pass Invoice` child table + item `supplier_delivery_note` tagging; the invoice-grouped entry UI; `validate_purchase_invoices`; the `grn_status` lifecycle + `on_purchase_receipt_submit` / `_clear_invoice_row_for_pr` (cancel/trash) handlers; list-aware cancel/amend (block while a linked PR is submitted; delete draft PRs on cancel); the `pending_gate_passes` report fix and the `document_links` fix.

---

## 6. Review fixes folded in

- **🔴 Migration (`migrate_single_pr_to_invoices`):** legacy gate passes with a `purchase_receipt` are **submitted** (`docstatus 1`); the current `gate_pass.save()` to append the invoice row + retag items raises `UpdateAfterSubmitError`. Set `gate_pass.flags.ignore_validate_update_after_submit = True` before `save()` (keep `ignore_validate`/`ignore_links`). Add a patch test that migrates a **submitted** legacy gate pass and asserts the invoice row + item tags + dropped column.
- **🔴 Permissions:** resolved by §3 (synchronous, permission-checked, runs as the stores user).
- **🟡 Validation message wording:** `validate_purchase_invoices` runs in `validate()` (every save), so its "…before submitting." text is misleading — reword to "…before saving." (Behavior unchanged; the old code also required items to save.)
- **🟡 Over-allocation:** left to ERPNext's native over-receipt tolerance at PR submit; the entry UI still warns. Not hard-gated at the gate. (Documented decision, unchanged.)
- **🟡 Item-PO-ownership & cross-pass invoice uniqueness:** left as-is (self-defending via `get_doc("Purchase Order Item")`; per-pass uniqueness sufficient). Not enforced.

---

## 7. Testing (v15 + v16)
- `create_purchase_receipts`: happy path (N invoices → N draft PRs, linked, `grn_status="Draft"`); **all-or-nothing** (force one invoice to fail → assert `frappe.db` has **zero** new PRs and the gate pass invoice rows still have no `purchase_receipt`); idempotent re-call when all PRs exist (no-op); **permission denied** for a user without PR create permission.
- Migration: migrate a **submitted** legacy gate pass successfully (the previously-untested branch).
- Remove/replace the obsolete background-job test; keep cancel-blocked / draft-deletion / `grn_status→Submitted` tests.
- All green on Frappe/ERPNext v15 (15.102.1) and v16 (16.13.0).

---

## 8. Migration note (still owed before release)
Dry-run the data migration against a production DB snapshot containing a submitted legacy PO gate pass before the release that ships the `purchase_receipt` column drop.
