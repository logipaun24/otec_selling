from __future__ import annotations

from collections.abc import Iterable

import frappe
from frappe import _

HIERARCHY_DOCTYPE = "Sales Access Hierarchy"
COMMERCIAL_POSITIONS = ("Sales Representative", "Team Leader", "Supervisor")
MULTI_TEAM_MANAGER_POSITIONS = ("Team Leader", "Supervisor")


def _unique(values: Iterable[str | None]) -> list[str]:
	return sorted({value for value in values if value})


def _active_hierarchy(user: str | None):
	if not user:
		return None
	return frappe.db.get_value(
		HIERARCHY_DOCTYPE,
		{"user": user, "active": 1},
		["name", "user", "position", "company", "branch", "sales_team_group"],
		as_dict=True,
	)


def _linked_quotation_context(doc) -> list:
	names = _unique(row.get("prevdoc_docname") for row in doc.get("items", []))
	if not names:
		return []
	return frappe.get_all(
		"Quotation",
		filters={"name": ["in", names]},
		fields=["name", "owner", "custom_sales_user", "custom_sales_team_group", "custom_branch", "company"],
	)


def _candidate_from_scope(company: str | None, branch: str | None, sales_team: str | None):
	if not company or not branch:
		return None

	filters = {
		"active": 1,
		"company": company,
		"branch": branch,
		"position": ["in", COMMERCIAL_POSITIONS],
	}
	if sales_team:
		filters["sales_team_group"] = sales_team
	candidates = frappe.get_all(
		HIERARCHY_DOCTYPE,
		filters=filters,
		fields=["name", "user", "position", "company", "branch", "sales_team_group"],
	)
	with_complete_scope = [row for row in candidates if row.user and row.sales_team_group]
	if not sales_team and len(_unique(row.sales_team_group for row in with_complete_scope)) != 1:
		return None
	representatives = [row for row in with_complete_scope if row.position == "Sales Representative"]
	if len(representatives) == 1:
		return representatives[0]
	if len(with_complete_scope) == 1:
		return with_complete_scope[0]
	return None


def resolve_sales_order_owner(doc):
	"""Return an unambiguous hierarchy row and the evidence used to select it."""
	if doc.get("custom_sales_user"):
		return _active_hierarchy(doc.custom_sales_user), "existing sales user"

	quotations = _linked_quotation_context(doc)
	quotation_users = _unique(row.custom_sales_user for row in quotations)
	if len(quotation_users) == 1:
		hierarchy = _active_hierarchy(quotation_users[0])
		if hierarchy:
			return hierarchy, "linked quotation sales user"

	quotation_owners = _unique(row.owner for row in quotations)
	if len(quotation_owners) == 1:
		hierarchy = _active_hierarchy(quotation_owners[0])
		if hierarchy:
			return hierarchy, "linked quotation owner"

	hierarchy = _active_hierarchy(doc.get("owner"))
	if hierarchy:
		return hierarchy, "sales order owner"

	quotation_branches = _unique(row.custom_branch for row in quotations)
	branch = doc.get("branch") or (quotation_branches[0] if len(quotation_branches) == 1 else None)
	quotation_teams = _unique(row.custom_sales_team_group for row in quotations)
	sales_team = doc.get("custom_sales_team_group") or (
		quotation_teams[0] if len(quotation_teams) == 1 else None
	)
	hierarchy = _candidate_from_scope(doc.get("company"), branch, sales_team)
	if hierarchy:
		return hierarchy, "unique hierarchy user for company and branch"

	return None, "no unambiguous hierarchy user"


def _apply_hierarchy(doc, hierarchy) -> None:
	doc.custom_sales_user = hierarchy.user
	if not doc.get("custom_sales_team_group") and hierarchy.sales_team_group:
		doc.custom_sales_team_group = hierarchy.sales_team_group
	if not doc.get("branch") and hierarchy.branch:
		doc.branch = hierarchy.branch


def set_sales_order_ownership(doc, method=None) -> None:
	"""Populate draft Sales Order ownership before Server Scripts validate it."""
	if doc.docstatus != 0:
		return
	hierarchy, _source = resolve_sales_order_owner(doc)
	if hierarchy:
		_apply_hierarchy(doc, hierarchy)


