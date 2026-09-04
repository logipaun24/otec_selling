"""Idempotent policy migration, applied AFTER fixtures on install and migrate.

Operational assignments remain site data. No usernames or passwords are fixtures.
"""

import copy
import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from otec_selling.branch_operations import MANAGERS, QUERY_SCRIPTS

WORKFLOW_ROLE = "Fulfillment Workflow User"
WORKFLOW_MEMBERS = {"Sales User", "Sales Team Leader", "Sales Supervisor", "Stock User", "Stock Manager"}
MARKER = "# OTEC BRANCH FULFILLMENT SCOPE V1"


def return_receipt_routing(script):
	"""Return receipts follow their receiving warehouse, not original dispatch root."""
	return script.replace(
		"if not sales_order_values.custom_central_fulfillment:",
		'if doc.get("is_return") or not sales_order_values.custom_central_fulfillment:',
	)


def visibility_extension(doctype):
	branch_field = "custom_branch" if doctype == "Pick List" else "branch"
	status = " AND `tabSales Order`.`docstatus` = 1" if doctype == "Sales Order" else ""
	return f"""
{MARKER}
# Only explicit company/branch assignments expand fulfillment visibility.
# Team boundaries remain in the original commercial query above.
branch_actor_user = user or frappe.session.user
branch_actor_rows = frappe.get_all(
    "Sales Access Hierarchy", filters={{"user": branch_actor_user, "active": 1}},
    fields=["name", "position", "company", "branch"], limit=2
)
if len(branch_actor_rows) == 1 and branch_actor_user != "Guest":
    branch_actor = branch_actor_rows[0]
    branch_roles = frappe.get_all("Has Role", filters={{"parent": branch_actor_user, "parenttype": "User"}}, pluck="role")
    if ((branch_actor.position == "Team Leader" and "Sales Team Leader" in branch_roles) or
        (branch_actor.position == "Supervisor" and "Sales Supervisor" in branch_roles)):
        branch_companies = []
        branch_names = []
        if branch_actor.company:
            branch_companies.append(branch_actor.company)
        if branch_actor.branch:
            branch_names.append(branch_actor.branch)
        for scope_row in frappe.get_all("Sales Hierarchy Company Access", filters={{
            "parent": branch_actor.name, "parenttype": "Sales Access Hierarchy", "parentfield": "allowed_companies"
        }}, fields=["company"]):
            if scope_row.company:
                branch_companies.append(scope_row.company)
        for scope_row in frappe.get_all("Sales Hierarchy Branch Access", filters={{
            "parent": branch_actor.name, "parenttype": "Sales Access Hierarchy", "parentfield": "allowed_branches"
        }}, fields=["branch"]):
            if scope_row.branch:
                branch_names.append(scope_row.branch)
        if branch_companies and branch_names:
            branch_company_sql = ", ".join([frappe.db.escape(value) for value in branch_companies])
            branch_name_sql = ", ".join([frappe.db.escape(value) for value in branch_names])
            branch_operation_sql = ("`tab{doctype}`.`company` IN (" + branch_company_sql +
                ") AND `tab{doctype}`.`{branch_field}` IN (" + branch_name_sql + "){status}")
            conditions = "(" + (conditions or "1 = 0") + ") OR (" + branch_operation_sql + ")"
"""


def _grant(doctype, role, rights):
	if not frappe.db.exists("DocType", doctype):
		return
	if not frappe.db.exists(
		"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0}
	):
		add_permission(doctype, role)
	for right in rights:
		update_permission_property(doctype, role, 0, right, 1, validate=False)
	frappe.clear_cache(doctype=doctype)


def commercial_transitions(transitions, approved, pending_owner):
	"""Preserve existing conditions and strengthen terminal approval thresholds."""
	result = copy.deepcopy(transitions)
	for row in result:
		if row.get("allowed") not in MANAGERS.values() or row.get("action") not in (
			"Approve",
			"Approve Return",
		):
			continue
		row["allow_self_approval"] = 1
		if row.get("next_state") == approved:
			condition = row.get("condition") or "True"
			if "requires_business_owner_approval" not in condition:
				row["condition"] = f"({condition}) and doc.requires_business_owner_approval == 0"
	# Both TL and Supervisor must be able to route their own exceptions upwards.
	for role, position in ((role, position) for position, role in MANAGERS.items()):
		state = "RMA Draft" if approved == "RMA Approved" else "Draft"
		if not any(
			row.get("state") == state
			and row.get("allowed") == role
			and row.get("next_state") == pending_owner
			for row in result
		):
			creator = (
				"creator_hierarchy_position"
				if approved == "RMA Approved"
				else "custom_creator_hierarchy_position"
			)
			result.append(
				{
					"state": state,
					"action": "Approve Return" if approved == "RMA Approved" else "Approve",
					"allowed": role,
					"next_state": pending_owner,
					"allow_self_approval": 1,
					"condition": f'doc.{creator} == "{position}" and doc.requires_business_owner_approval == 1',
				}
			)
	return result


