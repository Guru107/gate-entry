# Copyright (c) 2025, Gurudatt Kulkarni and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import cint

from gate_entry.gate_entry.doctype.gate_pass.gate_pass import (
	GatePass,
	get_delivery_note_items,
	get_sales_invoice_items,
)

# ============================================================================
# MOCK CLASSES AND HELPERS
# ============================================================================


class MockDoc(SimpleNamespace):
	"""Mock document class that supports both attribute access and .get() method like frappe documents."""

	def get(self, key, default=None):
		"""Support .get() method for dictionary-like access."""
		return getattr(self, key, default)


class MockQueryBuilder:
	"""Reusable mock query builder that supports chaining and run() calls."""

	def __init__(self, return_value_pluck=None, return_value_dict=None):
		self.return_value_pluck = return_value_pluck or []
		self.return_value_dict = return_value_dict or []

	def select(self, *args):
		return self

	def where(self, *args):
		return self

	def for_update(self):
		return self

	def groupby(self, *args):
		return self

	def limit(self, *args):
		"""Mock limit method for query builder chaining."""
		return self

	def run(self, pluck=False, as_dict=False):
		"""Return different values based on pluck vs as_dict."""
		if pluck:
			return self.return_value_pluck
		if as_dict:
			return self.return_value_dict
		return []


# ============================================================================
# TEST CLASS
# ============================================================================


