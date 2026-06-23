// Copyright (c) 2025, Gurudatt Kulkarni and contributors
// For license information, please see license.txt
const STOCK_ENTRY_REFERENCE = "Stock Entry";
const INBOUND_REFERENCES = ["Purchase Order", "Subcontracting Order"];
const OUTBOUND_REFERENCES = ["Sales Invoice", "Delivery Note"];
const DOCUMENT_REFERENCES = [
	...new Set([...INBOUND_REFERENCES, ...OUTBOUND_REFERENCES, STOCK_ENTRY_REFERENCE]),
];

frappe.ui.form.on("Gate Pass", {
	onload_post_render(frm) {
		// Initialize the custom UI component after form is fully rendered
		if (!frm.gate_pass_ui && window.GatePassCustomUI) {
			frm.gate_pass_ui = new window.GatePassCustomUI(frm);
		}
	},

	onload(frm) {
		frm.set_query("document_reference", function () {
			return {
				filters: {
					name: ["in", DOCUMENT_REFERENCES],
				},
			};
		});

	},

	async refresh(frm) {
		// Initialize the custom UI component if not already done
		if (!frm.gate_pass_ui && window.GatePassCustomUI) {
			frm.gate_pass_ui = new window.GatePassCustomUI(frm);
		} else if (frm.gate_pass_ui) {
			// Refresh the UI to show updated data
			frm.gate_pass_ui.refresh();
		}

		// Auto-populate security guard name with current user
		if (frm.is_new() && !frm.doc.security_guard_name) {
			frm.set_value(
				"security_guard_name",
				frappe.session.user_fullname || frappe.session.user
			);
		}

		// Auto-populate gate pass date and time
		if (frm.is_new() && !frm.doc.gate_pass_date) {
			frm.set_value("gate_pass_date", frappe.datetime.get_today());
			frm.set_value("gate_pass_time", frappe.datetime.now_time());
		}

		// Auto-populate gate entry date and time
		if (frm.is_new() && !frm.doc.gate_entry_date) {
			frm.set_value("gate_entry_date", frappe.datetime.get_today());
			frm.set_value("gate_entry_time", frappe.datetime.now_time());
		}

		// Hide the gate_pass_table field (it's for backend only)
		frm.toggle_display("gate_pass_table", false);

		frm.set_query("outbound_material_transfer", () => ({
			filters: {
				docstatus: 1,
				stock_entry_type: ["in", ["Material Transfer", "Send to Subcontractor"]],
				ge_external_transfer: 1,
			},
		}));

		frm.set_query("return_material_transfer", () => ({
			filters: {
				docstatus: 1,
				stock_entry_type: ["in", ["Material Transfer"]],
				is_return: 1,
			},
		}));

		frm.set_query("stock_entry_reference", () => ({
			filters: {
				docstatus: 1,
				name: frm.doc.reference_number || undefined,
			},
		}));

		toggle_stock_entry_link_permissions(frm);
		toggle_discrepancy_fields(frm);
		show_stock_entry_guidance(frm);

		// Show "Create Receipt" and "Create Stock Entry" buttons after submission
		if (frm.doc.docstatus === 1) {
			setup_receipt_buttons(frm);
			await setup_stock_entry_button(frm);
		}

		// Filter Document Reference to show only relevant doctypes
		frm.set_query("document_reference", function () {
			return {
				filters: {
					name: ["in", DOCUMENT_REFERENCES],
				},
			};
		});

		refresh_compliance_status(frm);
	},

	after_save(frm) {
		// Reload the form to ensure child table data is properly loaded
		// Then refresh the custom UI
		frappe.after_ajax(() => {
			if (frm.gate_pass_ui) {
				frm.gate_pass_ui.refresh();
			}
		});
	},

	document_reference(frm) {
		// Clear reference number when document reference changes
		if (frm.doc.reference_number) {
			frm.set_value("reference_number", "");
		}
		if (frm.doc.document_reference) {
			frm.set_query("reference_number", function () {
				console.log("On document_reference change Reference Number Filter Applied");
				let filters = { docstatus: 1 };
				if (
					frm.doc.document_reference === "Purchase Order" ||
					frm.doc.document_reference === "Subcontracting Order"
				) {
					filters["status"] = ["!=", "Closed"];
				} else if (frm.doc.document_reference === "Stock Entry") {
					filters["stock_entry_type"] = [
						"in",
						["Material Transfer", "Send to Subcontractor"],
					];
				}
				return { filters: filters };
			});
		}

		// Update entry type locally for better UX
		if (frm.doc.document_reference === STOCK_ENTRY_REFERENCE) {
			frm.set_value("entry_type", "Gate Out");
			frm.set_value("supplier", null);
			frm.set_value("supplier_delivery_note", null);
		} else if (is_outbound_reference(frm.doc.document_reference, "Gate Out")) {
			frm.set_value("entry_type", "Gate Out");
			frm.set_value("supplier", null);
			frm.set_value("supplier_delivery_note", null);
		} else {
			frm.set_value("entry_type", "Gate In");
		}

		// Clear items when document type changes
		frm.clear_table("gate_pass_table");
		frm.refresh_field("gate_pass_table");

		frm.set_value("outbound_material_transfer", null);
		frm.set_value("return_material_transfer", null);
		frm.set_value("has_discrepancy", 0);
		frm.set_value("lost_quantity", 0);
		frm.set_value("damaged_quantity", 0);
		frm.set_value("discrepancy_notes", null);

		toggle_stock_entry_link_permissions(frm);
		toggle_discrepancy_fields(frm);

		clear_compliance_status(frm);

		// Refresh custom UI
		if (frm.gate_pass_ui) {
			frm.gate_pass_ui.refresh();
		}
	},

	reference_number(frm) {
		// Fetch address display from reference document
		if (frm.doc.document_reference && frm.doc.reference_number) {
			load_reference_details(frm);

			if (frm.doc.document_reference === STOCK_ENTRY_REFERENCE) {
				load_reference_items(frm);
				clear_compliance_status(frm);
			} else if (is_outbound_reference(frm.doc.document_reference, frm.doc.entry_type)) {
				load_reference_items(frm);
				refresh_compliance_status(frm);
			} else {
				clear_compliance_status(frm);
			}
		} else {
			clear_compliance_status(frm);
		}

		// Refresh custom UI to show/hide Add Item button
		if (frm.gate_pass_ui) {
			frm.gate_pass_ui.refresh();
		}
	},

	has_discrepancy(frm) {
		toggle_discrepancy_fields(frm);
	},

	manual_return_flow(frm) {
		if (frm.doc.manual_return_flow) {
			frm.set_value("entry_type", "Gate In");
			show_stock_entry_guidance(frm);
		} else {
			frm.trigger("document_reference");
			show_stock_entry_guidance(frm);
		}
	},

	stock_entry_reference(frm) {
		// keep guidance in sync
		show_stock_entry_guidance(frm);
	},
});

