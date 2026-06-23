### Gate Entry
An erpnext security gate module for recording material and people movement

Demo Video: https://drive.google.com/file/d/1mzmrLoa4C1H7ZSi5jn5PSRyO7kTLzZwh/view?usp=drive_link

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

### Prerequisites
  - ERPNext Installed
  - India Compliance Installed

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app gate_entry
```

### Configuration

- Assign the auto-created `Security Guard` role to guard users. The setup hooks harden this role with read-only access to `Sales Invoice`, `Delivery Note`, and `GST Settings`, while keeping Desk access disabled.
- Ensure outbound sales documents capture transport details: add or expose `vehicle_number`, `driver_name`, and `driver_contact` fields on `Sales Invoice` and `Delivery Note` so the gate pass can auto-populate them.
- Review `GST Settings` and configure `e_waybill_threshold` (and `enable_e_waybill_from_dn` if Delivery Notes should be blocked) to align compliance checks with your statutory requirements.
- Keep guard users on the streamlined Gate Pass form; they should not require additional financial roles or report permissions.

### Stock Entry Integration

The Gate Entry app integrates seamlessly with ERPNext Stock Entry to automate gate pass creation for material transfers that leave the plant.

#### Features

1. **Auto-Creation of Gate Passes**
   - When a Stock Entry with `stock_entry_type = "Material Transfer"` is submitted with the `External Transfer` checkbox enabled, a draft Gate Pass is automatically created
   - The Gate Pass is created in the background via an enqueued job to avoid blocking Stock Entry submission
   - Gate Passes are also auto-created for `Send to Subcontractor` Stock Entries

2. **External Transfer Checkbox**
   - A custom field `ge_external_transfer` is added to Stock Entry
   - Visible only when `stock_entry_type == "Material Transfer"`
   - When checked, indicates that the material transfer leaves the plant and requires gate documentation
   - Optional `ge_gate_pass_instruction` field allows stores teams to pass notes to security

3. **Return Material Transfers**
   - Return Stock Entries (`is_return = 1`) automatically create inbound Gate Passes (Gate In)
   - The Gate Pass correctly links to the original outbound transfer via `outbound_material_transfer` field
   - Manual return flow: Gate Passes can be created before the return Stock Entry exists, referencing the outbound transfer directly

4. **Multi-Pass Allocations**
   - Multiple Gate Passes can be created for the same Stock Entry to handle partial dispatches
   - Allocation validation ensures total quantities across all Gate Passes do not exceed Stock Entry quantities
   - Database-level locking prevents race conditions when multiple Gate Passes are validated simultaneously

5. **Discrepancy Logging**
   - Gate Passes support recording material discrepancies (lost, damaged quantities)
   - Validation ensures discrepancy quantities do not exceed movement quantities
   - Discrepancy fields are automatically cleared when `has_discrepancy` is unchecked

6. **Cancellation Handling**
   - When a Stock Entry is cancelled, all linked Gate Pass references are automatically cleared
   - Auto-created Gate Passes are cancelled when their source Stock Entry is cancelled
   - Gate Passes can be cancelled independently, clearing the `gate_pass` reference from Stock Entry

#### Workflow Examples

**Outbound Transfer:**
1. Create Stock Entry with `stock_entry_type = "Material Transfer"`
2. Check `External Transfer` checkbox
3. Submit Stock Entry
4. Gate Pass is auto-created in draft status (Gate Out)
5. Security guard reviews and submits Gate Pass

**Return Transfer:**
1. Create return Stock Entry (`is_return = 1`) referencing original outbound transfer
2. Submit return Stock Entry
3. Gate Pass is auto-created in draft status (Gate In)
4. Gate Pass automatically links to original outbound transfer
5. Security guard reviews and submits Gate Pass

**Manual Return Flow:**
1. Create Gate Pass manually with `manual_return_flow = 1`
2. Reference the outbound Stock Entry in `outbound_material_transfer`
3. Submit Gate Pass
4. Later, create return Stock Entry and link it to the Gate Pass

#### Custom Fields Added

The app adds the following custom fields to Stock Entry (all removed on uninstall):

- `ge_external_transfer` (Check): Flags external transfers requiring gate documentation
- `ge_gate_pass_instruction` (Small Text): Optional notes for security team
- `gate_pass` (Link): Links to the Gate Pass created for this Stock Entry

#### Technical Details

- **Event Handlers**: Stock Entry `on_submit`, `on_cancel`, and `on_trash` events are hooked
- **Background Jobs**: Gate Pass creation runs in background queue to avoid blocking Stock Entry submission
- **Database Locking**: Uses `SELECT FOR UPDATE` to prevent over-allocation in concurrent scenarios
- **Reference Management**: Automatic cleanup of references when Stock Entries or Gate Passes are cancelled/deleted

For detailed installation and uninstallation instructions, see [INSTALLATION.md](INSTALLATION.md).

### Purchase Order Flow: Multiple Invoices per Gate Pass

A single supplier vehicle often arrives carrying material split across several supplier invoices (delivery challans) — all against one Purchase Order. The Gate Entry module supports this with one Gate Entry per vehicle:

- **One Gate Pass per vehicle** — the gate pass is still tied to a single Purchase Order and a single supplier.
- **Multiple supplier invoices** — the guard adds each invoice the driver presents as a separate invoice section, then records the items and quantities for that invoice within it.
- **One auto-created draft Purchase Receipt per invoice** — on Gate Pass submission the system automatically creates one draft Purchase Receipt for each invoice in the background. The guard is notified when all GRNs have been generated.
- **Guard never touches Purchase Receipts** — the guard's job ends at submission. The draft Purchase Receipts are visible to stores / accounts for verification and final submission.

The Gate Pass form displays a traceability table of every `[Invoice No → Purchase Receipt → status]` produced from that vehicle entry.

### Releases

This module follows [Semantic Versioning](https://semver.org/) and is compatible with ERPNext v15.x and v16.x.

**Current Version:** 1.0.0

For release information and version history, see [CHANGELOG.md](CHANGELOG.md).

To create a new release, follow the process outlined in [RELEASE.md](RELEASE.md) or use the quick reference guide in [scripts/QUICK_RELEASE.md](scripts/QUICK_RELEASE.md).

**Quick release command:**
```bash
./scripts/release.sh <version>
# Example: ./scripts/release.sh 1.0.0
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/gate_entry
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
