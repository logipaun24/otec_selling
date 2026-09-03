from __future__ import annotations

from collections.abc import Iterable

import frappe


def _unique(values: Iterable[str | None]) -> list[str]:
	return sorted({value for value in values if value})


def _consistent_value(rows: list, fieldname: str, *, required: bool = False):
	"""Return a value only when every source row agrees, including on blanks."""
	values = {row.get(fieldname) or None for row in rows}
	if len(values) != 1:
		return None, False
	value = values.pop()
	return value, bool(value) if required else True


def _source_sales_orders(doc, link_field: str) -> list:
	order_names = _unique(
		row.get(link_field) for row in doc.get("locations" if doc.doctype == "Pick List" else "items", [])
	)
	if not order_names:
		return []
	orders = frappe.get_all(
		"Sales Order",
		filters={"name": ["in", order_names]},
		fields=["name", "company", "branch", "custom_sales_user", "custom_sales_team_group"],
		limit_page_length=0,
	)
	return orders if len(orders) == len(order_names) else []


def resolve_fulfillment_ownership(doc) -> tuple[dict | None, str]:
	"""Resolve ownership only when all linked Sales Orders have the same scope."""
	link_field = "sales_order" if doc.doctype == "Pick List" else "against_sales_order"
	orders = _source_sales_orders(doc, link_field)
	if not orders:
		return None, "no linked Sales Order"

	company, company_ok = _consistent_value(orders, "company", required=True)
	branch, branch_ok = _consistent_value(orders, "branch", required=True)
	sales_user, user_ok = _consistent_value(orders, "custom_sales_user", required=True)
	sales_team, team_ok = _consistent_value(orders, "custom_sales_team_group")
	if not all((company_ok, branch_ok, user_ok, team_ok)):
		return None, "linked Sales Orders have incomplete or conflicting ownership"
	if doc.get("company") and doc.company != company:
		return None, "company does not match linked Sales Orders"

	return {
		"company": company,
		"branch": branch,
		"custom_sales_user": sales_user,
		"custom_sales_team_group": sales_team,
		"sales_orders": [row.name for row in orders],
	}, "linked Sales Orders"


def set_fulfillment_ownership(doc, method=None) -> None:
	if doc.docstatus != 0:
		return
	resolved, _source = resolve_fulfillment_ownership(doc)
	if not resolved:
		return

	branch_field = "custom_branch" if doc.doctype == "Pick List" else "branch"
	if not doc.get("custom_sales_user"):
		doc.custom_sales_user = resolved["custom_sales_user"]
	if not doc.get("custom_sales_team_group") and resolved["custom_sales_team_group"]:
		doc.custom_sales_team_group = resolved["custom_sales_team_group"]
	if not doc.get(branch_field):
		doc.set(branch_field, resolved["branch"])


def _backfill_doctype(doctype: str, dry_run: bool) -> tuple[list[dict], list[dict]]:
	updated = []
	unresolved = []
	branch_field = "custom_branch" if doctype == "Pick List" else "branch"
	for row in frappe.get_all(
		doctype,
		filters={"docstatus": ["<", 2], "custom_sales_user": ["in", ["", None]]},
		fields=["name"],
		order_by="creation asc",
		limit_page_length=0,
	):
		doc = frappe.get_doc(doctype, row.name)
		resolved, reason = resolve_fulfillment_ownership(doc)
		if not resolved:
			unresolved.append({"doctype": doctype, "name": doc.name, "reason": reason})
			continue

		values = {"custom_sales_user": resolved["custom_sales_user"]}
		if not doc.get("custom_sales_team_group") and resolved["custom_sales_team_group"]:
			values["custom_sales_team_group"] = resolved["custom_sales_team_group"]
		if not doc.get(branch_field):
			values[branch_field] = resolved["branch"]
		updated.append(
			{"doctype": doctype, "name": doc.name, "sales_orders": resolved["sales_orders"], **values}
		)
		if not dry_run:
			frappe.db.set_value(doctype, doc.name, values, update_modified=False)

	return updated, unresolved


@frappe.whitelist()
def backfill_fulfillment_ownership(dry_run: bool = True) -> dict:
	dry_run = bool(frappe.parse_json(dry_run))
	if not dry_run and frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles():
		frappe.throw("System Manager is required to update fulfillment ownership.", frappe.PermissionError)

	updated = []
	unresolved = []
	for doctype in ("Pick List", "Delivery Note"):
		doctype_updated, doctype_unresolved = _backfill_doctype(doctype, dry_run)
		updated.extend(doctype_updated)
		unresolved.extend(doctype_unresolved)

	if not dry_run:
		frappe.clear_cache(doctype="Pick List")
		frappe.clear_cache(doctype="Delivery Note")
	return {"dry_run": dry_run, "updated": updated, "unresolved": unresolved}