/**
 * Setup receipt creation buttons
 */
function setup_receipt_buttons(frm) {
	// Check if receipt already created
	const subcontracting_receipt_created = frm.doc.subcontracting_receipt;

	// Show appropriate button based on document reference type
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
	if (frm.doc.document_reference === "Subcontracting Order") {
		if (!subcontracting_receipt_created) {
			frm.add_custom_button(__("Create Subcontracting Receipt"), function () {
				create_subcontracting_receipt(frm);
			}).addClass("btn-primary");
		} else {
			// Show link to created receipt
			frm.add_custom_button(__("View Subcontracting Receipt"), function () {
				frappe.set_route("Form", "Subcontracting Receipt", frm.doc.subcontracting_receipt);
			});
		}
	}
}

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

/**
 * Create Subcontracting Receipt from Gate Pass
 */
function create_subcontracting_receipt(frm) {
	frappe.confirm(__("Create Subcontracting Receipt from this Gate Pass?"), function () {
		frappe.call({
			method: "gate_entry.gate_entry.doctype.gate_pass.gate_pass.create_subcontracting_receipt",
			args: {
				gate_pass_name: frm.doc.name,
			},
			freeze: true,
			freeze_message: __("Creating Subcontracting Receipt..."),
			callback: function (r) {
				if (r.message) {
					frappe.show_alert({
						message: __("Subcontracting Receipt {0} created successfully", [
							r.message,
						]),
						indicator: "green",
					});
					// Redirect to the new Subcontracting Receipt
					frappe.set_route("Form", "Subcontracting Receipt", r.message);
				}
			},
		});
	});
}