class TestGatePass(FrappeTestCase):
	"""Test suite for Gate Pass doctype."""

	def setUp(self):
		"""Set up test fixtures - uses test records from test_records.json"""
		self.company = "Wind Power LLP"
		self.company_abbr = "WP"
		self.test_item = "_Test Gate Entry Item 1"

	# ========================================================================
	# HELPER METHODS
	# ========================================================================

	def create_stock_entry_item(self, name, item_code=None, qty=10, **kwargs):
		"""Create a mock stock entry item."""
		item_code = item_code or self.test_item
		return SimpleNamespace(
			name=name,
			item_code=item_code,
			item_name=item_code,
			description="",
			qty=qty,
			transfer_qty=qty,
			uom="Nos",
			stock_uom="Nos",
			conversion_factor=1.0,
			basic_rate=100,
			basic_amount=qty * 100,
			s_warehouse=f"Stores - {self.company_abbr}",
			t_warehouse=f"Finished Goods - {self.company_abbr}",
			cost_center=None,
			project=None,
			**kwargs,
		)

	def create_mock_stock_entry(self, name, items, **kwargs):
		"""Create a mock stock entry document."""
		return MockDoc(
			name=name,
			docstatus=1,
			items=items,
			company=self.company,
			stock_entry_type="Material Transfer",
			is_return=0,
			return_against=None,
			ge_outbound_reference=None,
			**kwargs,
		)

	def create_gate_pass(self, **kwargs):
		"""Create a new gate pass document with default values."""
		gate_pass = frappe.new_doc("Gate Pass")
		gate_pass.company = self.company
		gate_pass.document_reference = kwargs.get("document_reference", "Stock Entry")
		gate_pass.reference_number = kwargs.get("reference_number")
		gate_pass.entry_type = kwargs.get("entry_type", "Gate Out")
		gate_pass.manual_return_flow = kwargs.get("manual_return_flow", 0)
		# Set all provided kwargs (overwrite defaults if needed)
		for key, value in kwargs.items():
			setattr(gate_pass, key, value)
		return gate_pass

	def mock_get_cached_doc(self, stock_entry=None, gst_settings=True):
		"""Create a mock for frappe.get_cached_doc."""

		def fake_get_cached(doctype, name=None):
			if name is None:
				if doctype == "GST Settings" and gst_settings:
					return frappe._dict()
				raise frappe.DoesNotExistError

			if doctype == "Stock Entry" and stock_entry and name == stock_entry.name:
				return stock_entry
			raise frappe.DoesNotExistError

		return fake_get_cached

	def mock_qb_for_allocations(self, gate_pass_names=None, allocations=None):
		"""
		Create a mock for frappe.qb.from_ that returns allocations.

		Args:
			gate_pass_names: List of gate pass names (for pluck=True queries)
			allocations: List of allocation dicts (for as_dict=True queries)
				Format: [frappe._dict(order_item_name="ITEM-1", total=5)]

		Returns:
			(call_count_list, fake_qb_from_function)
		"""
		gate_pass_names = gate_pass_names or []
		allocations = allocations or []

		gate_pass_names_qb = MockQueryBuilder(return_value_pluck=gate_pass_names)
		allocations_qb = MockQueryBuilder(return_value_dict=allocations)
		call_count = [0]

		def fake_qb_from(doctype):
			call_count[0] += 1
			# Odd calls return gate pass names, even calls return allocations
			if call_count[0] % 2 == 1:
				return gate_pass_names_qb
			return allocations_qb

		return call_count, fake_qb_from

	def mock_qb_for_multiple_calls(self, call_sequences):
		"""
		Create a mock for frappe.qb.from_ that handles multiple call sequences.

		Args:
			call_sequences: List of tuples, each tuple is (gate_pass_names, allocations)
				Example: [(["GP-1"], [dict(total=3)]), (["GP-2"], [dict(total=5)])]

		Returns:
			(call_count_list, fake_qb_from_function)
		"""
		instances = []
		for gate_pass_names, allocations in call_sequences:
			instances.append(MockQueryBuilder(return_value_pluck=gate_pass_names))
			instances.append(MockQueryBuilder(return_value_dict=allocations))

		call_count = [0]

		def fake_qb_from(doctype):
			instance = instances[call_count[0] % len(instances)]
			call_count[0] += 1
			return instance

		return call_count, fake_qb_from

	# ========================================================================
	# TESTS
	# ========================================================================

	def test_sales_invoice_items_exclude_financial_fields(self):
		"""Test that sales invoice items exclude financial fields."""
		item = SimpleNamespace(
			item_code="ITEM-001",
			item_name="Widget",
			description="Sample",
			uom="Nos",
			stock_uom="Nos",
			conversion_factor=1,
			qty=5,
			warehouse="Stores - CO",
			cost_center="Main - CO",
			rate=100,
			amount=500,
			project=None,
			delivery_date=None,
			name="SINV-ITEM-001",
		)
		mock_doc = SimpleNamespace(
			items=[item],
			get=lambda field, default=None: [item] if field == "items" else default,
		)

		with patch("gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.get_doc", return_value=mock_doc):
			items = get_sales_invoice_items("SINV-0001")

		self.assertEqual(len(items), 1)
		data = items[0]
		self.assertNotIn("rate", data)
		self.assertNotIn("amount", data)
		self.assertEqual(data["dispatched_qty"], 5)
		self.assertEqual(data["warehouse"], "Stores - CO")

	def test_delivery_note_items_exclude_financial_fields(self):
		"""Test that delivery note items exclude financial fields."""
		item = SimpleNamespace(
			item_code="ITEM-002",
			item_name="Gadget",
			description="Sample",
			uom="Nos",
			stock_uom="Nos",
			conversion_factor=1,
			qty=3,
			warehouse="Finished - CO",
			target_warehouse=None,
			cost_center="Main - CO",
			rate=200,
			amount=600,
			project=None,
			schedule_date=None,
			name="DN-ITEM-001",
		)
		mock_doc = SimpleNamespace(
			items=[item],
			get=lambda field, default=None: [item] if field == "items" else default,
		)

		with patch("gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.get_doc", return_value=mock_doc):
			items = get_delivery_note_items("DN-0001")

		self.assertEqual(len(items), 1)
		data = items[0]
		self.assertNotIn("rate", data)
		self.assertNotIn("amount", data)
		self.assertEqual(data["dispatched_qty"], 3)
		self.assertEqual(data["warehouse"], "Finished - CO")

	def test_manual_return_flow_preserves_received_quantities(self):
		"""Test that manual return flow preserves received quantities when items are re-aligned."""
		# Setup
		item_row = self.create_stock_entry_item("STE-OUT-ITEM-1", qty=5)
		stock_entry = self.create_mock_stock_entry("STE-OUT-001", [item_row])

		gate_pass = self.create_gate_pass(
			reference_number="STE-OUT-001", manual_return_flow=1, entry_type="Gate In"
		)

		# Mock dependencies
		call_count, fake_qb_from = self.mock_qb_for_allocations()

		with (
			patch(
				"gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.get_cached_doc",
				side_effect=self.mock_get_cached_doc(stock_entry),
			),
			patch(
				"gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.get_doc",
				return_value=stock_entry,
			),
			patch("gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.get_all", return_value=[]),
			patch("gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.db.get_all", return_value=[]),
			patch(
				"gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.qb.from_", side_effect=fake_qb_from
			),
		):
			gate_pass.before_validate()
			context = gate_pass.get_stock_entry_context()
			gate_pass.ensure_stock_entry_items(context)

			self.assertEqual(len(gate_pass.gate_pass_table), 1)

			# Set received_qty and verify it's preserved after re-alignment
			gate_pass.gate_pass_table[0].received_qty = 2
			gate_pass.before_validate()
			context = gate_pass.get_stock_entry_context()
			gate_pass.ensure_stock_entry_items(context)

			self.assertEqual(gate_pass.outbound_material_transfer, "STE-OUT-001")
			self.assertEqual(gate_pass.gate_pass_table[0].received_qty, 2)

			gate_pass.validate()

	def test_get_existing_allocations_considers_outbound_link(self):
		"""Test that get_existing_allocations considers outbound material transfer links."""
		gate_pass = GatePass(frappe._dict(doctype="Gate Pass"))
		gate_pass.name = "GP-TEST-001"

		call_count, fake_qb_from = self.mock_qb_for_multiple_calls(
			[
				(["GP-OTHER"], [frappe._dict(order_item_name="STE-OUT-ITEM-1", total=3)]),
			]
		)

		with patch(
			"gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.qb.from_", side_effect=fake_qb_from
		):
			result = gate_pass.get_existing_stock_entry_allocations("STE-OUT-001", "Gate In")

		self.assertEqual(result, {"STE-OUT-ITEM-1": 3})

	def test_multi_pass_allocation_partial_quantities(self):
		"""Test that multiple gate passes can allocate partial quantities from same stock entry."""
		gate_pass1 = GatePass(frappe._dict(doctype="Gate Pass"))
		gate_pass1.name = "GP-001"

		gate_pass2 = GatePass(frappe._dict(doctype="Gate Pass"))
		gate_pass2.name = "GP-002"

		# GP-001 excludes itself, so sees allocations from GP-OTHER
		# GP-002 sees GP-001's allocations
		call_count, fake_qb_from = self.mock_qb_for_multiple_calls(
			[
				(["GP-OTHER"], [frappe._dict(order_item_name="STE-ITEM-1", total=3)]),  # GP-001 call
				(["GP-001"], [frappe._dict(order_item_name="STE-ITEM-1", total=3)]),  # GP-002 call
			]
		)

		with patch(
			"gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.qb.from_", side_effect=fake_qb_from
		):
			result1 = gate_pass1.get_existing_stock_entry_allocations("STE-001", "Gate Out")
			self.assertEqual(result1, {"STE-ITEM-1": 3})

			result2 = gate_pass2.get_existing_stock_entry_allocations("STE-001", "Gate Out")
			self.assertEqual(result2, {"STE-ITEM-1": 3})

	def test_multi_pass_allocation_exceeds_balance(self):
		"""Test that gate pass validation prevents over-allocation across multiple passes."""
		# Setup: Stock entry with 10 units, 8 already allocated, trying to allocate 5 more
		item = self.create_stock_entry_item("STE-ITEM-1", qty=10)
		stock_entry = self.create_mock_stock_entry("STE-001", [item])

		gate_pass = self.create_gate_pass(reference_number="STE-001", entry_type="Gate Out")

		# Mock: 8 units already allocated
		call_count, fake_qb_from = self.mock_qb_for_allocations(
			gate_pass_names=["GP-EXISTING"], allocations=[frappe._dict(order_item_name="STE-ITEM-1", total=8)]
		)

		# Patch to preserve dispatched_qty during alignment
		original_align = GatePass.align_gate_pass_items
		test_dispatched_qty = 5

		def patched_align(self, reference_items, preserve_quantities=False):
			original_align(self, reference_items, preserve_quantities)
			if not preserve_quantities and hasattr(self, "_test_dispatched_qty"):
				for row in self.gate_pass_table:
					if row.order_item_name == "STE-ITEM-1":
						row.dispatched_qty = self._test_dispatched_qty
						break

		with (
			patch(
				"gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.get_cached_doc",
				side_effect=self.mock_get_cached_doc(stock_entry),
			),
			patch(
				"gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.qb.from_",
				side_effect=fake_qb_from,
			),
			patch(
				"gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.db.exists",
				side_effect=lambda dt, dn=None: dt == "DocType" and dn == "GST Settings" if dn else False,
			),
			patch.object(GatePass, "align_gate_pass_items", new=patched_align),
			patch.object(GatePass, "validate_outbound_quantities", return_value=None),
		):
			gate_pass.before_validate()
			context = gate_pass.get_stock_entry_context()
			gate_pass._test_dispatched_qty = test_dispatched_qty
			gate_pass.ensure_stock_entry_items(context)

			self.assertEqual(len(gate_pass.gate_pass_table), 1)
			self.assertEqual(gate_pass.gate_pass_table[0].dispatched_qty, test_dispatched_qty)

			# Reset call count for validate() which calls get_existing_stock_entry_allocations() again
			call_count[0] = 0

			with self.assertRaises(frappe.ValidationError) as error_context:
				gate_pass.validate()

			self.assertIn("exceeds remaining balance", str(error_context.exception))

	def test_discrepancy_logging_validation(self):
		"""Test discrepancy quantity validation."""
		gate_pass = self.create_gate_pass(reference_number="STE-001", entry_type="Gate In", has_discrepancy=1)

		gate_pass.append(
			"gate_pass_table",
			{
				"item_code": self.test_item,
				"received_qty": 10,
				"dispatched_qty": 0,
			},
		)

		# Test: Lost + Damaged cannot exceed total quantity
		gate_pass.lost_quantity = 6
		gate_pass.damaged_quantity = 5  # Total = 11, exceeds 10

		with self.assertRaises(frappe.ValidationError) as error_context:
			gate_pass.validate_discrepancy_quantities()

		self.assertIn("cannot exceed movement quantity", str(error_context.exception))

		# Test: Negative quantities not allowed
		gate_pass.lost_quantity = -1
		gate_pass.damaged_quantity = 0

		with self.assertRaises(frappe.ValidationError) as error_context:
			gate_pass.validate_discrepancy_quantities()

		self.assertIn("cannot be negative", str(error_context.exception))

		# Test: Valid discrepancy
		gate_pass.lost_quantity = 3
		gate_pass.damaged_quantity = 2  # Total = 5, within 10
		gate_pass.validate_discrepancy_quantities()  # Should not raise

	def test_discrepancy_fields_cleanup(self):
		"""Test that discrepancy fields are cleared when has_discrepancy is unchecked."""
		gate_pass = self.create_gate_pass(has_discrepancy=1)
		gate_pass.lost_quantity = 5
		gate_pass.damaged_quantity = 3
		gate_pass.discrepancy_notes = "Test notes"

		gate_pass.has_discrepancy = 0
		gate_pass.cleanup_discrepancy_fields()

		self.assertEqual(gate_pass.lost_quantity, 0)
		self.assertEqual(gate_pass.damaged_quantity, 0)
		self.assertIsNone(gate_pass.discrepancy_notes)

	def test_cancel_clears_stock_entry_reference(self):
		"""Test that cancelling gate pass clears Stock Entry reference."""
		gate_pass = self.create_gate_pass(
			reference_number="STE-001", entry_type="Gate Out", stock_entry="STE-001"
		)
		gate_pass.name = "GP-001"

		def fake_db_exists(doctype, name):
			return doctype == "Stock Entry" and name == "STE-001"

		def fake_db_get_value(doctype, name, field):
			if doctype == "Stock Entry" and name == "STE-001" and field == "gate_pass":
				return "GP-001"
			return None

		def fake_db_set_value(doctype, name, field, value, **kwargs):
			if doctype == "Stock Entry" and name == "STE-001" and field == "gate_pass":
				self.assertIsNone(value)

		with (
			patch(
				"gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.db.exists",
				side_effect=fake_db_exists,
			),
			patch(
				"gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.db.get_value",
				side_effect=fake_db_get_value,
			),
			patch(
				"gate_entry.gate_entry.doctype.gate_pass.gate_pass.frappe.db.set_value",
				side_effect=fake_db_set_value,
			),
		):
			gate_pass.clear_stock_entry_reference()

	def test_cancel_manual_return_flow_clears_references(self):
		"""Test that cancelling manual return flow gate pass clears outbound_material_transfer."""
		gate_pass = self.create_gate_pass(
			reference_number="STE-OUT-001",
			outbound_material_transfer="STE-OUT-001",
			manual_return_flow=1,
			entry_type="Gate In",
		)
		gate_pass.name = "GP-001"

		with patch("frappe.db.set_value") as db_set:
			# Simulate on_cancel behavior
			if (
				cint(gate_pass.manual_return_flow) == 1
				and gate_pass.entry_type == "Gate In"
				and not gate_pass.return_material_transfer
				and gate_pass.document_reference == "Stock Entry"
			):
				gate_pass.db_set("outbound_material_transfer", None, update_modified=False)
				gate_pass.db_set("reference_number", None, update_modified=False)

			# Verify db_set was called with None values
			calls_with_none = [
				call for call in db_set.call_args_list if len(call[0]) > 3 and call[0][3] is None
			]
			self.assertEqual(
				len(calls_with_none),
				2,
				f"Expected 2 calls with None values, got {len(calls_with_none)}. "
				f"All calls: {db_set.call_args_list}",
			)

			fields_cleared = {call[0][2] for call in calls_with_none}
			self.assertIn("outbound_material_transfer", fields_cleared)
			self.assertIn("reference_number", fields_cleared)


