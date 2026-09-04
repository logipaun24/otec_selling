"""Separate commercial approval scope from branch stock-operation scope.

Native role and User Permission checks still apply. These hooks only deny access;
the installer grants the minimum document permissions to existing TL/Sup roles.
"""

import frappe
from frappe.utils import cint, now_datetime

MANAGERS = {"Team Leader": "Sales Team Leader", "Supervisor": "Sales Supervisor"}
STOCK_ROLES = {"Stock User", "Stock Manager"}
QUERY_SCRIPTS = {
	"Quotation": "Quotation - Hierarchical Visibility Query",
	"Sales Order": "Sales Order - Hierarchical Visibility Query",
	"Pick List": "PICK LIST - HIERARCHICAL VISIBILITY",
	"Delivery Note": "Delivery Note - Hierarchical Visibility",
}
APPROVED = {
	"Quotation": "Approved",
	"Sales Order": "Approved for Fulfillment",
	"Sales Return Request": "RMA Approved",
}


def hierarchy_for(user):
	rows = frappe.get_all(
		"Sales Access Hierarchy",
		filters={"user": user, "active": 1},
		fields=["name", "user", "position", "company", "branch", "sales_team_group"],
		limit_page_length=2,
	)
	return rows[0] if len(rows) == 1 else None


def scopes(hierarchy, field, child_doctype, parentfield):
	values = {hierarchy.get(field)} - {None, ""}
	values.update(
		frappe.get_all(
			child_doctype,
			filters={
				"parent": hierarchy.name,
				"parenttype": "Sales Access Hierarchy",
				"parentfield": parentfield,
			},
			pluck=field,
		)
	)
	return values - {None, ""}


def company_branch_scope(hierarchy):
	return (
		scopes(hierarchy, "company", "Sales Hierarchy Company Access", "allowed_companies"),
		scopes(hierarchy, "branch", "Sales Hierarchy Branch Access", "allowed_branches"),
	)


def is_manager(hierarchy, user):
	return bool(hierarchy and MANAGERS.get(hierarchy.position) in frappe.get_roles(user))


def document_branch(doc):
	return doc.get("custom_branch") if doc.doctype in ("Quotation", "Pick List") else doc.get("branch")


def in_branch_scope(doc, hierarchy):
	companies, branches = company_branch_scope(hierarchy)
	return doc.get("company") in companies and document_branch(doc) in branches


def in_commercial_scope(doc, hierarchy, user):
	companies, _branches = company_branch_scope(hierarchy)
	if hierarchy.position == "Business Owner":
		return doc.get("company") in companies
	if not in_branch_scope(doc, hierarchy):
		return False
	teams = scopes(hierarchy, "sales_team_group", "Sales Hierarchy Team Access", "allowed_sales_teams")
	team = (
		doc.get("sales_team_group")
		if doc.doctype == "Sales Return Request"
		else doc.get("custom_sales_team_group")
	)
	owner = doc.get("sales_user") if doc.doctype == "Sales Return Request" else doc.get("custom_sales_user")
	return team in teams or owner == user or doc.get("owner") == user


def warehouse_within(warehouse, root, company):
	if not warehouse or not root:
		return False
	child = frappe.db.get_value("Warehouse", warehouse, ["company", "lft", "rgt", "disabled"], as_dict=True)
	parent = frappe.db.get_value("Warehouse", root, ["company", "lft", "rgt", "disabled"], as_dict=True)
	return bool(
		child
		and parent
		and not child.disabled
		and not parent.disabled
		and child.company == parent.company == company
		and parent.lft <= child.lft
		and child.rgt <= parent.rgt
	)


def explicit_warehouse_access(user, warehouse, company, doctype):
	"""A dual-role manager needs an explicit native Warehouse assignment for central work."""
	if not STOCK_ROLES.intersection(frappe.get_roles(user)):
		return False
	rows = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": "Warehouse"},
		fields=["for_value", "hide_descendants", "applicable_for", "apply_to_all_doctypes"],
	)
	return any(
		(row.apply_to_all_doctypes or not row.applicable_for or row.applicable_for == doctype)
		and (
			row.for_value == warehouse
			or (not row.hide_descendants and warehouse_within(warehouse, row.for_value, company))
		)
		for row in rows
	)


def source_orders(doc):
	rows = doc.get("locations" if doc.doctype == "Pick List" else "items") or []
	field = "sales_order" if doc.doctype == "Pick List" else "against_sales_order"
	names = {row.get(field) for row in rows} - {None, ""}
	return [frappe.get_doc("Sales Order", name) for name in sorted(names)]


