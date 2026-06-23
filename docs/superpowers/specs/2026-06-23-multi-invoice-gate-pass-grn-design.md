# Multi-Invoice Gate Entry → Auto-Generated GRNs

**Issue:** [#17](https://github.com/Guru107/gate_entry/issues/17)
**Date:** 2026-06-23
**Status:** Design approved — pending implementation plan

---

## 1. Problem & scope

A supplier vehicle arrives with material for **a single Purchase Order**, split across **several supplier invoices** (delivery challans). Today a Gate Pass is locked to a single invoice (`supplier_delivery_note`) and a single Purchase Receipt (single `purchase_receipt` field + a hard guard blocking a second PR), so one physical vehicle entry with three invoices forces the guard to create three separate Gate Passes — breaking the "one vehicle entry = one gate record" traceability.

This feature lets **one Gate Entry hold N invoices for one PO**, and the **system auto-creates one Purchase Receipt (GRN) per invoice** when the Gate Entry is submitted.

### In scope
- **Purchase Order → Purchase Receipt** flow only.

### Out of scope (explicit)
- Subcontracting Order → Subcontracting Receipt, Sales Invoice, Delivery Note, and Stock Entry flows — untouched.
- **Multiple POs** in one vehicle entry — each Gate Entry is still one PO.
- **Multiple suppliers** in one vehicle entry — still one supplier.
- Any downstream **quality-inspection / pending-inspection-qty / batched-acceptance** tracking. The gate module is the security cabin; it records what physically arrived (invoices + their items against a PO). Partial-inspection lifecycle belongs to ERPNext-native PO→PR partial receipts + Quality Inspection. (See the original issue discussion: the inspection-tracking framing was deliberately rejected.)

---

## 2. Roles & responsibilities

| Actor | Responsibility |
|---|---|
| **Security guard** | Creates the Gate Entry: PO, vehicle, driver, and **each invoice the driver presents** (invoice number + that invoice's items + quantities). Submits. Never interacts with a Purchase Receipt. |
| **System** | On Gate Entry submit, auto-creates **one draft Purchase Receipt per invoice** in the background, stamps the invoice number on each, and links it back to the Gate Entry. |
| **Stores / Accounts** (downstream, out of this module) | Verify and submit the draft Purchase Receipts; perform inspection. |

---

## 3. Standard operating procedure

**Phase 1 — Vehicle arrives (open the gate entry)**
1. Guard creates a new Gate Pass; sets Document Reference = **Purchase Order** and picks the PO → supplier/company/address auto-fill.
2. Enters **vehicle number, driver name, driver contact**.

**Phase 2 — Record each invoice**
3. For each invoice the driver presents, the guard adds an **invoice** (invoice number) and, under it, **adds the items on that invoice** (from the PO's items) with their **quantities (> 0)**.

**Phase 3 — Submit**
4. Guard **submits** the Gate Entry.
5. The system creates **one draft Purchase Receipt per invoice** in the background and populates the invoice→PR mapping on the Gate Entry.
6. The Gate Entry displays the PO, vehicle, and a table of **[Invoice No → Purchase Receipt → status]** — full traceability of every GRN from this one vehicle entry.

---

## 4. Data model

The Gate Pass header keeps its single PO (`document_reference` / `reference_number`), supplier, company, vehicle, and driver fields — **unchanged**.

### 4.1 New child table: `Gate Pass Invoice`
One row per supplier invoice on this gate entry.

| Field | Type | Notes |
|---|---|---|
| `supplier_delivery_note` | Data, reqd | Invoice number. **Unique within the gate pass.** |
| `invoice_date` | Date | Optional. |
| `purchase_receipt` | Link → Purchase Receipt, read-only, `no_copy` | Set by the automation after the PR is created. |
| `grn_status` | Data/Select, read-only | Reflects the PR docstatus (Not Created / Draft / Submitted / Cancelled). |

### 4.2 Existing child table: `Gate Pass Table` (items) — extended
- **Add** `supplier_delivery_note` (Data) — tags each item line to the invoice it belongs to (matches a `Gate Pass Invoice.supplier_delivery_note`).
- The **same PO item may appear under two invoices** with different quantities → multiple rows, distinct by invoice tag.
- Existing fields (`order_item_name` → PO Item, `received_qty`, `warehouse`, `rate`, …) keep their meaning, now scoped per invoice line.

### 4.3 Retired fields (migrated, then removed)
- Header `supplier_delivery_note` (Data) — superseded by `Gate Pass Invoice.supplier_delivery_note`.
- Header `purchase_receipt` (Link) — superseded by `Gate Pass Invoice.purchase_receipt`.

### 4.4 Grouping key
`supplier_delivery_note` (the invoice number) is the join key between an invoice row and its tagged item rows. Uniqueness of the invoice number within the gate pass is enforced so the mapping is unambiguous.

---

## 5. Guard UI (custom UI rework — PO flow only)

The on-form item area (`custom_ui` HTML field, rendered by `GatePassCustomUI` in `gate_pass_custom_ui.js`) becomes **invoice-grouped** for the Purchase Order flow:

- **"Add Invoice"** → guard enters an invoice number → a collapsible **invoice section** appears (heading = invoice number; rejects duplicate numbers).
- Within a section, **"Add Item"** reuses the existing item-selector dialog (`show_item_selector_dialog`, backed by `get_items` → `get_purchase_order_items`): a checkbox list of the PO's items showing **remaining pending qty**, filtering out items already added **to that invoice**.
- Each added item gets a qty input; entered qty must be **> 0**.
- **Pending qty** shown per item = `ordered − received-on-PO (submitted PRs) − qty already allocated in sibling invoices on this gate pass`, preventing over-allocation across the gate entry's own invoices.
- Items are synced to `Gate Pass Table` with their `supplier_delivery_note` tag; invoice headers sync to `Gate Pass Invoice`.

**Non-PO inbound flows (Subcontracting, Stock Entry return) keep today's flat item UI unchanged.** The grouped behavior is gated on `document_reference === "Purchase Order"`.

The old manual **"Create Purchase Receipt" / "View Purchase Receipt"** buttons and the `create_purchase_receipt` confirm dialog in `gate_pass.js` are **removed** for the PO flow.

---

## 6. Automation — auto-create GRNs on submit

Mirrors the existing precedent `on_stock_entry_submit` → `frappe.enqueue(create_gate_pass_from_stock_entry, …)`, which deliberately runs in the background "to avoid blocking submission."

On `Gate Pass.on_submit` (PO flow):
1. Enqueue a background job (`frappe.enqueue`, `queue="long"`, `now=frappe.flags.in_test`).
2. The job iterates `Gate Pass Invoice` rows. For each, gathers the item rows tagged with that invoice's `supplier_delivery_note` and builds **one draft Purchase Receipt**:
   - Reuses the existing PR header + per-item field mapping from `create_purchase_receipt` ([gate_pass.py:1508](../../../gate_entry/gate_entry/doctype/gate_pass/gate_pass.py)) — refactored into an internal helper `_build_purchase_receipt(gate_pass, invoice_row, item_rows)`.
   - Sets `pr.supplier_delivery_note = invoice_row.supplier_delivery_note`, `pr.gate_pass = gate_pass.name`, vehicle/driver from the gate pass.
   - `pr.insert()` (**draft** — not submitted).
   - Writes `invoice_row.purchase_receipt = pr.name` and `grn_status = "Draft"` back via `db_set` (no re-validation of the submitted gate pass).
3. A failure on one invoice's PR is logged (`frappe.log_error`) and does **not** roll back the Gate Entry or the other invoices' PRs — the guard's gate entry stands; stores resolves the flagged PR.
4. **On completion, the guard is notified.** A realtime/desk notification (and a timeline comment on the Gate Entry) tells the guard the GRNs were generated, listing the created Purchase Receipts (and flagging any invoice whose PR failed). This is the only PR-related feedback the guard sees — they still never *act* on a PR.

The whitelisted `create_purchase_receipt` endpoint is removed (or reduced to the internal helper); nothing in the UI calls it anymore.

---

## 7. Validation (before submit, PO flow)

- At least **one invoice** row.
- Each invoice has **≥ 1 tagged item**.
- Each item qty **> 0**.
- **Invoice numbers unique** within the gate pass.
- Every tagged item's `order_item_name` belongs to the gate pass's PO.
- Cumulative qty per PO item across all invoices (+ already received on the PO from other documents) **≤ ordered qty**, respecting ERPNext's native over-receipt tolerance.

The current PO-flow requirement to enter `received_qty` directly on a flat `gate_pass_table` is replaced by the per-invoice item validation above.

---

## 8. Cancel / amend

- **Cancel Gate Entry:** blocked while **any** linked Purchase Receipt is **submitted** (list-aware version of today's `check_linked_receipts_before_cancel`). Draft PRs created by the automation are **cancelled/deleted** as part of (or before) the gate pass cancellation, and invoice rows' `purchase_receipt` links cleared.
- **Amend Gate Entry:** blocked while any linked PR is submitted (list-aware `check_receipts_in_amended_document`).
- **PR cancel/trash handlers** (`on_purchase_receipt_cancel` / `_trash`): clear the matching `Gate Pass Invoice` row's `purchase_receipt` + reset `grn_status`, instead of clearing a single header field.

---

## 9. Migration

Patch for existing gate passes that used the single fields:
- For each Gate Pass with a non-empty header `purchase_receipt` (or `supplier_delivery_note`): create **one** `Gate Pass Invoice` row from the old `supplier_delivery_note` + `purchase_receipt` (+ derived `grn_status`).
- Tag all existing `Gate Pass Table` rows with that invoice's `supplier_delivery_note`.
- Then drop the retired header fields (custom-field/doctype JSON update + patch).

---

## 10. Reports

Audit and update for the new child-table structure (they currently read the retired header fields):
- `gate_register`
- `material_reconciliation`
- `pending_gate_passes`

---

## 11. Testing

- Multi-invoice Gate Entry → N draft PRs auto-created on submit, one per invoice, each carrying the correct `supplier_delivery_note`.
- Item-to-invoice tagging round-trips (UI sync ↔ child tables).
- Validation: duplicate invoice number rejected; qty ≤ 0 rejected; over-allocation across sibling invoices rejected; item not on PO rejected.
- Cancel blocked when a linked PR is submitted; draft PRs cleaned up on cancel.
- PR cancel/trash clears the matching invoice row.
- Migration patch converts a legacy single-PR gate pass correctly.
- Subcontracting / Stock Entry / outbound flows unaffected (regression).

---

## 12. Resolved decisions & remaining planning detail

- **Cancel cleanup (confirmed):** auto-created **draft** PRs are deleted when the Gate Entry is cancelled (drafts can be deleted; submitted PRs block cancel anyway, so no orphan drafts are left behind).
- **Completion notification (confirmed):** the guard receives a notification + Gate Entry timeline comment when the background GRN generation finishes (see §6.4).
- **`grn_status` value set:** `Pending` (invoice recorded, PR not yet generated — i.e. between submit and job completion) → `Draft` (PR created) → `Submitted` → `Cancelled`.
- Remaining detail for planning: exact realtime channel/event for the notification, and copy for the timeline comment.