def _company_uses_sales_hierarchy(company: str | None) -> bool:
	return bool(company and frappe.db.exists(HIERARCHY_DOCTYPE, {"company": company, "active": 1}))


def _allows_multiple_team_scopes(position: str | None) -> bool:
	return position in MULTI_TEAM_MANAGER_POSITIONS


def _has_team_scope(hierarchy) -> bool:
	if hierarchy.sales_team_group:
		return True
	if not _allows_multiple_team_scopes(hierarchy.position):
		return False
	return bool(
		frappe.db.exists(
			"Sales Hierarchy Team Access",
			{
				"parent": hierarchy.name,
				"parenttype": HIERARCHY_DOCTYPE,
				"parentfield": "allowed_sales_teams",
				"sales_team_group": ["!=", ""],
			},
		)
	)


def validate_sales_order_ownership(doc, method=None) -> None:
	"""Prevent new hierarchy-managed orders from becoming invisible after submit."""
	set_sales_order_ownership(doc)
	if not _company_uses_sales_hierarchy(doc.get("company")):
		return

	if not doc.get("custom_sales_user"):
		frappe.throw(
			_(
				"Sales Person could not be determined. Create the Sales Order from an assigned Quotation "
				"or ask a Sales Administrator to assign its ownership before submission."
			)
		)

	hierarchy = _active_hierarchy(doc.custom_sales_user)
	if not hierarchy:
		frappe.throw(
			_("Sales Person {0} needs an active Sales Access Hierarchy record.").format(doc.custom_sales_user)
		)

	if hierarchy.position != "Business Owner" and not hierarchy.branch:
		frappe.throw(
			_("Complete Branch on the Sales Access Hierarchy record for {0} before submission.").format(
				doc.custom_sales_user
			)
		)

	if hierarchy.position != "Business Owner" and not _has_team_scope(hierarchy):
		frappe.throw(
			_(
				"Configure a default Sales Team, or allowed Sales Teams for a Team Leader or Supervisor, "
				"on the Sales Access Hierarchy record for {0} before submission."
			).format(doc.custom_sales_user)
		)


@frappe.whitelist()
def backfill_sales_order_ownership(dry_run: bool = True) -> dict:
	"""Backfill only ownership that can be resolved from configured hierarchy evidence."""
	dry_run = bool(frappe.parse_json(dry_run))
	if not dry_run and frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles():
		frappe.throw(_("System Manager is required to update Sales Order ownership."), frappe.PermissionError)

	updated = []
	unresolved = []
	orders = frappe.get_all(
		"Sales Order",
		filters={"docstatus": ["<", 2]},
		fields=["name", "custom_sales_user"],
		order_by="creation asc",
	)
	for row in orders:
		if row.custom_sales_user:
			continue
		doc = frappe.get_doc("Sales Order", row.name)
		hierarchy, source = resolve_sales_order_owner(doc)
		if not hierarchy:
			unresolved.append(
				{"name": doc.name, "reason": source, "company": doc.company, "branch": doc.get("branch")}
			)
			continue
		if (hierarchy.position != "Business Owner" and not hierarchy.branch) or (
			hierarchy.position != "Business Owner" and not _has_team_scope(hierarchy)
		):
			unresolved.append(
				{
					"name": doc.name,
					"reason": "resolved hierarchy user has incomplete required scope",
					"company": doc.company,
					"branch": doc.get("branch"),
				}
			)
			continue

		values = {"custom_sales_user": hierarchy.user}
		if not doc.get("custom_sales_team_group") and hierarchy.sales_team_group:
			values["custom_sales_team_group"] = hierarchy.sales_team_group
		if not doc.get("branch") and hierarchy.branch:
			values["branch"] = hierarchy.branch
		updated.append({"name": doc.name, "source": source, **values})
		if not dry_run:
			frappe.db.set_value("Sales Order", doc.name, values, update_modified=False)

	if not dry_run:
		frappe.clear_cache(doctype="Sales Order")
	return {"dry_run": dry_run, "updated": updated, "unresolved": unresolved}
