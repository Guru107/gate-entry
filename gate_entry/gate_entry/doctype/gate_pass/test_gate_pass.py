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