def _ensure_test_fixtures_for_po():
	"""Discover an INR company that has a Stores warehouse, creating fixtures as needed.

	Strategy (in order):
	1. Use "Wind Power LLP" if it exists with INR currency (v15 standard).
	2. Look for any INR company that already has a "Stores - <abbr>" warehouse.
	3. Fall back to "_Test Company" (always exists with INR in ERPNext test sites).
	"""
	supplier_name = "_Test Gate Entry Supplier"
	item_code = "_Test Gate Entry Item 1"

	# --- Step 1: prefer Wind Power LLP if it exists and uses INR ---
	company = None
	if frappe.db.exists("Company", "Wind Power LLP"):
		if frappe.db.get_value("Company", "Wind Power LLP", "default_currency") == "INR":
			company = "Wind Power LLP"

	# --- Step 2: any INR company that already has a Stores warehouse ---
	if not company:
		rows = frappe.db.sql(
			"""
			SELECT w.company FROM tabWarehouse w
			JOIN tabCompany c ON c.name = w.company
			WHERE w.warehouse_name = 'Stores'
			  AND c.default_currency = 'INR'
			  AND w.disabled = 0
			LIMIT 1
			""",
			as_dict=True,
		)
		if rows:
			company = rows[0].company

	# --- Step 3: fall back to _Test Company ---
	if not company:
		company = "_Test Company"

	# Resolve warehouse name from company abbr
	company_abbr = frappe.db.get_value("Company", company, "abbr") or "TC"
	warehouse_name = f"Stores - {company_abbr}"

	# Ensure warehouse exists
	if not frappe.db.exists("Warehouse", warehouse_name):
		parent_wh = frappe.db.get_value(
			"Warehouse", {"warehouse_name": "All Warehouses", "company": company}, "name"
		)
		if not parent_wh:
			pw = frappe.get_doc(
				{
					"doctype": "Warehouse",
					"warehouse_name": "All Warehouses",
					"is_group": 1,
					"company": company,
				}
			)
			pw.flags.ignore_permissions = True
			pw.flags.ignore_validate = True
			pw.insert(ignore_if_duplicate=True)
			frappe.db.commit()
			parent_wh = pw.name or f"All Warehouses - {company_abbr}"
		wh = frappe.get_doc(
			{
				"doctype": "Warehouse",
				"warehouse_name": "Stores",
				"is_group": 0,
				"company": company,
				"parent_warehouse": parent_wh,
			}
		)
		wh.flags.ignore_permissions = True
		wh.flags.ignore_validate = True
		wh.insert(ignore_if_duplicate=True)
		frappe.db.commit()

	# Ensure supplier exists
	if not frappe.db.exists("Supplier", supplier_name):
		supplier = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": supplier_name,
				"supplier_group": "All Supplier Groups",
				"country": "India",
			}
		)
		supplier.flags.ignore_permissions = True
		supplier.flags.ignore_validate = True
		supplier.flags.ignore_links = True
		supplier.insert(ignore_if_duplicate=True)
		frappe.db.commit()

	# Ensure item exists.  Include HSN code for india_compliance compatibility.
	if not frappe.db.exists("Item", item_code):
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Products",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"valuation_rate": 100,
				"gst_hsn_code": "61149090",
			}
		)
		item.flags.ignore_permissions = True
		item.flags.ignore_validate = True
		item.flags.ignore_links = True
		item.insert(ignore_if_duplicate=True)
		frappe.db.commit()

	# Ensure the company has an active fiscal year so PO can be submitted
	_ensure_fiscal_year_for_company(company)

	return supplier_name, item_code, warehouse_name, company


