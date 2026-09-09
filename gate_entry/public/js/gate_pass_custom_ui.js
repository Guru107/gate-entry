/**
 * Gate Pass Custom UI Component
 *
 * This component provides a todo-list style interface for managing items in a Gate Pass.
 * Features:
 * - Clean, modern UI with Item Code, Item Name, and Received Qty columns
 * - Add/remove items with +/- icons
 * - Info icon showing additional details (UOM, Ordered Qty, Pending Qty, Description)
 * - Color coding: red for pending items, green for fully received
 * - Mobile responsive design
 * - Real-time validation
 * - Syncs with hidden child table (gate_pass_table)
 */

class GatePassCustomUI {
	constructor(frm) {
		this.frm = frm;
		this.items = [];
		this.available_items = [];
		this.wrapper = null;
		this.precision = 3;
		this._resizeHandlerBound = false;
		this.init();
	}

	hasWriteAccess() {
		if (!this.frm || !this.frm.perm || !this.frm.perm.length) {
			return false;
		}
		return !!this.frm.perm[0].write || frappe.perm.has_perm("Gate Pass", 0, "write");
	}

	isGateOut() {
		return (this.frm?.doc?.entry_type || "Gate Out") === "Gate Out";
	}

	isGateIn() {
		return (this.frm?.doc?.entry_type || "Gate Out") === "Gate In";
	}

	isPurchaseOrderFlow() {
		return this.frm?.doc?.document_reference === "Purchase Order" && this.isGateIn();
	}

	isStockEntry() {
		return this.frm?.doc?.document_reference === "Stock Entry";
	}

	shouldAllowQuantityEdit() {
		return (
			this.hasWriteAccess() &&
			this.frm.doc.docstatus === 0 &&
			(this.isGateIn() || (this.isGateOut() && this.isStockEntry()))
		);
	}

	getQuantityField() {
		return this.isGateIn() ? "received_qty" : "dispatched_qty";
	}

	getQuantityLabel() {
		return this.isGateIn() ? __("Received Qty") : __("Dispatched Qty");
	}

	getQuantityValue(item) {
		const field = this.getQuantityField();
		return parseFloat(item[field] || 0);
	}

	/**
	 * Initialize the custom UI component
	 */
	init() {
		if (!this.frm || !this.frm.fields_dict.custom_ui) {
			console.error("Custom UI field not found");
			return;
		}

		this.wrapper = this.frm.fields_dict.custom_ui.$wrapper;
		this.render();
		this.setup_event_listeners();
		this.setup_responsive_listener();
	}

	/**
	 * Load items from the child table with all fields
	 */
	load_items_from_table() {
		this.items = [];

		// Ensure the form and child table exist
		if (!this.frm || !this.frm.doc) {
			console.warn("Gate Pass Custom UI: Form or document not available");
			return this.items;
		}

		// Debug: Check child table state
		console.log("Gate Pass Custom UI: Loading items from child table", {
			has_table: !!this.frm.doc.gate_pass_table,
			table_length: this.frm.doc.gate_pass_table ? this.frm.doc.gate_pass_table.length : 0,
			table_data: this.frm.doc.gate_pass_table,
		});

		// Load items from the child table with all fields
		if (this.frm.doc.gate_pass_table && this.frm.doc.gate_pass_table.length > 0) {
			this.frm.doc.gate_pass_table.forEach((row) => {
				// Only add items that have a valid item_code
				if (row.item_code) {
					const item = {
						// Basic item details
						item_code: row.item_code,
						item_name: row.item_name || "",
						description: row.description || "",
						uom: row.uom || "",
						stock_uom: row.stock_uom || "",
						conversion_factor: row.conversion_factor || 1.0,
						// Quantities
						ordered_qty: row.ordered_qty || 0,
						received_qty: row.received_qty || 0,
						dispatched_qty: row.dispatched_qty || 0,
						pending_qty: row.pending_qty || 0,
						is_rate_contract: row.is_rate_contract || 0,
						// Pricing details
						rate: row.rate || 0,
						amount: row.amount || 0,
						// Warehouse and location
						warehouse: row.warehouse || "",
						rejected_warehouse: row.rejected_warehouse || "",
						// Accounting details
						expense_account: row.expense_account || "",
						cost_center: row.cost_center || "",
						// Reference details
						project: row.project || "",
						schedule_date: row.schedule_date || "",
						// Other details (important for subcontracting and PO linking)
						bom: row.bom || "",
						include_exploded_items: row.include_exploded_items || 0,
						order_item_name: row.order_item_name || "",
						// Index for tracking
						idx: row.idx,
					};

					const quantityField = this.getQuantityField();
					const orderedQty = parseFloat(item.ordered_qty || 0);
					const quantityValue = parseFloat(item[quantityField] || 0);

					if (this.isStockEntry()) {
						item.pending_qty = Math.max(orderedQty - quantityValue, 0);
					} else if (
						item.pending_qty === undefined ||
						item.pending_qty === null ||
						isNaN(parseFloat(item.pending_qty))
					) {
						item.pending_qty = Math.max(orderedQty - quantityValue, 0);
					}

					this.items.push(item);
				} else {
					console.warn("Gate Pass Custom UI: Row missing item_code", row);
				}
			});
		}

		console.log("Gate Pass Custom UI: Loaded items", this.items);

		return this.items;
	}

