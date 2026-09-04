from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.safe_exec import get_safe_globals, safe_exec

from otec_selling.return_dashboards import (
	API_NAME,
	STAGES,
	api_script,
	merge_return_icons,
	setup_return_dashboards,
)


class TestReturnDashboards(IntegrationTestCase):
	def test_saved_layout_merge_preserves_customization_and_is_idempotent(self):
		before = [{"label": "Selling", "hidden": 1, "idx": 9}]
		icons = [{"label": "My Sales Returns", "hidden": 0}, {"label": "Unrelated"}]
		after = merge_return_icons(before, icons)
		self.assertEqual(after[:1], before)
		self.assertEqual(len(after), 2)
		self.assertEqual(after, merge_return_icons(after, icons))
		self.assertEqual(before, [{"label": "Selling", "hidden": 1, "idx": 9}])

	def run_api(self, mode="my", teams=None, **filters):
		actor = "dashboard-test@example.invalid"
		hierarchy = frappe._dict(
			name="Test Hierarchy",
			user=actor,
			position="Team Leader",
			company="Company",
			branch="Branch",
			sales_team_group=None,
		)

		def metadata(doctype, **kwargs):
			if doctype == "Sales Access Hierarchy":
				return [hierarchy]
			if doctype == "Has Role":
				return ["Sales Team Leader"]
			if doctype == "Sales Hierarchy Team Access":
				return [frappe._dict(sales_team_group=team) for team in (teams or [])]
			if doctype in ("Sales Hierarchy Company Access", "Sales Hierarchy Branch Access"):
				return []
			self.fail("Unexpected unrestricted read: " + doctype)

		def transactions(doctype, **kwargs):
			self.assertEqual(doctype, "Sales Return Request")
			if kwargs["fields"] == [{"COUNT": "name", "as": "total"}]:
				return [frappe._dict(total=0)]
			return []

		response = {"type": "json"}
		# Replace only the script's namespace, not Frappe's internal metadata reads.
		globals_for_script = get_safe_globals()
		queries = Mock(side_effect=transactions)
		globals_for_script.frappe.update(
			session=frappe._dict(user=actor),
			form_dict=frappe._dict(mode=mode, **filters),
			response=response,
			get_all=Mock(side_effect=metadata),
			get_list=queries,
		)
		with patch("frappe.utils.safe_exec.get_safe_globals", return_value=globals_for_script):
			safe_exec(api_script(), restrict_commit_rollback=True)
			return response["message"], queries.call_args_list

	def test_my_counts_and_rows_use_ownership_and_permission_aware_reads(self):
		result, calls = self.run_api()
		self.assertEqual(len(result["cards"]), len(STAGES) - 1)
		for call in calls:
			self.assertEqual(
				{row[0] for row in call.kwargs["or_filters"]}, {"owner", "sales_user", "requested_by"}
			)
		self.assertEqual(calls[-1].kwargs["limit_page_length"], 20)

	def test_multiple_managed_teams_without_default_team(self):
		result, calls = self.run_api(mode="team", teams=["B", "C"])
		self.assertEqual(result["teams"], ["B", "C"])
		for call in calls:
			if ["sales_team_group", "is", "not set"] not in call.kwargs["filters"]:
				self.assertIn(["sales_team_group", "in", ["B", "C"]], call.kwargs["filters"])
			self.assertIn(["company", "in", ["Company"]], call.kwargs["filters"])
			self.assertIn(["branch", "in", ["Branch"]], call.kwargs["filters"])
			self.assertEqual(call.kwargs["or_filters"], [])

	def test_missing_teams_fail_closed(self):
		result, calls = self.run_api(mode="team")
		self.assertTrue(result["notice"])
		for call in calls:
			self.assertIn(["name", "=", ""], call.kwargs["filters"])

	def test_unassigned_queue_is_separate_and_company_branch_scoped(self):
		result, calls = self.run_api(mode="team", teams=["B", "C"], stage="unassigned")
		filters = calls[-1].kwargs["filters"]
		self.assertIn(["sales_team_group", "is", "not set"], filters)
		self.assertIn(["company", "in", ["Company"]], filters)
		self.assertIn(["branch", "in", ["Branch"]], filters)
		self.assertNotIn(["sales_team_group", "in", ["B", "C"]], filters)
		self.assertIn("excluded from team totals", result["notice"])
		with self.assertRaises(frappe.ValidationError):
			self.run_api(mode="my", stage="unassigned")

	def test_unassigned_team_cannot_be_requested(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_api(mode="team", teams=["B"], team="Other Team")

	def test_date_filter_targets_request_date_and_is_inclusive(self):
		_, calls = self.run_api(date_from="2026-09-01", date_to="2026-09-05")
		date_filters = [row for row in calls[-1].kwargs["filters"] if row[0] == "request_date"]
		self.assertEqual([row[1] for row in date_filters], [">=", "<="])
		with self.assertRaises(frappe.ValidationError):
			self.run_api(date_from="2026-09-05", date_to="2026-09-01")

	def test_invalid_scope_and_status_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_api(mode="all")
		with self.assertRaises(frappe.ValidationError):
			self.run_api(stage="arbitrary")

	def test_install_is_idempotent(self):
		setup_return_dashboards()
		setup_return_dashboards()
		self.assertEqual(frappe.db.count("Server Script", {"api_method": API_NAME}), 1)
		for title in ("My Sales Returns", "Team Sales Returns"):
			workspace = frappe.get_doc("Workspace", title)
			self.assertEqual(len(workspace.custom_blocks), 1)
			# Frappe's Block.make matches content.custom_block_name against row.label.
			self.assertEqual(workspace.custom_blocks[0].label, "OTEC " + title)
			self.assertTrue(frappe.db.exists("Custom HTML Block", "OTEC " + title))
			sidebar = frappe.get_doc("Workspace Sidebar", title)
			self.assertEqual(
				sum(row.link_type == "Workspace" and row.link_to == title for row in sidebar.items), 1
			)
			icon = frappe.get_doc("Desktop Icon", title)
			self.assertEqual(icon.link_type, "Workspace Sidebar")
			self.assertEqual(icon.link_to, title)
			self.assertEqual(icon.standard, 1)
			self.assertFalse(icon.hidden)
			self.assertEqual({r.role for r in icon.roles}, {r.role for r in workspace.roles})

	def test_native_query_builder_supports_dashboard_aggregate(self):
		result = frappe.get_list(
			"Sales Return Request", fields=[{"COUNT": "name", "as": "total"}], limit_page_length=1
		)
		self.assertIn("total", result[0])
