# Changelog

All notable changes to the Gate Entry module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Multiple Invoices per Gate Pass (#17)
- **`Gate Pass Invoice` child table** — one row per supplier invoice on a gate entry (fields: `supplier_delivery_note`, `invoice_date`, `purchase_receipt` (read-only, set on GRN creation), `grn_status`).
- **Per-invoice item tagging** — `Gate Pass Table` gains a `supplier_delivery_note` column linking each item row to its invoice; the same PO item may appear under multiple invoices with different quantities.
- **Invoice-grouped custom UI** (Purchase Order flow only) — guard clicks "Add Invoice", enters an invoice number, then "Add Item" within that section. Pending-qty display accounts for quantities already allocated to sibling invoices on the same gate pass. Duplicate invoice numbers within a gate pass are rejected.
- **"Create Purchase Receipt" bulk action** — on a submitted PO Gate Pass, a stores/downstream user clicks **"Create Purchase Receipt"** to create one draft Purchase Receipt per invoice in a single, all-or-nothing synchronous action. Each PR carries the invoice number (`supplier_delivery_note`), `gate_pass` link, and vehicle/driver details. If any invoice fails, the entire operation is rolled back and a clear error names the failing invoice; no partial batches are created. A timeline comment is added to the Gate Pass on success.
- **Traceability table** — the submitted Gate Pass displays a `[Invoice No → Purchase Receipt → status]` summary for every GRN produced from that vehicle entry.
- **ERPNext v15 and v16 compatibility** verified and tested.

### Changed
- **GRN creation is now stores-triggered, not automatic**: Purchase Receipts for PO gate entries are no longer created by a background job on Gate Pass submit. Instead, a stores or downstream user opens the submitted Gate Pass and clicks **"Create Purchase Receipt"**, which creates all per-invoice draft Purchase Receipts at once (all-or-nothing). The guard is not notified and does not interact with Purchase Receipts.
- **`pending_gate_passes` report** updated to detect awaiting-receipt gate passes via a NOT-EXISTS check against `Gate Pass Invoice` (replacing the retired `gp.purchase_receipt` column reference).
- **`hooks.py` `document_links`** updated so the Purchase Receipt → Gate Pass backlink uses the PR's own `gate_pass` field.
- Header `supplier_delivery_note` field visibility on Gate Pass changed to `depends_on: eval:doc.document_reference != 'Purchase Order'` (still used by Subcontracting flow; hidden for PO flow where invoice numbers now live on `Gate Pass Invoice`).
- Cancel and amend guards updated to be list-aware (check all linked Purchase Receipts from `Gate Pass Invoice`, not a single header field).

### Removed
- **Header `purchase_receipt` field** (Link, PO-only) on Gate Pass: superseded by `Gate Pass Invoice.purchase_receipt`. The column is dropped after data migration.

### Migration
- Patch `gate_entry.patches.migrate_gate_pass_invoices`: for each existing PO-flow Gate Pass with a non-empty `purchase_receipt` or `supplier_delivery_note` header value, one `Gate Pass Invoice` row is created from those values (with derived `grn_status`); all `Gate Pass Table` rows are tagged with that invoice's `supplier_delivery_note`; the header `supplier_delivery_note` is cleared on the PO doc; and the orphan `purchase_receipt` column is dropped.

### Deprecated

### Fixed

### Security

---

## [1.0.1] - 2025-12-21

### Added

#### Core Gate Pass Module
- **Gate Pass DocType** with comprehensive material movement tracking
  - Auto-generated gate pass IDs with fiscal year naming series (GP-2025-26/00001)
  - Entry Type support (Gate In, Gate Out)
  - Document reference system supporting multiple source document types
  - Vehicle and driver information capture
  - Security guard tracking with auto-populated user information
  - Gate entry date and time tracking
  - Status lifecycle management (Draft, Submitted, Receipt Created, Cancelled)
  - Custom HTML-based item management UI with todo-list style interface
  - Color-coded item status indicators (red for pending, green for fully received)
  - Item-level discrepancy logging (lost/damaged quantities)
  - Multi-pass allocation support for partial dispatches

#### Purchase Order & Subcontracting Order Integration
- **Inbound Material Tracking** for Purchase Orders
  - Auto-fetch items from Purchase Orders with ordered quantities
  - Pending quantity calculation (ordered - already received)
  - Support for partial deliveries across multiple gate passes
  - Rate Contract support with relaxed quantity validation
  - Auto-population of supplier and supplier address from Purchase Order
  - Seamless conversion to Purchase Receipt with item-level mapping
  - Custom field linking Purchase Receipt to source Gate Pass

- **Subcontracting Order Integration**
  - Full support for subcontracting material movements
  - Auto-fetch items from Subcontracting Orders
  - Conversion to Subcontracting Receipt with complete data mapping
  - Custom field linking Subcontracting Receipt to source Gate Pass
  - Support for both raw material dispatch and finished goods receipt

#### Sales Document Integration (Gate Out)
- **Sales Invoice & Delivery Note Support**
  - Outbound gate pass creation from Sales Invoices
  - Outbound gate pass creation from Delivery Notes
  - Auto-population of vehicle number, driver name, and driver contact from sales documents
  - Read-only dispatched quantities to maintain data integrity
  - Auto-populated dispatch date and time
  - Compliance validation for e-invoice and e-way bill requirements
  - Hard-block submission when required compliance documents are missing (based on GST Settings threshold)
  - Integration with ERPNext GST Settings for e-waybill threshold validation

#### Stock Entry Integration
- **Material Transfer Support**
  - Automatic gate pass creation for Material Transfer Stock Entries
  - External Transfer checkbox on Stock Entry for gate documentation
  - Background job processing for non-blocking gate pass creation
  - Support for both outbound and inbound material transfers
  - Return material transfer handling with outbound reference linking
  - Manual gate pass creation with Stock Entry linking
  - Custom fields on Stock Entry: `ge_external_transfer`, `ge_gate_pass_instruction`, `gate_pass`

- **Send to Subcontractor Support**
  - Automatic gate pass creation for subcontracting Stock Entries
  - Complete integration with subcontracting workflow
  - Material tracking for subcontractor dispatches and receipts

- **Multi-Pass Allocation System**
  - Multiple gate passes per Stock Entry for partial dispatches
  - Quantity allocation validation preventing over-allocation
  - Database-level locking (SELECT FOR UPDATE) for concurrent scenarios
  - Remaining quantity calculations per item
  - Allocation tracking across all linked gate passes

- **Discrepancy Management**
  - Lost quantity logging at gate level
  - Damaged quantity tracking
  - Discrepancy validation ensuring quantities don't exceed movement quantities
  - Automatic field clearing when discrepancy flag is unchecked

- **Cancellation Handling**
  - Independent gate pass cancellation without affecting Stock Entry
  - Automatic reference cleanup when Stock Entry is cancelled
  - Auto-cancellation of gate passes when source Stock Entry is cancelled
  - Quantity reservation release on cancellation

#### Reports & Analytics
- **Pending Gate Passes Report**
  - Track all submitted gate passes awaiting receipt creation
  - Aging calculation (days since submission)
  - Color-coded aging indicators (green < 1 day, yellow 1-2 days, red > 2 days)
  - Filtering by date range, supplier, company, document type
  - Stock Entry integration with type, warehouse, and posting date display
  - Item-level details for each pending gate pass
  - Support for both inbound and outbound gate passes

- **Gate Register Report**
  - Daily log of all gate pass activities
  - Comprehensive material movement tracking
  - Vehicle and driver information display
  - Material summary with item-level details
  - Filtering by date range, entry type, supplier, vehicle number
  - Stock Entry metadata display (type, warehouses, posting dates)
  - Return material transfer tracking with outbound reference
  - Excel and PDF export functionality

- **Material Reconciliation Report**
  - Comparison between gate pass quantities and receipt quantities
  - Discrepancy highlighting for review
  - Document-wise summary (Purchase Order, Subcontracting Order, Sales Invoice, Delivery Note, Stock Entry)
  - Stock Entry allocated quantity calculation (sum of gate pass quantities)
  - Item-level reconciliation with detailed breakdown
  - Warehouse information display
  - Filtering by date range, document type, supplier, stock entry type
  - Support for return material transfer reconciliation

#### User Interface & Experience
- **Custom HTML Item Management UI**
  - Modern todo-list style interface for gate pass items
  - Add/remove items with +/- icons
  - Info icon (i) for detailed item information (UOM, Ordered Qty, Pending Qty, Description)
  - Real-time quantity validation
  - Mobile-responsive design for tablet/phone usage at gates
  - Color-coded status indicators
  - Seamless integration with child table for backend processing

- **Form Enhancements**
  - Auto-population of supplier and address from reference documents
  - Dynamic "Get Items" button based on reference selection
  - Context-aware receipt creation buttons (Purchase Receipt vs Subcontracting Receipt)
  - Compliance warning display for outbound dispatches
  - Status-based button visibility and enabling/disabling
  - Auto-refresh after receipt creation

#### Permissions & Security
- **Role-Based Access Control**
  - Gate User role: Create, Read, Submit gate passes
  - Store Manager role: Full gate pass management + receipt creation
  - Purchase User role: Read-only access
  - System Manager: Full administrative access
  - Security Guard role with hardened permissions (read-only access to Sales Invoice, Delivery Note, GST Settings)
  - Company-based data isolation

#### Technical Infrastructure
- **Document Event Hooks**
  - Stock Entry `on_submit` event for automatic gate pass creation
  - Stock Entry `on_cancel` event for reference cleanup
  - Stock Entry `on_trash` event for complete cleanup
  - Purchase Receipt and Subcontracting Receipt event handlers
  - Automatic reference management on document lifecycle events


### Changed
- Gate Pass DocType structure enhanced with new fields and validations
- Report queries updated to support Stock Entry integration
- Custom field system for seamless ERPNext integration
- Form layouts optimized for security guard workflow

### Technical Details
- Database-level locking (SELECT FOR UPDATE) for allocation validation
- Automatic reference cleanup on document cancellation
- ERPNext v15 compatibility verified and tested
- Python 3.10+ support

---

## [0.0.1] - Development Version

Initial development version (pre-release)

[Unreleased]: https://github.com/Guru107/gate-entry/compare/v1.0.0...develop
[1.0.0]: https://github.com/Guru107/gate-entry/releases/tag/v1.0.0