def can_operate(doc, user, *, submitting=False):
	hierarchy = hierarchy_for(user)
	if not is_manager(hierarchy, user) or not in_branch_scope(doc, hierarchy):
		return False
	if doc.doctype == "Pick List" and doc.get("purpose") != "Delivery":
		return False
	branch = document_branch(doc)
	local_root = frappe.db.get_value("Branch", branch, "custom_default_branch_warehouse")
	if not local_root:
		return False
	rows = doc.get("locations" if doc.doctype == "Pick List" else "items") or []
	warehouses = {row.get("warehouse") for row in rows} - {None, ""}
	warehouses.update(row.get("target_warehouse") for row in rows if row.get("target_warehouse"))
	header_warehouses = (
		("set_target_warehouse",)
		if doc.get("is_return")
		else ("set_warehouse", "custom_fulfillment_warehouse", "set_target_warehouse")
	)
	for field in header_warehouses:
		if doc.get(field):
			warehouses.add(doc.get(field))
	if submitting and (not rows or any(not row.get("warehouse") for row in rows)):
		return False
	central = bool(cint(doc.get("custom_central_fulfillment"))) and not doc.get("is_return")
	for order in source_orders(doc):
		if order.company != doc.company or order.get("branch") != branch or order.docstatus != 1:
			return False
		# Return receipt authority follows the receiving warehouse, not original dispatch route.
		if not doc.get("is_return") and cint(order.get("custom_central_fulfillment")):
			central = True
		if not doc.get("is_return") and order.get("custom_fulfillment_warehouse"):
			warehouses.add(order.custom_fulfillment_warehouse)
	if central and not warehouses:
		return False
	return all(
		(not central and warehouse_within(warehouse, local_root, doc.company))
		or explicit_warehouse_access(user, warehouse, doc.company, doc.doctype)
		for warehouse in warehouses
	)


def has_permission(doc, user=None, ptype="read", **kwargs):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	hierarchy = hierarchy_for(user)
	manager_role = bool(set(MANAGERS.values()).intersection(frappe.get_roles(user)))
	if manager_role and not is_manager(hierarchy, user):
		return False  # A role alone is not a branch/approval assignment.
	if doc.doctype == "Stock Reservation Entry" and is_manager(hierarchy, user):
		return ptype == "create" or reservation_in_scope(doc, user)
	if doc.doctype in ("Pick List", "Delivery Note") and is_manager(hierarchy, user):
		if ptype in ("read", "print", "email", "export", "report"):
			return in_branch_scope(doc, hierarchy)
		if ptype == "create":
			return True  # Full scope checked after defaults/linked orders have been applied.
		if ptype in ("write", "submit", "amend", "cancel", "delete"):
			return can_operate(doc, user, submitting=ptype == "submit")
	if doc.doctype in ("Quotation", "Sales Order", "Sales Return Request") and is_manager(hierarchy, user):
		if (
			doc.doctype in ("Sales Order", "Sales Return Request")
			and ptype in ("read", "print")
			and doc.docstatus == 1
		):
			return in_branch_scope(doc, hierarchy)
		if ptype != "create":
			return in_commercial_scope(doc, hierarchy, user)
	if hierarchy and doc.doctype == "Sales Return Request" and ptype != "create":
		if hierarchy.position == "Business Owner":
			return in_commercial_scope(doc, hierarchy, user)
		return in_branch_scope(doc, hierarchy) and user in (
			doc.get("owner"),
			doc.get("sales_user"),
			doc.get("requested_by"),
		)
	return True


def reservation_in_scope(doc, user):
	if doc.get("from_voucher_type") != "Pick List" or doc.get("voucher_type") != "Sales Order":
		return False
	if not doc.get("from_voucher_no") or not frappe.db.exists("Pick List", doc.from_voucher_no):
		return False
	pick = frappe.get_doc("Pick List", doc.from_voucher_no)
	if pick.docstatus != 1 or pick.company != doc.company or not can_operate(pick, user, submitting=True):
		return False
	return any(
		row.name == doc.get("from_voucher_detail_no")
		and row.sales_order == doc.get("voucher_no")
		and row.sales_order_item == doc.get("voucher_detail_no")
		and row.item_code == doc.get("item_code")
		and row.warehouse == doc.get("warehouse")
		for row in pick.locations
	)


def validate_reservation(doc, method=None):
	user = frappe.session.user
	if user == "Administrator" or not set(MANAGERS.values()).intersection(frappe.get_roles(user)):
		return
	previous = doc.get_doc_before_save()
	if not reservation_in_scope(doc, user) or (previous and not reservation_in_scope(previous, user)):
		frappe.throw(
			"Branch stock reservation must reference a submitted delivery Pick List within your fulfillment scope.",
			frappe.PermissionError,
		)


def reservation_query(user=None):
	user = user or frappe.session.user
	if user == "Administrator" or not set(MANAGERS.values()).intersection(frappe.get_roles(user)):
		return ""
	hierarchy = hierarchy_for(user)
	if not is_manager(hierarchy, user):
		return "1 = 0"
	companies, branches = company_branch_scope(hierarchy)
	if not companies or not branches:
		return "1 = 0"
	company_sql = ", ".join(frappe.db.escape(value) for value in sorted(companies))
	branch_sql = ", ".join(frappe.db.escape(value) for value in sorted(branches))
	return (
		"`tabStock Reservation Entry`.`from_voucher_type` = 'Pick List' AND "
		"`tabStock Reservation Entry`.`from_voucher_no` IN (SELECT name FROM `tabPick List` "
		f"WHERE company IN ({company_sql}) AND custom_branch IN ({branch_sql}) AND docstatus = 1)"
	)


