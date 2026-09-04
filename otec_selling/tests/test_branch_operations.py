"""Policy regression tests; no real users or transactions are changed."""

from contextlib import ExitStack
from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from otec_selling import branch_operations as policy
from otec_selling.branch_operations_setup import (
	MARKER,
	WORKFLOW_ROLE,
	commercial_transitions,
	return_receipt_routing,
	setup_branch_operations,
	visibility_extension,
)


class TestBranchPolicy(TestCase):
	def setUp(self):
		self.stack = ExitStack()
		self.addCleanup(self.stack.close)
		self.hierarchy = frappe._dict(name="test-hierarchy", position="Supervisor")
		self.stack.enter_context(patch.object(policy, "hierarchy_for", return_value=self.hierarchy))
		self.stack.enter_context(patch.object(policy.frappe, "get_roles", return_value=["Sales Supervisor"]))
		self.stack.enter_context(
			patch.object(policy, "company_branch_scope", return_value=({"Co"}, {"Branch"}))
		)
		self.stack.enter_context(patch.object(policy, "scopes", return_value={"Team B", "Team C"}))
		self.stack.enter_context(patch.object(policy.frappe.db, "get_value", return_value="Local"))
		self.stack.enter_context(
			patch.object(
				policy, "warehouse_within", side_effect=lambda warehouse, root, company: warehouse == "Local"
			)
		)
		self.orders = self.stack.enter_context(patch.object(policy, "source_orders", return_value=[]))
		self.explicit = self.stack.enter_context(
			patch.object(policy, "explicit_warehouse_access", return_value=False)
		)

	def document(self, **kwargs):
		values = dict(
			doctype="Pick List",
			company="Co",
			custom_branch="Branch",
			purpose="Delivery",
			locations=[frappe._dict(warehouse="Local")],
			docstatus=0,
			owner="rep",
			custom_sales_team_group="Team A",
		)
		values.update(kwargs)
		return frappe._dict(values)

	def test_entire_branch_fulfillment_without_default_team(self):
		self.assertTrue(policy.can_operate(self.document(), "manager", submitting=True))
		self.assertTrue(policy.has_permission(self.document(), "manager", "read"))

	def test_other_branch_and_missing_branch_denied(self):
		for branch in ("Elsewhere", None):
			self.assertFalse(policy.can_operate(self.document(custom_branch=branch), "manager"))

	def test_central_stock_denied_without_explicit_assignment(self):
		self.assertFalse(
			policy.can_operate(self.document(locations=[frappe._dict(warehouse="Central")]), "manager")
		)

	def test_source_central_route_cannot_be_bypassed_by_header(self):
		self.orders.return_value = [
			frappe._dict(company="Co", branch="Branch", docstatus=1, custom_central_fulfillment=1)
		]
		self.assertFalse(policy.can_operate(self.document(custom_central_fulfillment=0), "manager"))
		self.explicit.return_value = True
		self.assertTrue(policy.can_operate(self.document(), "manager"))

	def test_stock_transfer_is_not_sales_fulfillment(self):
		self.assertFalse(policy.can_operate(self.document(purpose="Material Transfer"), "manager"))

	def test_submit_requires_actual_warehouses(self):
		self.assertFalse(policy.can_operate(self.document(locations=[]), "manager", submitting=True))
		self.assertFalse(
			policy.can_operate(self.document(locations=[frappe._dict()]), "manager", submitting=True)
		)

	def test_branch_receipt_of_originally_central_order(self):
		self.orders.return_value = [
			frappe._dict(company="Co", branch="Branch", docstatus=1, custom_central_fulfillment=1)
		]
		doc = self.document(
			doctype="Delivery Note",
			branch="Branch",
			is_return=1,
			items=[frappe._dict(warehouse="Local")],
			custom_fulfillment_warehouse="Central",
		)
		self.assertTrue(policy.can_operate(doc, "manager", submitting=True))

	def test_commercial_scope_still_respects_multiple_managed_teams(self):
		for team in ("Team B", "Team C"):
			self.assertTrue(
				policy.in_commercial_scope(
					self.document(custom_sales_team_group=team), self.hierarchy, "manager"
				)
			)
		self.assertFalse(policy.in_commercial_scope(self.document(), self.hierarchy, "manager"))
		self.assertTrue(policy.in_commercial_scope(self.document(owner="manager"), self.hierarchy, "manager"))

	def test_approved_other_team_order_read_only(self):
		doc = self.document(doctype="Sales Order", branch="Branch", docstatus=1)
		self.assertTrue(policy.has_permission(doc, "manager", "read"))
		self.assertFalse(policy.has_permission(doc, "manager", "write"))

	def test_self_approval_does_not_remove_exception_conditions(self):
		rows = [
			{
				"state": "Draft",
				"action": "Approve",
				"allowed": "Sales Supervisor",
				"next_state": "Approved",
				"condition": 'doc.custom_creator_hierarchy_position == "Supervisor"',
			}
		]
		result = commercial_transitions(rows, "Approved", "For Business Owner Approval")
		self.assertEqual(result[0]["allow_self_approval"], 1)
		self.assertIn("requires_business_owner_approval == 0", result[0]["condition"])
		self.assertIn(rows[0]["condition"], result[0]["condition"])
		self.assertTrue(any(row["next_state"] == "For Business Owner Approval" for row in result))
		self.assertEqual(result, commercial_transitions(result, "Approved", "For Business Owner Approval"))

	def test_server_script_extension_compiles(self):
		for doctype in ("Sales Order", "Pick List", "Delivery Note"):
			compile(visibility_extension(doctype), "visibility-extension", "exec")

	def test_return_routing_change_is_narrow_and_idempotent(self):
		source = (
			"if not sales_order_values.custom_central_fulfillment:\n    continue\n# DR paper checks remain"
		)
		result = return_receipt_routing(source)
		self.assertIn('if doc.get("is_return") or not sales_order_values.custom_central_fulfillment:', result)
		self.assertIn("# DR paper checks remain", result)
		self.assertEqual(result, return_receipt_routing(result))

	def test_reservation_requires_matching_submitted_pick(self):
		pick = self.document(
			docstatus=1,
			locations=[
				frappe._dict(
					name="row",
					warehouse="Local",
					item_code="item",
					sales_order="order",
					sales_order_item="order-row",
				)
			],
		)
		doc = frappe._dict(
			doctype="Stock Reservation Entry",
			company="Co",
			from_voucher_type="Pick List",
			from_voucher_no="pick",
			from_voucher_detail_no="row",
			voucher_type="Sales Order",
			voucher_no="order",
			voucher_detail_no="order-row",
			warehouse="Local",
			item_code="item",
		)
		with (
			patch.object(frappe.db, "exists", return_value=True),
			patch.object(frappe, "get_doc", return_value=pick),
		):
			self.assertTrue(policy.reservation_in_scope(doc, "manager"))
			doc.warehouse = "Central"
			self.assertFalse(policy.reservation_in_scope(doc, "manager"))
			doc.warehouse = "Local"
			pick.docstatus = 0
			self.assertFalse(policy.reservation_in_scope(doc, "manager"))
			doc.from_voucher_type = "Purchase Receipt"
			self.assertFalse(policy.reservation_in_scope(doc, "manager"))

	def test_unsaved_bundle_allows_only_local_sales_packing(self):
		doc = frappe._dict(company="Co", voucher_type="Pick List", warehouse="Local")
		self.assertTrue(policy.bundle_in_scope(doc, "manager"))
		doc.warehouse = "Central"
		self.assertFalse(policy.bundle_in_scope(doc, "manager"))
		doc.warehouse = "Local"
		doc.voucher_type = "Stock Entry"
		self.assertFalse(policy.bundle_in_scope(doc, "manager"))

	def test_self_approval_guard_and_audit(self):
		doc = self.document(
			doctype="Sales Order",
			branch="Branch",
			owner="manager",
			workflow_state="Approved for Fulfillment",
			requires_business_owner_approval=0,
			get_doc_before_save=lambda: None,
		)
		with patch.object(policy.frappe, "session", frappe._dict(user="manager")):
			policy.validate_approval(doc, "before_submit")
			self.assertEqual(doc.custom_commercial_approved_by, "manager")
			self.assertEqual(doc.custom_self_approved, 1)
			doc.requires_business_owner_approval = 1
			with self.assertRaises(frappe.PermissionError):
				policy.validate_approval(doc, "before_submit")

	def test_business_owner_queue_cannot_be_self_released(self):
		doc = self.document(
			doctype="Sales Order",
			branch="Branch",
			owner="manager",
			workflow_state="Approved for Fulfillment",
			requires_business_owner_approval=0,
		)
		previous = self.document(
			doctype="Sales Order",
			branch="Branch",
			owner="manager",
			workflow_state="For Business Owner Approval",
		)
		doc.get_doc_before_save = lambda: previous
		with patch.object(policy.frappe, "session", frappe._dict(user="manager")):
			with self.assertRaises(frappe.PermissionError):
				policy.validate_approval(doc, "before_submit")

	def test_business_owner_with_sales_roles_keeps_exception_authority(self):
		self.hierarchy.position = "Business Owner"
		doc = self.document(
			doctype="Sales Order",
			branch="Elsewhere",
			owner="rep",
			workflow_state="Approved for Fulfillment",
			requires_business_owner_approval=1,
			get_doc_before_save=lambda: None,
		)
		with (
			patch.object(policy.frappe, "session", frappe._dict(user="boss")),
			patch.object(policy.frappe, "get_roles", return_value=["Business Owner", "Sales Supervisor"]),
		):
			self.assertTrue(policy.has_permission(doc, "boss", "write"))
			policy.validate_commercial_write(doc)
			policy.validate_approval(doc, "before_submit")
			self.assertEqual(doc.custom_commercial_approved_by, "boss")

	def test_previous_branch_prevents_reassignment_bypass(self):
		doc = self.document(get_doc_before_save=lambda: self.document(custom_branch="Elsewhere"))
		with patch.object(policy.frappe, "session", frappe._dict(user="manager")):
			with self.assertRaises(frappe.PermissionError):
				policy.validate_operation(doc)


