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
		# pr_col / sdn_col are code-controlled column-name literals (or "NULL"),
		# never user input — safe to interpolate.
		rows = frappe.db.sql(  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-sql-format-injection
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
			gate_pass.flags.ignore_validate_update_after_submit = True
			gate_pass.save(ignore_permissions=True)

	# Drop only the orphan purchase_receipt column.
	# supplier_delivery_note stays — it remains a live field for the Subcontracting flow.
	if has_pr:
		frappe.db.sql_ddl("ALTER TABLE `tabGate Pass` DROP COLUMN `purchase_receipt`")

	frappe.db.commit()