/**
 * Setup Stock Entry creation button for inbound gate passes
 */
async function setup_stock_entry_button(frm) {
	// Only show for inbound gate passes with Stock Entry reference
	if (frm.doc.document_reference === STOCK_ENTRY_REFERENCE && frm.doc.entry_type === "Gate In") {
		// Check if return_material_transfer exists and is valid
		// If the field is set, verify the document exists in the database
		// This handles cases where a draft Stock Entry was deleted
		const return_transfer = frm.doc.return_material_transfer;
		let has_valid_return_transfer = false;

		if (return_transfer) {
			try {
				has_valid_return_transfer = await frappe.db.exists("Stock Entry", return_transfer);
			} catch (e) {
				// Document doesn't exist or error checking
				has_valid_return_transfer = false;
			}
		}

		if (!has_valid_return_transfer) {
			// Show "Create Stock Entry" button if:
			// 1. return_material_transfer is not set, OR
			// 2. return_material_transfer is set but the document doesn't exist (was deleted)
			// But only if outbound_material_transfer exists (required to create return Stock Entry)
			if (frm.doc.outbound_material_transfer) {
				frm.add_custom_button(__("Create Stock Entry"), function () {
					create_stock_entry_from_gate_pass(frm);
				}).addClass("btn-primary");
			}
		} else {
			// Show link to created Stock Entry if it exists
			frm.add_custom_button(__("View Stock Entry"), function () {
				frappe.set_route("Form", "Stock Entry", return_transfer);
			});
		}
	}
}

/**
 * Create Stock Entry from inbound Gate Pass
 */