	/**
	 * Sync items to the hidden child table
	 */
	sync_to_child_table() {
		console.log("Gate Pass Custom UI: Syncing items to child table", this.items);

		// Clear existing rows
		this.frm.clear_table("gate_pass_table");

		// Add items to child table with all fields
		this.items.forEach((item, index) => {
			let row = this.frm.add_child("gate_pass_table");
			// Basic item details
			row.item_code = item.item_code;
			row.item_name = item.item_name;
			row.description = item.description || "";
			row.uom = item.uom || "";
			row.stock_uom = item.stock_uom || "";
			row.conversion_factor = item.conversion_factor || 1.0;
			// Quantities
			row.ordered_qty = item.ordered_qty || 0;
			row.received_qty = item.received_qty || 0;
			row.dispatched_qty = item.dispatched_qty || 0;
			row.pending_qty = item.pending_qty || 0;
			row.is_rate_contract = item.is_rate_contract || 0;
			// Pricing
			row.rate = item.rate || 0;
			const qty_for_amount =
				(this.isOutbound() ? item.dispatched_qty : item.received_qty) || 0;
			row.amount = qty_for_amount * (item.rate || 0);
			// Warehouse
			row.warehouse = item.warehouse || "";
			row.rejected_warehouse = item.rejected_warehouse || "";
			// Accounting
			row.expense_account = item.expense_account || "";
			row.cost_center = item.cost_center || "";
			// Reference
			row.project = item.project || "";
			row.schedule_date = item.schedule_date || "";
			// Other details
			row.bom = item.bom || "";
			row.include_exploded_items = item.include_exploded_items || 0;
			row.order_item_name = item.order_item_name || "";
			row.idx = index + 1;
		});

		// Refresh the child table and mark form as dirty
		this.frm.refresh_field("gate_pass_table");
		this.frm.dirty();

		console.log("Gate Pass Custom UI: Child table synced", this.frm.doc.gate_pass_table);
	}

	/**
	 * Main render method
	 */
	render() {
		// Ensure wrapper exists
		if (!this.wrapper || !this.wrapper.length) {
			console.error("Custom UI wrapper not found");
			return;
		}

		if (this.isPurchaseOrderFlow()) {
			this.render_invoice_grouped();
			return;
		}

		// Load items from child table before rendering
		this.load_items_from_table();

		let html = `
			<div class="gate-pass-custom-ui">
				<div class="gate-pass-items-header">
					<h6 class="mb-3">Items List</h6>
					${this.render_add_item_button()}
				</div>
				<div class="gate-pass-items-container">
					${this.items.length > 0 ? this.render_items() : this.render_empty_state()}
				</div>
			</div>
		`;

		this.wrapper.html(html);
		this.bind_events();
	}