class TestBranchPolicyInstallation(IntegrationTestCase):
	def test_visibility_runs_in_restricted_server_script_environment(self):
		from frappe.utils.safe_exec import safe_exec

		def rows(doctype, **kwargs):
			if doctype == "Sales Access Hierarchy":
				return [frappe._dict(name="test", position="Team Leader", company="Co", branch="Branch")]
			if doctype == "Has Role":
				return ["Sales Team Leader"]
			return []

		for doctype in ("Sales Order", "Pick List", "Delivery Note"):
			context = {"user": "test@example.invalid", "conditions": "1 = 0"}
			with patch.object(frappe, "get_all", side_effect=rows):
				safe_exec(visibility_extension(doctype), _locals=context)
			self.assertIn(" OR (", context["conditions"])
			self.assertIn("Branch", context["conditions"])
			if doctype == "Sales Order":
				self.assertIn("`docstatus` = 1", context["conditions"])

	def test_installation_is_idempotent(self):
		setup_branch_operations()
		setup_branch_operations()
		for doctype in ("Sales Order", "Pick List", "Delivery Note"):
			script = frappe.db.get_value("Server Script", policy.QUERY_SCRIPTS[doctype], "script")
			self.assertEqual(script.count(MARKER), 1)
		for doctype in ("Pick List", "Delivery Note"):
			for role in policy.MANAGERS.values():
				perms = frappe.db.get_value(
					"Custom DocPerm",
					{"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
					["read", "write", "create", "submit"],
					as_dict=True,
				)
				self.assertTrue(all(perms.values()))
		self.assertFalse(frappe.db.exists("Custom DocPerm", {"role": WORKFLOW_ROLE}))
		self.assertFalse(frappe.db.exists("DocPerm", {"role": WORKFLOW_ROLE}))
		self.assertTrue(frappe.db.exists("Workspace", "Branch Fulfillment"))

	def test_approval_and_operator_audit_fields_exist(self):
		for doctype in policy.APPROVED:
			self.assertTrue(frappe.get_meta(doctype).has_field("custom_self_approved"))
		for doctype in ("Pick List", "Delivery Note"):
			self.assertTrue(frappe.get_meta(doctype).has_field("custom_fulfillment_operator"))