function create_stock_entry_from_gate_pass(frm) {
	frappe.confirm(
		__("Create a return Material Transfer Stock Entry from this inbound Gate Pass?"),
		function () {
			frappe.call({
				method: "gate_entry.gate_entry.doctype.gate_pass.gate_pass.create_stock_entry_from_inbound_gate_pass",
				args: {
					gate_pass_name: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Creating Stock Entry..."),
				callback: function (r) {
					if (r.message) {
						frappe.show_alert({
							message: __("Stock Entry {0} created successfully", [r.message]),
							indicator: "green",
						});
						// Reload the form to show the updated return_material_transfer field
						frm.reload_doc();
						// Redirect to the new Stock Entry
						frappe.set_route("Form", "Stock Entry", r.message);
					}
				},
			});
		}
	);
}

function load_reference_details(frm) {
	frappe.call({
		method: "gate_entry.gate_entry.doctype.gate_pass.gate_pass.get_reference_details",
		args: {
			document_reference: frm.doc.document_reference,
			reference_number: frm.doc.reference_number,
		},
		callback(response) {
			const details = response.message;
			console.log("Details: ", details);
			if (!details) {
				return;
			}

			const updates = {};

			if (details.company && !frm.doc.company) {
				updates.company = details.company;
			}

			if (details.address_display) {
				updates.address_display = details.address_display;
			}

			updates.e_invoice_status = details.e_invoice_status || null;
			updates.e_invoice_reference = details.e_invoice_reference || null;
			updates.e_waybill_status = details.e_waybill_status || null;
			updates.e_waybill_number = details.e_waybill_number || null;

			if (details.vehicle_number && !frm.doc.vehicle_number) {
				updates.vehicle_number = details.vehicle_number;
			}
			if (details.driver_name && !frm.doc.driver_name) {
				updates.driver_name = details.driver_name;
			}
			if (details.driver_contact && !frm.doc.driver_contact) {
				updates.driver_contact = details.driver_contact;
			}
			if (is_outbound_reference(frm.doc.document_reference, frm.doc.entry_type)) {
				updates.supplier = null;
				updates.supplier_delivery_note = null;
			} else if (details.party_type === "Supplier" && details.party) {
				updates.supplier = details.party;
				if (details.supplier_delivery_note) {
					updates.supplier_delivery_note = details.supplier_delivery_note;
				}
			}
			console.log("Updates: ", updates);
			frm.set_value(updates).then(() => {
				frm.refresh();
			});
		},
	});
}

function load_reference_items(frm) {
	frappe.call({
		method: "gate_entry.gate_entry.doctype.gate_pass.gate_pass.get_items",
		args: {
			document_reference: frm.doc.document_reference,
			reference_number: frm.doc.reference_number,
		},
		freeze: true,
		freeze_message: __("Loading items from reference document..."),
		callback(response) {
			const items = response.message || [];
			set_gate_pass_items(frm, items);
		},
	});
}

function set_gate_pass_items(frm, items) {
	frm.clear_table("gate_pass_table");
	// fetch the value of manual_return_flow
	const is_return_flow = parseInt(frm.doc.manual_return_flow || 0) === 1;
	console.log("Is return flow: ", is_return_flow);
	(items || []).forEach((item) => {
		const row = frm.add_child("gate_pass_table");
		row.item_code = item.item_code;
		row.item_name = item.item_name || "";
		row.description = item.description || "";
		row.uom = item.uom || "";
		row.stock_uom = item.stock_uom || "";
		row.conversion_factor = item.conversion_factor || 1.0;
		row.ordered_qty = item.ordered_qty || 0;
		row.received_qty = is_return_flow ? item.received_qty : 0;
		row.dispatched_qty = item.dispatched_qty || 0;
		row.pending_qty = item.pending_qty || 0;
		row.is_rate_contract = item.is_rate_contract || 0;
		row.rate = item.rate || 0;
		const qty_for_amount = is_outbound_reference(
			frm.doc.document_reference,
			frm.doc.entry_type
		)
			? item.dispatched_qty || 0
			: item.received_qty || 0;
		row.amount = qty_for_amount * (item.rate || 0);
		row.warehouse = item.warehouse || "";
		row.rejected_warehouse = item.rejected_warehouse || "";
		row.expense_account = item.expense_account || "";
		row.cost_center = item.cost_center || "";
		row.project = item.project || "";
		row.schedule_date = item.schedule_date || "";
		row.bom = item.bom || "";
		row.include_exploded_items = item.include_exploded_items || 0;
		row.order_item_name = item.order_item_name || "";
	});

	frm.refresh_field("gate_pass_table");

	if (frm.gate_pass_ui) {
		frm.gate_pass_ui.refresh();
	}
}

function toggle_discrepancy_fields(frm) {
	console.log(frm.doc.has_discrepancy);

	const show = frm.doc.has_discrepancy;
	const can_edit =
		(frm.perm && frm.perm[0] && frm.perm[0].write) ||
		frappe.perm.has_perm("Gate Pass", 0, "write");

	const fields = ["has_discrepancy", "lost_quantity", "damaged_quantity", "discrepancy_notes"];
	fields.forEach((fieldname) => {
		const read_only = !can_edit || frm.doc.docstatus > 0;
		frm.set_df_property(fieldname, "read_only", read_only);
	});

	frm.toggle_reqd("lost_quantity", show);
	frm.toggle_reqd("damaged_quantity", show);
}

function is_outbound_reference(documentReference, entryType) {
	if (documentReference === STOCK_ENTRY_REFERENCE) {
		return (entryType || "Gate Out") === "Gate Out";
	}
	return OUTBOUND_REFERENCES.includes(documentReference);
}

function toggle_stock_entry_link_permissions(frm) {
	const can_edit =
		(frm.perm && frm.perm[0] && frm.perm[0].write) ||
		frappe.perm.has_perm("Gate Pass", 0, "write");
	const read_only = !can_edit || frm.doc.docstatus > 0;

	["outbound_material_transfer", "return_material_transfer"].forEach((field) => {
		frm.set_df_property(field, "read_only", read_only);
	});
	frm.set_df_property("manual_return_flow", "read_only", read_only);
}

function refresh_compliance_status(frm) {
	const field = frm.fields_dict?.compliance_status_html;
	if (!field) {
		return;
	}

	if (
		!frm.doc.document_reference ||
		!frm.doc.reference_number ||
		!is_outbound_reference(frm.doc.document_reference, frm.doc.entry_type)
	) {
		clear_compliance_status(frm);
		return;
	}

	frappe.call({
		method: "gate_entry.gate_entry.doctype.gate_pass.gate_pass.get_outbound_compliance_status",
		args: {
			document_reference: frm.doc.document_reference,
			reference_number: frm.doc.reference_number,
			gate_pass: frm.doc.name || null,
		},
		callback(response) {
			const status = response.message;
			set_compliance_status(field, status);
		},
	});
}

function clear_compliance_status(frm) {
	const field = frm.fields_dict?.compliance_status_html;
	if (!field) {
		return;
	}
	set_compliance_status(field, null);
}

function set_compliance_status(field, status) {
	const wrapper = field.$wrapper;
	if (!wrapper || wrapper.length === 0) {
		return;
	}
	if (!status) {
		wrapper.empty();
		return;
	}

	const level = status.level || "info";
	const title = frappe.utils.escape_html(status.title || "");
	const messages = Array.isArray(status.messages) ? status.messages : [];
	const description = status.description ? frappe.utils.escape_html(status.description) : "";

	let icon = "info-circle";
	if (level === "success") {
		icon = "check-circle";
	} else if (level === "warning") {
		icon = "exclamation-triangle";
	} else if (level === "error") {
		icon = "times-circle";
	}

	const body = [];
	if (title) {
		body.push(`<div class="compliance-banner-title">${title}</div>`);
	}

	if (description) {
		body.push(`<div class="compliance-banner-description">${description}</div>`);
	}

	if (messages.length) {
		const listItems = messages
			.map((message) => `<li>${frappe.utils.escape_html(message)}</li>`)
			.join("");
		body.push(`<ul class="compliance-banner-list">${listItems}</ul>`);
	}

	if (!body.length) {
		body.push(
			`<div class="compliance-banner-description">${__(
				"No compliance information available."
			)}</div>`
		);
	}

	const html = `
		<div class="compliance-banner compliance-${level}">
			<div class="compliance-banner-icon">
				<i class="fa fa-${icon}"></i>
			</div>
			<div class="compliance-banner-body">
				${body.join("")}
			</div>
		</div>
	`;

	wrapper.html(html);
}

function show_stock_entry_guidance(frm) {
	if (frm.doc.document_reference !== STOCK_ENTRY_REFERENCE) {
		return;
	}

	frm.dashboard.clear_comment();

	if (frm.doc.manual_return_flow) {
		frm.dashboard.add_comment(
			__(
				"Material is returning before a Stock Entry is recorded. Select the outbound transfer in the section below so quantities can be validated."
			),
			"yellow"
		);
	} else if (frm.doc.entry_type === "Gate In" && !frm.doc.reference_number) {
		frm.dashboard.add_comment(
			__("Select the Stock Entry return document to link this Gate Pass."),
			"orange"
		);
	}
}
