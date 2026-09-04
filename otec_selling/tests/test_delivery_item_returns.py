import json
from pathlib import Path
from unittest import TestCase

import frappe
from frappe.tests import IntegrationTestCase

from otec_selling.delivery_item_returns import (
	PRINT_MARKER,
	SYNC_SCRIPT,
	VALIDATE_SCRIPT,
	apply_balances,
	enhance_print,
	event_script,
	quantities,
	setup_delivery_item_returns,
)


class TestDeliveryItemReturnMath(TestCase):
	def test_partial_full_and_cancelled_return(self):
		self.assertEqual(quantities(10, 1, 3), (3, 7))
		self.assertEqual(quantities(10, 1, 10), (10, 0))
		self.assertEqual(quantities(10, 1, 0), (0, 10))

	def test_different_return_uom(self):
		self.assertEqual(quantities(10, 12, 18), (1.5, 8.5))

	def test_does_not_hide_over_returned_data(self):
		self.assertEqual(quantities(10, 1, 11), (11, -1))

	def test_all_existing_print_templates_and_idempotence(self):
		formats = json.loads((Path(__file__).parents[1] / "fixtures" / "print_format.json").read_text())
		for format in formats:
			if format["doc_type"] != "Delivery Note":
				continue
			original = format["html"]
			updated = enhance_print(original)
			self.assertIn(PRINT_MARKER, updated)
			self.assertEqual(enhance_print(updated), updated)
			if format["name"] == "DR 2026":
				self.assertIn("url_token != saved_token", updated)
				self.assertIn('doc.status != "To Bill"', updated)


class TestDeliveryItemReturnConfiguration(IntegrationTestCase):
	def test_fields_and_print_setup(self):
		setup_delivery_item_returns()
		setup_delivery_item_returns()
		for name in ("custom_returned_qty", "custom_client_retained_qty"):
			field = frappe.get_meta("Delivery Note Item").get_field(name)
			self.assertTrue(field.read_only and field.no_copy and field.in_list_view)
		for name in ("Delivery Note Standard", "Delivery Note with Item Image", "DR 2026"):
			self.assertEqual(frappe.db.get_value("Print Format", name, "html").count(PRINT_MARKER), 1)

	def test_only_submitted_physical_returns_and_original_row_links(self):
		# Minimal SQL fixtures live only in the rollback-isolated CI database.
		prefix = "_TestReturnDisplay-" + frappe.generate_hash(length=8)
		doc = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"name": prefix,
				"docstatus": 1,
				"is_return": 0,
				"items": [
					{"name": prefix + "-a", "item_code": "same-item", "qty": 10, "conversion_factor": 2},
					{"name": prefix + "-b", "item_code": "same-item", "qty": 5, "conversion_factor": 1},
				],
			}
		)
		for suffix, status, against, detail, qty in (
			("part1", 1, prefix, prefix + "-a", -4),
			("part2", 1, prefix, prefix + "-a", -2),
			("draft", 0, prefix, prefix + "-a", -10),
			("cancel", 2, prefix, prefix + "-a", -10),
			("other", 1, prefix + "-other", prefix + "-a", -10),
		):
			name = prefix + suffix
			frappe.db.sql(
				"INSERT INTO `tabDelivery Note` (name,docstatus,is_return,return_against) VALUES (%s,%s,1,%s)",
				(name, status, against),
			)
			frappe.db.sql(
				"INSERT INTO `tabDelivery Note Item` (name,parent,parenttype,parentfield,dn_detail,stock_qty) VALUES (%s,%s,'Delivery Note','items',%s,%s)",
				(name + "-row", name, detail, qty),
			)
		apply_balances(doc)
		self.assertEqual((doc.items[0].custom_returned_qty, doc.items[0].custom_client_retained_qty), (3, 7))
		self.assertEqual((doc.items[1].custom_returned_qty, doc.items[1].custom_client_retained_qty), (0, 5))
		frappe.db.sql("UPDATE `tabDelivery Note` SET docstatus=2 WHERE name=%s", prefix + "part2")
		apply_balances(doc)
		self.assertEqual((doc.items[0].custom_returned_qty, doc.items[0].custom_client_retained_qty), (2, 8))
		self.assertEqual(doc.items[0].qty, 10)
		from frappe.utils.safe_exec import safe_exec

		safe_exec(event_script(VALIDATE_SCRIPT), _locals={"doc": doc}, restrict_commit_rollback=True)
		self.assertEqual(doc.items[0].custom_client_retained_qty, 8)
		frappe.db.sql("INSERT INTO `tabDelivery Note` (name,docstatus,is_return) VALUES (%s,1,0)", prefix)
		for row in doc.items:
			frappe.db.sql(
				"INSERT INTO `tabDelivery Note Item` (name,parent,parenttype,parentfield,qty,conversion_factor) VALUES (%s,%s,'Delivery Note','items',%s,%s)",
				(row.name, prefix, row.qty, row.conversion_factor),
			)
		safe_exec(
			event_script(SYNC_SCRIPT),
			_locals={"doc": frappe._dict(is_return=1, return_against=prefix)},
			restrict_commit_rollback=True,
		)
		self.assertEqual(
			frappe.db.get_value("Delivery Note Item", prefix + "-a", "custom_client_retained_qty"), 8
		)

	def test_return_documents_do_not_display_negative_client_balance(self):
		doc = frappe.get_doc({"doctype": "Delivery Note", "is_return": 1, "items": [{"qty": -3}]})
		apply_balances(doc)
		self.assertEqual(doc.items[0].custom_client_retained_qty, 0)

	def test_unsubmitted_delivery_is_not_yet_client_retained(self):
		doc = frappe.get_doc(
			{
				"doctype": "Delivery Note",
				"docstatus": 0,
				"is_return": 0,
				"items": [{"qty": 10, "conversion_factor": 1}],
			}
		)
		apply_balances(doc)
		self.assertEqual(doc.items[0].custom_client_retained_qty, 0)