	/**
	 * Render the add item button
	 */
	render_add_item_button() {
		if (!this.frm.doc.reference_number) {
			return `
				<div class="alert alert-info">
					<i class="fa fa-info-circle"></i>
					Please select a Reference Document and Reference Number first to add items.
				</div>
			`;
		}

		if (this.isGateOut() && !this.shouldAllowQuantityEdit()) {
			const referenceLabel =
				this.frm.doc.document_reference === "Sales Invoice"
					? __("Sales Invoice")
					: __("Delivery Note");

			return `
				<div class="alert alert-info outbound-note">
					<i class="fa fa-info-circle"></i>
					${__(
						"Items and dispatched quantities are loaded automatically from the {0}. Editing is disabled.",
						[referenceLabel]
					)}
				</div>
			`;
		}

		if (this.isGateOut() && this.isStockEntry()) {
			return `
				<div class="alert alert-warning outbound-note">
					<i class="fa fa-info-circle"></i>
					${__(
						"You can adjust dispatched quantities here to handle partial movements for this Stock Entry."
					)}
				</div>
			`;
		}

		return `
			<button class="btn btn-sm btn-primary add-item-btn" type="button">
				<i class="fa fa-plus"></i> Add Item
			</button>
		`;
	}

	/**
	 * Render empty state when no items
	 */
	render_empty_state() {
		return `
			<div class="empty-state">
				<div class="empty-state-icon">
					<i class="fa fa-cube fa-3x text-muted"></i>
				</div>
				<p class="text-muted mt-3">No items added yet</p>
				<p class="text-muted">Click "Add Item" to get started</p>
			</div>
		`;
	}

	/**
	 * Render items list
	 */
	render_items() {
		if (!this.items || this.items.length === 0) {
			return this.render_empty_state();
		}

		if (this.isGateOut() && !this.shouldAllowQuantityEdit()) {
			return this.render_outbound_items();
		}

		return this.render_editable_items();
	}

	render_editable_items() {
		const quantityLabel = this.getQuantityLabel();

		const items_html = this.items
			.map((item, index) => this.render_item_row(item, index))
			.join("");

		return `
			<div class="items-list">
				<div class="items-list-header">
					<div class="item-col item-code-col">Item Code</div>
					<div class="item-col item-name-col">Item Name</div>
					<div class="item-col received-qty-col">${frappe.utils.escape_html(quantityLabel)}</div>
					<div class="item-col actions-col">Actions</div>
				</div>
				<div class="items-list-body">
					${items_html}
				</div>
			</div>
		`;
	}

	/**
	 * Render a single item row
	 */
	render_item_row(item, index) {
		const is_rate_contract = item.is_rate_contract || 0;
		const ordered_qty = parseFloat(item.ordered_qty || 0);
		const quantity_value = this.getQuantityValue(item);
		let pending_qty = parseFloat(item.pending_qty || 0);

		if (isNaN(pending_qty) || this.isStockEntry()) {
			pending_qty = Math.max(ordered_qty - quantity_value, 0);
			item.pending_qty = pending_qty;
		}

		let is_complete;
		if (this.isGateIn()) {
			if (is_rate_contract) {
				is_complete = quantity_value > 0;
			} else {
				is_complete = pending_qty <= 0 && quantity_value > 0;
			}
		} else {
			is_complete = quantity_value > 0 && pending_qty <= 0;
		}

		const status_class = is_complete ? "status-complete" : "status-pending";
		const quantityField = this.getQuantityField();
		const inputDisabled = this.frm.doc.docstatus === 1;
		const allowRemove = this.isGateIn();

		return `
			<div class="item-row ${status_class}" data-index="${index}">
				<div class="item-col item-code-col">
					<span class="item-code">${frappe.utils.escape_html(item.item_code)}</span>
					${
						is_rate_contract
							? '<span class="badge badge-info" style="font-size: 9px; margin-left: 4px;">RC</span>'
							: ""
					}
				</div>
				<div class="item-col item-name-col">
					<span class="item-name">${frappe.utils.escape_html(item.item_name)}</span>
				</div>
				<div class="item-col received-qty-col">
					<input
						type="number"
						class="form-control form-control-sm quantity-input"
						value="${quantity_value}"
						min="0"
						step="0.01"
						data-index="${index}"
						data-field="${quantityField}"
						${inputDisabled ? "disabled" : ""}
					/>
				</div>
				<div class="item-col actions-col">
					<button class="btn btn-xs btn-info info-btn" data-index="${index}" title="View Details">
						<i class="fa fa-info-circle"></i>
					</button>
					<button class="btn btn-xs btn-danger remove-btn" data-index="${index}" title="Remove Item"
						${inputDisabled || !allowRemove ? "disabled" : ""}>
						<i class="fa fa-minus"></i>
					</button>
				</div>
			</div>
		`;
	}