def _update_workflows():
	for name, approved, pending_owner in (
		("Quotation Approval Workflow", "Approved", "For Business Owner Approval"),
		("Sales Order Fulfillment", "Approved for Fulfillment", "For Business Owner Approval"),
		("Sales Return Request Approval", "RMA Approved", "RMA Pending Business Owner"),
	):
		if not frappe.db.exists("Workflow", name):
			continue
		workflow = frappe.get_doc("Workflow", name)
		if not workflow.is_active:
			continue
		rows = [row.as_dict() for row in workflow.transitions]
		workflow.set("transitions", commercial_transitions(rows, approved, pending_owner))
		workflow.save(ignore_permissions=True)
	if frappe.db.exists("Workflow", "Picklist 2026"):
		workflow = frappe.get_doc("Workflow", "Picklist 2026")
		if workflow.is_active:
			for state in workflow.states:
				if state.state != "Cancelled":
					state.allow_edit = WORKFLOW_ROLE
			for state, action, next_state in (
				("Draft", "Send to Warehouse", "For Picking"),
				("For Picking", "Start Picking", "Picking"),
				("Picking", "Confirm Picked", "Picked"),
				("For Picking", "Return to Sales", "Returned to Sales"),
				("Picking", "Return to Sales", "Returned to Sales"),
				("Returned to Sales", "Revise", "Draft"),
			):
				for role in MANAGERS.values():
					if not any(
						row.state == state and row.action == action and row.allowed == role
						for row in workflow.transitions
					):
						workflow.append(
							"transitions",
							{
								"state": state,
								"action": action,
								"next_state": next_state,
								"allowed": role,
								"allow_self_approval": 1,
							},
						)
			workflow.save(ignore_permissions=True)


def sync_workflow_role(doc, method=None):
	"""UI edit eligibility only: this helper role has NO document permissions."""
	if not frappe.db.exists("Role", WORKFLOW_ROLE):
		return
	roles = {row.role for row in doc.get("roles", [])}
	eligible = bool(WORKFLOW_MEMBERS.intersection(roles)) and bool(doc.get("enabled"))
	if eligible and WORKFLOW_ROLE not in roles:
		doc.append("roles", {"role": WORKFLOW_ROLE})
	elif not eligible and WORKFLOW_ROLE in roles:
		doc.set("roles", [row for row in doc.roles if row.role != WORKFLOW_ROLE])


def _workspace():
	name = "Branch Fulfillment"
	if frappe.db.exists("Workspace", name):
		return
	shortcuts = ["Sales Order", "Pick List", "Delivery Note", "Sales Return Request"]
	content = [{"id": "branch-header", "type": "header", "data": {"text": "Branch Fulfillment", "col": 12}}]
	content += [
		{"id": f"branch-{index}", "type": "shortcut", "data": {"shortcut_name": label, "col": 3}}
		for index, label in enumerate(shortcuts)
	]
	frappe.get_doc(
		{
			"doctype": "Workspace",
			"name": name,
			"label": name,
			"title": name,
			"public": 1,
			"module": "OTEC Selling",
			"icon": "package",
			"content": json.dumps(content),
			"roles": [{"role": role} for role in MANAGERS.values()],
			"shortcuts": [
				{"label": label, "type": "DocType", "link_to": label, "doc_view": "List"}
				for label in shortcuts
			],
		}
	).insert(ignore_permissions=True)


def setup_branch_operations():
	if not frappe.db.exists("Role", WORKFLOW_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": WORKFLOW_ROLE, "desk_access": 1}).insert(
			ignore_permissions=True
		)
	for role in MANAGERS.values():
		if not frappe.db.exists("Role", role):
			continue
		for doctype in ("Pick List", "Delivery Note"):
			_grant(doctype, role, ("read", "create", "write", "submit", "print"))
		_grant("Stock Reservation Entry", role, ("read", "create", "write", "submit"))
		for doctype in ("Warehouse", "Item", "UOM", "Batch", "Serial No", "Bin"):
			_grant(doctype, role, ("read", "select"))
	fields = {}
	for doctype in ("Quotation", "Sales Order", "Sales Return Request"):
		fields[doctype] = [
			{
				"fieldname": "custom_commercial_approved_by",
				"label": "Commercial Approved By",
				"fieldtype": "Link",
				"options": "User",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "custom_commercial_approved_on",
				"label": "Commercial Approved On",
				"fieldtype": "Datetime",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "custom_self_approved",
				"label": "Self Approved",
				"fieldtype": "Check",
				"read_only": 1,
				"no_copy": 1,
			},
		]
	for doctype in ("Pick List", "Delivery Note"):
		fields[doctype] = [
			{
				"fieldname": "custom_fulfillment_operator",
				"label": "Fulfillment Operator",
				"fieldtype": "Link",
				"options": "User",
				"read_only": 1,
				"no_copy": 1,
			},
			{
				"fieldname": "custom_fulfillment_completed_on",
				"label": "Fulfillment Completed On",
				"fieldtype": "Datetime",
				"read_only": 1,
				"no_copy": 1,
			},
		]
	create_custom_fields(fields, update=True)
	for name in ("Central Fulfillment DR", "Delivery Note Validation"):
		if frappe.db.exists("Server Script", name):
			script = frappe.get_doc("Server Script", name)
			script.script = return_receipt_routing(script.script)
			script.save(ignore_permissions=True)
	for doctype in ("Sales Order", "Pick List", "Delivery Note"):
		name = QUERY_SCRIPTS[doctype]
		if frappe.db.exists("Server Script", name):
			script = frappe.get_doc("Server Script", name)
			script.script = script.script.split(MARKER)[0].rstrip() + "\n" + visibility_extension(doctype)
			script.save(ignore_permissions=True)
	# Replaced by the common before_save/before_submit guard, which understands
	# the active combined TL/Supervisor queue and explicitly permits self-approval.
	if frappe.db.exists("Server Script", "Quotation - Enforce Approval Scope"):
		script = frappe.get_doc("Server Script", "Quotation - Enforce Approval Scope")
		script.disabled = 1
		script.save(ignore_permissions=True)
	_update_workflows()
	for name in frappe.get_all("User", filters={"user_type": "System User"}, pluck="name"):
		user = frappe.get_doc("User", name)
		before = [row.role for row in user.roles]
		sync_workflow_role(user)
		if before != [row.role for row in user.roles]:
			user.save(ignore_permissions=True)
	_workspace()
	frappe.clear_cache()