def validate_operation(doc, method=None):
	user = frappe.session.user
	if user == "Administrator":
		return
	roles = set(frappe.get_roles(user))
	if roles.intersection(MANAGERS.values()):
		previous = doc.get_doc_before_save()
		if previous and not can_operate(previous, user):
			frappe.throw(
				"You cannot change the branch or warehouse of a document outside your fulfillment scope.",
				frappe.PermissionError,
			)
		if not can_operate(doc, user, submitting=method == "before_submit"):
			frappe.throw(
				"Fulfillment is restricted to your assigned branch and its local warehouse. Central warehouse work requires an explicit warehouse assignment and Stock role.",
				frappe.PermissionError,
			)
	elif method == "before_submit" and hierarchy_for(user) and not STOCK_ROLES.intersection(roles):
		frappe.throw("Sales representatives cannot post stock movements.", frappe.PermissionError)
	if method == "before_submit":
		doc.custom_fulfillment_operator = user
		doc.custom_fulfillment_completed_on = now_datetime()


def validate_approval(doc, method=None):
	user = frappe.session.user
	if user == "Administrator":
		return
	state = doc.get("workflow_state") or ""
	previous = doc.get_doc_before_save()
	old_state = previous.get("workflow_state") if previous else ""
	approval_states = {
		APPROVED[doc.doctype],
		"For Business Owner Approval",
		"RMA Pending Business Owner",
		"Rejected",
		"RMA Rejected",
	}
	if state not in approval_states or (old_state == state and method != "before_submit"):
		return
	hierarchy = hierarchy_for(user)
	if not hierarchy or not in_commercial_scope(doc, hierarchy, user):
		frappe.throw("This transaction is outside your commercial approval scope.", frappe.PermissionError)
	if previous and not in_commercial_scope(previous, hierarchy, user):
		frappe.throw(
			"You cannot change ownership to bypass commercial approval scope.", frappe.PermissionError
		)
	if hierarchy.position == "Business Owner":
		if "Business Owner" not in frappe.get_roles(user):
			frappe.throw("Business Owner role is required.", frappe.PermissionError)
	elif not is_manager(hierarchy, user):
		frappe.throw(
			"Only the responsible Team Leader, Supervisor or Business Owner may approve.",
			frappe.PermissionError,
		)
	if state == APPROVED[doc.doctype]:
		credit_only = doc.doctype == "Sales Return Request" and any(
			row.disposition == "Credit Only" for row in doc.items
		)
		if (
			cint(doc.get("requires_business_owner_approval")) or credit_only
		) and hierarchy.position != "Business Owner":
			frappe.throw(
				"This exception requires Business Owner approval; self-approval cannot bypass it.",
				frappe.PermissionError,
			)
		if (
			old_state in ("For Business Owner Approval", "RMA Pending Business Owner")
			and hierarchy.position != "Business Owner"
		):
			frappe.throw("Only the Business Owner can release this approval queue.", frappe.PermissionError)
		if method == "before_submit":
			doc.custom_commercial_approved_by = user
			doc.custom_commercial_approved_on = now_datetime()
			doc.custom_self_approved = int(user in (doc.get("owner"), doc.get("requested_by")))


def validate_commercial_write(doc, method=None):
	user = frappe.session.user
	if user != "Administrator" and set(MANAGERS.values()).intersection(frappe.get_roles(user)):
		hierarchy = hierarchy_for(user)
		if not is_manager(hierarchy, user) or not in_commercial_scope(doc, hierarchy, user):
			frappe.throw(
				"Branch fulfillment access does not permit editing another team's sale.",
				frappe.PermissionError,
			)
		previous = doc.get_doc_before_save()
		if previous and not in_commercial_scope(previous, hierarchy, user):
			frappe.throw("You cannot reassign an out-of-scope sale to yourself.", frappe.PermissionError)
	validate_approval(doc, method)


def rma_query(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	hierarchy = hierarchy_for(user)
	if not hierarchy:
		return "1 = 0" if set(MANAGERS.values()).intersection(frappe.get_roles(user)) else ""
	companies, branches = company_branch_scope(hierarchy)

	def sql_in(field, values):
		return (
			f"`tabSales Return Request`.`{field}` IN ("
			+ ", ".join(frappe.db.escape(value) for value in sorted(values))
			+ ")"
			if values
			else "1 = 0"
		)

	company_sql = sql_in("company", companies)
	if hierarchy.position == "Business Owner":
		return company_sql
	own = " OR ".join(sql_in(field, {user}) for field in ("owner", "sales_user", "requested_by"))
	if is_manager(hierarchy, user):
		teams = scopes(hierarchy, "sales_team_group", "Sales Hierarchy Team Access", "allowed_sales_teams")
		own += " OR `tabSales Return Request`.`docstatus` = 1 OR " + sql_in("sales_team_group", teams)
	return f"({company_sql}) AND ({sql_in('branch', branches)}) AND ({own})"