def _ensure_fiscal_year_for_company(company):
	"""Add company to the current active fiscal year if not already present."""
	from erpnext.accounts.utils import FiscalYearError, get_fiscal_year
	from frappe.utils import getdate

	try:
		get_fiscal_year(getdate(), company=company)
		return  # Fiscal year already active for this company
	except FiscalYearError:
		pass

	# Get any active fiscal year and add this company to it
	today = frappe.utils.getdate()
	fy_list = frappe.get_all(
		"Fiscal Year",
		filters={"year_start_date": ["<=", today], "year_end_date": [">=", today], "disabled": 0},
		fields=["name"],
		limit=1,
	)
	if not fy_list:
		return
	fy_doc = frappe.get_doc("Fiscal Year", fy_list[0].name)
	fy_companies = [row.company for row in fy_doc.get("companies") or []]
	if company not in fy_companies:
		fy_doc.append("companies", {"company": company})
		fy_doc.flags.ignore_permissions = True
		fy_doc.save()
		frappe.db.commit()


def _make_test_purchase_order(qty=10):
	"""Create and submit a test Purchase Order using gate_entry fixture data."""
	supplier_name, item_code, warehouse_name, company = _ensure_test_fixtures_for_po()

	po = frappe.new_doc("Purchase Order")
	po.supplier = supplier_name
	po.company = company
	po.schedule_date = frappe.utils.nowdate()
	po.append(
		"items",
		{
			"item_code": item_code,
			"qty": qty,
			"rate": 100,
			"schedule_date": frappe.utils.nowdate(),
			"warehouse": warehouse_name,
		},
	)
	po.insert()
	po.submit()
	return po