	/**
	 * Bind event listeners to UI elements
	 */
	bind_events() {
		const self = this;

		// Info buttons
		this.wrapper
			.find(".info-btn")
			.off("click")
			.on("click", function () {
				const index = $(this).data("index");
				self.show_item_details(index);
			});

		if (!this.shouldAllowQuantityEdit()) {
			return;
		}

		// Add item button
		if (this.isGateIn()) {
			this.wrapper
				.find(".add-item-btn")
				.off("click")
				.on("click", function () {
					self.show_add_item_dialog();
				});

			this.wrapper
				.find(".remove-btn")
				.off("click")
				.on("click", function () {
					if ($(this).is(":disabled")) {
						return;
					}
					const index = $(this).data("index");
					self.remove_item(index);
				});
		}

		// Quantity inputs
		this.wrapper
			.find(".quantity-input")
			.off("change")
			.on("change", function () {
				const index = $(this).data("index");
				const value = parseFloat($(this).val() || 0);
				self.updateQuantity(index, value);
			});

		this.wrapper
			.find(".quantity-input")
			.off("input")
			.on("input", function () {
				const index = $(this).data("index");
				const value = parseFloat($(this).val() || 0);
				self.validateQuantityInput(index, value, $(this));
			});
	}

	/**
	 * Show dialog to add items
	 */
	show_add_item_dialog() {
		if (!this.isGateIn()) {
			return;
		}

		const self = this;

		if (!this.frm.doc.reference_number || !this.frm.doc.document_reference) {
			frappe.msgprint(__("Please select Document Reference and Reference Number first"));
			return;
		}

		// Fetch available items from the reference document
		frappe.call({
			method: "gate_entry.gate_entry.doctype.gate_pass.gate_pass.get_items",
			args: {
				document_reference: this.frm.doc.document_reference,
				reference_number: this.frm.doc.reference_number,
			},
			callback: function (r) {
				if (r.message) {
					self.available_items = r.message;
					console.log("Available Items", self.available_items);
					self.show_item_selector_dialog();
				}
			},
		});
	}

	/**
	 * Show item selector dialog
	 */
	show_item_selector_dialog() {
		const self = this;

		// Filter out items that are already added
		const added_item_codes = this.items.map((item) => item.item_code);
		const available_for_selection = this.available_items.filter(
			(item) => !added_item_codes.includes(item.item_code)
		);

		if (available_for_selection.length === 0) {
			frappe.msgprint(__("All items from the reference document have been added"));
			return;
		}

		// Create dialog
		const dialog = new frappe.ui.Dialog({
			title: __("Select Items to Add"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "items_html",
				},
			],
			primary_action_label: __("Add Selected"),
			primary_action: function () {
				const selected_items = dialog.$wrapper.find('input[type="checkbox"]:checked');
				const items_to_add = [];

				selected_items.each(function () {
					const item_code = $(this).val();
					const item = available_for_selection.find((i) => i.item_code === item_code);
					if (item) {
						items_to_add.push(item);
					}
				});

				if (items_to_add.length > 0) {
					self.add_items(items_to_add);
					dialog.hide();
				} else {
					frappe.msgprint(__("Please select at least one item"));
				}
			},
		});

		// Render items in dialog
		const items_html = available_for_selection
			.map((item) => {
				const is_rate_contract = item.is_rate_contract || 0;
				const pending_info = is_rate_contract
					? '<span class="badge badge-info">Rate Contract</span>'
					: `<span class="text-muted">(Pending: ${item.pending_qty} ${item.uom})</span>`;

				return `
				<div class="checkbox">
					<label>
						<input type="checkbox" value="${item.item_code}">
						<strong>${frappe.utils.escape_html(item.item_code)}</strong> -
						${frappe.utils.escape_html(item.item_name)}
						${pending_info}
					</label>
				</div>
			`;
			})
			.join("");

		dialog.fields_dict.items_html.$wrapper.html(`
			<div class="item-selector-list">
				${items_html}
			</div>
		`);

