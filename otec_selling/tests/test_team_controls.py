from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe.utils.safe_exec import get_safe_globals, safe_exec

from otec_selling.team_controls import CORE


class Record(frappe._dict):
	def set(self, key, value):
		self[key] = value

	def get_doc_before_save(self):
		return self.get("previous")


class TestTeamControls(TestCase):
	def record(self, **values):
		doc = Record(
			doctype="Sales Order",
			company="Co",
			branch="Branch",
			owner="manager",
			custom_sales_user="manager",
			custom_sales_team_group="",
			docstatus=0,
			items=[],
		)
		doc.update(values)
		return doc

	def run_guard(self, doc, teams=("B", "C"), sources=None, required=False):
		namespace = get_safe_globals()

		def metadata(dt, **kwargs):
			if dt == "Sales Team Group":
				return list(teams)
			if dt == "Has Role":
				return ["Sales Team Leader"]
			if dt == "Sales Access Hierarchy":
				return [
					frappe._dict(
						name="H", position="Team Leader", company="Co", branch="Branch", sales_team_group=None
					)
				]
			if dt == "Sales Hierarchy Team Access":
				return [frappe._dict(sales_team_group=t) for t in teams]
			return []

		namespace.frappe.update(
			session=frappe._dict(user="manager"),
			get_all=metadata,
			get_doc=Mock(side_effect=lambda dt, name: sources[name]),
			throw=Mock(side_effect=frappe.ValidationError),
		)
		with patch("frappe.utils.safe_exec.get_safe_globals", return_value=namespace):
			safe_exec(CORE + "\nvalidate_team(doc, required=" + str(required) + ")", _locals={"doc": doc})
		return doc

	def test_multi_team_draft_stays_blank(self):
		self.assertFalse(self.run_guard(self.record()).custom_sales_team_group)

	def test_multi_team_submission_requires_selection(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_guard(self.record(docstatus=1), required=True)

	def test_single_team_autofills(self):
		self.assertEqual(self.run_guard(self.record(), teams=("B",)).custom_sales_team_group, "B")

	def test_out_of_scope_team_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_guard(self.record(custom_sales_team_group="Other"))

	def test_self_approval_requires_team(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_guard(self.record(workflow_state="Approved for Fulfillment"))

	def test_legacy_approved_draft_cannot_submit_blank(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_guard(
				self.record(docstatus=1, previous=self.record(workflow_state="Approved for Fulfillment")),
				required=True,
			)

	def test_source_team_not_processor_team(self):
		doc = self.record(doctype="Delivery Note", items=[frappe._dict(against_sales_order="SO")])
		source = self.record(custom_sales_team_group="A", docstatus=1)
		self.assertEqual(self.run_guard(doc, sources={"SO": source}).custom_sales_team_group, "A")

	def test_mixed_source_teams_rejected(self):
		doc = self.record(
			doctype="Pick List", locations=[frappe._dict(sales_order="A"), frappe._dict(sales_order="B")]
		)
		with self.assertRaises(frappe.ValidationError):
			self.run_guard(
				doc,
				sources={
					"A": self.record(custom_sales_team_group="A"),
					"B": self.record(custom_sales_team_group="B"),
				},
			)

	def test_missing_source_team_cannot_be_overridden(self):
		doc = self.record(
			doctype="Delivery Note",
			custom_sales_team_group="B",
			items=[frappe._dict(against_sales_order="SO")],
		)
		with self.assertRaises(frappe.ValidationError):
			self.run_guard(doc, sources={"SO": self.record()})

	def test_return_inherits_original_team(self):
		doc = self.record(
			doctype="Sales Return Request",
			source_doctype="Delivery Note",
			source_document="DN",
			sales_team_group="",
		)
		self.assertEqual(
			self.run_guard(
				doc, sources={"DN": self.record(doctype="Delivery Note", custom_sales_team_group="C")}
			).sales_team_group,
			"C",
		)

	def test_submitted_ownership_locked_but_status_updates_allowed(self):
		old = self.record(docstatus=1, custom_sales_team_group="B")
		self.run_guard(self.record(docstatus=1, custom_sales_team_group="B", previous=old))
		with self.assertRaises(frappe.ValidationError):
			self.run_guard(self.record(docstatus=1, custom_sales_team_group="C", previous=old))