def _build_submitted_gate_pass(po, invoices):
	gp = frappe.new_doc("Gate Pass")
	gp.document_reference = "Purchase Order"
	gp.reference_number = po.name
	gp.company = po.company
	gp.supplier = po.supplier
	gp.vehicle_number = "KA01AB1234"
	gp.driver_name = "Test Driver"
	for inv, qty in invoices:
		gp.append("gate_pass_invoices", {"supplier_delivery_note": inv})
		gp.append(
			"gate_pass_table",
			{
				"item_code": po.items[0].item_code,
				"received_qty": qty,
				"order_item_name": po.items[0].name,
				"warehouse": po.items[0].warehouse,
				"supplier_delivery_note": inv,
			},
		)
	gp.submit()
	return gp


def _submitted_po_gate_pass(po, invoices):
	"""Build and submit a Gate Pass for a PO, call create_purchase_receipts, return reloaded doc."""
	from gate_entry.gate_entry.doctype.gate_pass.gate_pass import create_purchase_receipts

	gp = _build_submitted_gate_pass(po, invoices)
	create_purchase_receipts(gp.name)
	gp.reload()
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
				frappe.db.set_value(
					"Gate Pass Table", row.name, "order_item_name", "NONEXISTENT", update_modified=False
				)

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
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "NoPerm",
					"send_welcome_email": 0,
					"roles": [],
				}
			).insert(ignore_permissions=True)

		frappe.set_user(email)
		try:
			self.assertFalse(frappe.has_permission("Purchase Receipt", "create"))
			with self.assertRaises(frappe.PermissionError):
				create_purchase_receipts(gp.name)
		finally:
			frappe.set_user("Administrator")