		dialog.show();
	}

	/**
	 * Add items to the list
	 */
	add_items(items_to_add) {
		console.log("Items to add", items_to_add);
		items_to_add.forEach((item) => {
			this.items.push({
				// Basic item details
				item_code: item.item_code,
				item_name: item.item_name,
				description: item.description || "",
				uom: item.uom || "",
				stock_uom: item.stock_uom || "",
				conversion_factor: item.conversion_factor || 1.0,
				// Quantities
				ordered_qty: item.ordered_qty || 0,
				received_qty: 0, // Default to 0, user will enter
				dispatched_qty: item.dispatched_qty || 0,
				pending_qty: item.pending_qty || 0,
				is_rate_contract: item.is_rate_contract || 0,
				// Pricing details
				rate: item.rate || 0,
				amount: 0, // Will be calculated when user enters received_qty
				// Warehouse and location
				warehouse: item.warehouse || "",
				rejected_warehouse: item.rejected_warehouse || "",
				// Accounting details
				expense_account: item.expense_account || "",
				cost_center: item.cost_center || "",
				// Reference details
				project: item.project || "",
				schedule_date: item.schedule_date || "",
				// Other details (important for subcontracting)
				bom: item.bom || "",
				include_exploded_items: item.include_exploded_items || 0,
				order_item_name: item.order_item_name || "",
			});
		});
		console.log("Items", this.items);

		this.sync_to_child_table();
		this.render();
	}

	/**
	 * Remove an item from the list
	 */
	remove_item(index) {
		if (!this.isGateIn()) {
			return;
		}

		const item = this.items[index];

		frappe.confirm(__("Are you sure you want to remove {0}?", [item.item_code]), () => {
			this.items.splice(index, 1);
			this.sync_to_child_table();
			this.render();
			frappe.show_alert({
				message: __("Item removed successfully"),
				indicator: "green",
			});
		});
	}

	updateQuantity(index, value) {
		if (!this.shouldAllowQuantityEdit()) {
			return;
		}

		if (index < 0 || index >= this.items.length) {
			return;
		}

		const quantityField = this.getQuantityField();

		if (value < 0) {
			frappe.msgprint(
				this.isGateIn()
					? __("Quantity cannot be negative.")
					: __("Dispatched quantity cannot be negative.")
			);
			this.render();
			return;
		}

		const item = this.items[index];
		const orderedQty = parseFloat(item.ordered_qty || 0);
		const isRateContract = item.is_rate_contract || 0;

		if (this.isGateIn()) {
			const pendingQty = parseFloat(item.pending_qty || Math.max(orderedQty - value, 0));
			if (!isRateContract && value > pendingQty && pendingQty > 0) {
				frappe.msgprint({
					title: __("Over Receipt Warning"),
					message: __("You are receiving more than the pending quantity ({0} {1})", [
						pendingQty,
						item.uom,
					]),
					indicator: "orange",
				});
			}
		} else if (value > orderedQty && orderedQty > 0) {
			frappe.msgprint({
				title: __("Over Dispatch Warning"),
				message: __("You are dispatching more than the available quantity ({0})", [
					orderedQty,
				]),
				indicator: "orange",
			});
		}

		item[quantityField] = value;
		item.pending_qty = Math.max(orderedQty - value, 0);
		item.amount = value * (parseFloat(item.rate) || 0);

		this.sync_to_child_table();
		this.render();
	}

	validateQuantityInput(index, value, input_element) {
		if (!this.shouldAllowQuantityEdit()) {
			return;
		}

		const item = this.items[index];
		const orderedQty = parseFloat(item.ordered_qty || 0);
		const isRateContract = item.is_rate_contract || 0;

		input_element.removeClass("text-danger text-warning");

		if (value < 0) {
			input_element.addClass("text-danger");
			return;
		}

		if (this.isGateIn()) {
			const pendingQty = parseFloat(item.pending_qty || Math.max(orderedQty - value, 0));
			if (!isRateContract && value > pendingQty && pendingQty > 0) {
				input_element.addClass("text-warning");
			}
		} else if (value > orderedQty && orderedQty > 0) {
			input_element.addClass("text-warning");
		}
	}

	/**
	 * Show item details in a dialog
	 */
	show_item_details(index) {
		const item = this.items[index];
		const is_rate_contract = item.is_rate_contract || 0;
		const is_outbound = this.isOutbound();
		let fields = [
			{
				fieldtype: "Data",
				fieldname: "item_code",
				label: __("Item Code"),
				read_only: 1,
				default: item.item_code,
			},
			{
				fieldtype: "Data",
				fieldname: "item_name",
				label: __("Item Name"),
				read_only: 1,
				default: item.item_name,
			},
			{
				fieldtype: "Small Text",
				fieldname: "description",
				label: __("Description"),
				read_only: 1,
				default: item.description || "N/A",
			},
			{
				fieldtype: "Column Break",
			},
			{
				fieldtype: "Data",
				fieldname: "uom",
				label: __("UOM"),
				read_only: 1,
				default: item.uom || "N/A",
			},
		];

		// Add order type information
		if (is_outbound) {
			fields.push({
				fieldtype: "Float",
				fieldname: "dispatched_qty",
				label: __("Dispatched Qty"),
				read_only: 1,
				default: item.dispatched_qty || 0,
			});
		} else {
			if (is_rate_contract) {
				fields.push({
					fieldtype: "Data",
					fieldname: "order_type",
					label: __("Order Type"),
					read_only: 1,
					default: "Rate Contract",
				});
			} else {
				fields.push({
					fieldtype: "Float",
					fieldname: "ordered_qty",
					label: __("Ordered Qty"),
					read_only: 1,
					default: item.ordered_qty || 0,
				});
				fields.push({
					fieldtype: "Float",
					fieldname: "pending_qty",
					label: __("Pending Qty"),
					read_only: 1,
					default: item.pending_qty || 0,
				});
			}

			fields.push({
				fieldtype: "Float",
				fieldname: "received_qty",
				label: __("Received Qty"),
				read_only: 1,
				default: item.received_qty || 0,
			});
		}

		const dialog = new frappe.ui.Dialog({
			title: __("Item Details"),
			fields: fields,
		});

		dialog.show();
	}

	/**
	 * Setup event listeners for form state changes
	 */
	setup_event_listeners() {
		const self = this;

		// Re-render when form is refreshed
		this.frm.cscript.custom_onload = function () {
			self.render();
		};
	}

	/**
	 * Ensure layout recalculates on viewport changes (e.g., mobile rotation)
	 */
	setup_responsive_listener() {
		if (this._resizeHandlerBound) {
			return;
		}

		this._resizeHandlerBound = true;

		this._resizeHandler = frappe.utils.debounce
			? frappe.utils.debounce(() => this.render(), 300)
			: () => this.render();

		$(window).on("resize.gate_pass_ui orientationchange.gate_pass_ui", this._resizeHandler);

		// Refresh listener is handled via frappe hooks in setup_event_listeners
	}

	teardown_responsive_listener() {
		if (!this._resizeHandlerBound) {
			return;
		}

		$(window).off("resize.gate_pass_ui orientationchange.gate_pass_ui", this._resizeHandler);
		this._resizeHandlerBound = false;
	}

	/**
	 * Refresh the UI
	 */
	refresh() {
		// Small delay to ensure data is loaded from server
		setTimeout(() => {
			this.render();
		}, 100);
	}

	isOutbound() {
		return (this.frm?.doc?.entry_type || "Gate Out") === "Gate Out";
	}

	// ── PO-flow: invoice-grouped rendering ─────────────────────────────────

	render_invoice_grouped() {
		const invoices = this.frm.doc.gate_pass_invoices || [];
		const editable = this.shouldAllowQuantityEdit();

		const groups = invoices.map((inv) => this.render_invoice_group(inv, editable)).join("");

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
			? `<button class="btn btn-xs btn-default inv-add-item" data-invoice="${frappe.utils.escape_html(
					invoice_no
			  )}">
					<i class="fa fa-plus"></i> ${__("Add Item")}</button>`
			: "";

		return `
			<div class="invoice-group" data-invoice="${frappe.utils.escape_html(
				invoice_no
			)}" style="border:1px solid var(--border-color);border-radius:6px;padding:10px;margin-bottom:10px;">
				<div class="invoice-group-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
					<strong>${__("Invoice")}: ${frappe.utils.escape_html(invoice_no) || __("(unnamed)")}</strong>
					${
						editable
							? `<button class="btn btn-xs btn-danger inv-remove-invoice" data-invoice="${frappe.utils.escape_html(
									invoice_no
							  )}">${__("Remove Invoice")}</button>`
							: ""
					}
				</div>
				<div class="invoice-items">${items_html}</div>
				<div class="mt-2">${add_item}</div>
			</div>`;
	}

	bind_invoice_events() {
		const self = this;
		this.wrapper
			.find(".add-invoice-btn")
			.off("click")
			.on("click", () => self.add_invoice());
		this.wrapper
			.find(".inv-remove-invoice")
			.off("click")
			.on("click", function () {
				self.remove_invoice($(this).data("invoice"));
			});
		this.wrapper
			.find(".inv-add-item")
			.off("click")
			.on("click", function () {
				self.add_item_to_invoice($(this).data("invoice"));
			});
		this.wrapper
			.find(".inv-remove-item")
			.off("click")
			.on("click", function () {
				self.remove_invoice_item($(this).data("name"));
			});
		this.wrapper
			.find(".inv-qty-input")
			.off("change")
			.on("change", function () {
				self.set_invoice_item_qty($(this).data("name"), parseFloat($(this).val() || 0));
			});
	}

	add_invoice() {
		frappe.prompt(
			[
				{
					fieldname: "invoice_no",
					label: __("Supplier Invoice No"),
					fieldtype: "Data",
					reqd: 1,
				},
			],
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
					const remaining =
						flt(item.pending_qty) - flt(allocated[item.order_item_name] || 0);
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
					const remaining =
						flt(item.pending_qty) - flt(allocated[item.order_item_name] || 0);
					return `<div class="checkbox"><label>
						<input type="checkbox" value="${item.order_item_name}">
						<strong>${frappe.utils.escape_html(item.item_code)}</strong> - ${frappe.utils.escape_html(
						item.item_name || ""
					)}
						<span class="text-muted">(${__("Pending")}: ${remaining} ${frappe.utils.escape_html(
						item.uom || ""
					)})</span>
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
			this.wrapper
				.find(`.inv-qty-input[data-name="${row_name}"]`)
				.val(flt(row.received_qty));
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

	render_outbound_items() {
		return `
			<div class="items-list outbound-items-list">
				<div class="items-list-header outbound-items-header">
					<div class="item-col item-code-col">${__("Item Code")}</div>
					<div class="item-col item-name-col">${__("Item Name")}</div>
					<div class="item-col received-qty-col">${__("Dispatched Qty")}</div>
					<div class="item-col actions-col">${__("Actions")}</div>
				</div>
				<div class="items-list-body outbound-items-body">
					${this.items
						.map((item, idx) => {
							const tooltip =
								item.item_code && item.item_code !== item.item_name
									? `title="${frappe.utils.escape_html(item.item_code)}"`
									: "";
							return `
								<div class="item-row outbound-row" ${tooltip}>
					<div class="item-col item-code-col">
						<span class="item-code">${frappe.utils.escape_html(item.item_code || "")}</span>
					</div>
					<div class="item-col item-name-col outbound-name">
						<span class="item-name">${frappe.utils.escape_html(item.item_name || item.item_code || "")}</span>
					</div>
					<div class="item-col received-qty-col outbound-qty-col">
						<span class="outbound-qty-value">${this.formatQuantity(item.dispatched_qty)}</span>
						${item.uom ? `<span class="outbound-qty-uom">${frappe.utils.escape_html(item.uom)}</span>` : ""}
					</div>
					<div class="item-col actions-col outbound-actions">
						<button class="btn btn-xs btn-info info-btn" data-index="${idx}" title="View Details">
							<i class="fa fa-info-circle"></i>
						</button>
					</div>
								</div>
							`;
						})
						.join("")}
				</div>
			</div>
		`;
	}

	formatQuantity(value) {
		const number = frappe.utils.flt ? frappe.utils.flt(value || 0) : parseFloat(value || 0);
		return frappe.format
			? frappe.format(number, { fieldtype: "Float", precision: this.precision })
			: (number || 0).toFixed(this.precision);
	}
}

// Export for use in gate_pass.js
window.GatePassCustomUI = GatePassCustomUI;