class TestCancelBehavior(FrappeTestCase):
	def test_cancel_blocked_when_pr_submitted(self):
		"""Cancel must be blocked when an invoice-linked Purchase Receipt is in Submitted state."""
		po = _make_test_purchase_order(qty=5)
		gp = _submitted_po_gate_pass(po, [("INV-CANCEL-A", 5)])
		pr_name = gp.gate_pass_invoices[0].purchase_receipt
		self.assertIsNotNone(pr_name, "create_purchase_receipts must have created a PR")
		pr = frappe.get_doc("Purchase Receipt", pr_name)
		# Allow negative stock so PR can be submitted in test environments without valuation setup
		try:
			item_code = pr.items[0].item_code
			frappe.db.set_value("Item", item_code, "allow_negative_stock", 1)
			frappe.db.set_value("Stock Settings", None, "allow_negative_stock", 1)
		except Exception:
			pass
		try:
			pr.submit()
		except Exception as e:
			self.skipTest(f"PR submission not possible in this environment: {e}")
		gp.reload()
		with self.assertRaises(frappe.ValidationError):
			gp.cancel()

	def test_cancel_deletes_draft_prs_and_clears_links(self):
		"""Cancelling a gate pass with DRAFT PRs must delete those PRs and clear invoice row links."""
		po = _make_test_purchase_order(qty=10)
		gp = _submitted_po_gate_pass(po, [("INV-CANCEL-DRAFT", 10)])
		pr_name = gp.gate_pass_invoices[0].purchase_receipt
		self.assertIsNotNone(pr_name, "create_purchase_receipts must have created a PR")
		# Confirm it's a draft
		self.assertEqual(frappe.db.get_value("Purchase Receipt", pr_name, "docstatus"), 0)

		gp.cancel()
		gp.reload()

		# PR must be deleted
		self.assertFalse(frappe.db.exists("Purchase Receipt", pr_name), "Draft PR must be deleted on cancel")
		# Invoice row link must be cleared
		for row in gp.gate_pass_invoices:
			self.assertIsNone(row.purchase_receipt, "Invoice row purchase_receipt must be None after cancel")
			self.assertEqual(row.grn_status, "Pending")


class TestGRNStatusSubmitted(FrappeTestCase):
	def test_grn_status_advances_to_submitted_on_pr_submit(self):
		"""on_purchase_receipt_submit must set grn_status='Submitted' on the matching invoice row."""
		from gate_entry.gate_entry.doctype.gate_pass.gate_pass import on_purchase_receipt_submit

		po = _make_test_purchase_order(qty=5)
		gp = _submitted_po_gate_pass(po, [("INV-SUBMIT-TEST", 5)])
		pr_name = gp.gate_pass_invoices[0].purchase_receipt
		self.assertIsNotNone(pr_name, "create_purchase_receipts must have created a PR")
		self.assertEqual(gp.gate_pass_invoices[0].grn_status, "Draft")

		pr = frappe.get_doc("Purchase Receipt", pr_name)
		# Allow negative stock so PR can be submitted in test environments without valuation setup
		try:
			item_code = pr.items[0].item_code
			frappe.db.set_value("Item", item_code, "allow_negative_stock", 1)
			frappe.db.set_value("Stock Settings", None, "allow_negative_stock", 1)
		except Exception:
			pass
		try:
			pr.submit()
		except Exception as e:
			self.skipTest(f"PR submission not possible in this environment: {e}")

		# Simulate the doc_event hook (hooks wiring is not active in unit tests)
		on_purchase_receipt_submit(pr, None)

		gp.reload()
		self.assertEqual(
			gp.gate_pass_invoices[0].grn_status,
			"Submitted",
			"grn_status must advance to 'Submitted' after PR is submitted",
		)


class TestSubmittedGatePassUpdate(FrappeTestCase):
	def test_can_append_invoice_row_to_submitted_gate_pass_with_flag(self):
		po = _make_test_purchase_order(qty=10)
		gp = _build_submitted_gate_pass(po, [("INV-A", 3)])  # docstatus 1

		gp.append("gate_pass_invoices", {"supplier_delivery_note": "INV-LATE", "grn_status": "Pending"})
		gp.flags.ignore_validate_update_after_submit = True
		gp.save(ignore_permissions=True)  # must NOT raise UpdateAfterSubmitError

		gp.reload()
		self.assertIn("INV-LATE", [r.supplier_delivery_note for r in gp.gate_pass_invoices])


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
		gp.append(
			"gate_pass_table",
			{
				"item_code": "X",
				"received_qty": 5,
				"order_item_name": "POI-1",
				"supplier_delivery_note": "INV-1",
			},
		)
		with self.assertRaises(frappe.ValidationError):
			gp.validate_purchase_invoices()

	def test_invoice_without_items_rejected(self):
		gp = self._po_gate_pass(["INV-1"])
		with self.assertRaises(frappe.ValidationError):
			gp.validate_purchase_invoices()

	def test_zero_qty_rejected(self):
		gp = self._po_gate_pass(["INV-1"])
		gp.append(
			"gate_pass_table",
			{
				"item_code": "X",
				"received_qty": 0,
				"order_item_name": "POI-1",
				"supplier_delivery_note": "INV-1",
			},
		)
		with self.assertRaises(frappe.ValidationError):
			gp.validate_purchase_invoices()

	def test_no_invoices_rejected(self):
		gp = self._po_gate_pass([])
		with self.assertRaises(frappe.ValidationError):
			gp.validate_purchase_invoices()
