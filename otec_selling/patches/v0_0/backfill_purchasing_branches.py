from __future__ import annotations

import frappe


def _existing_branch(name: str) -> str | None:
    return name if frappe.db.exists("Branch", name) else None


def _branch_from_text(company: str | None, *values: str | None) -> str | None:
    text = " ".join(value or "" for value in values).lower()
    if "porac" in text:
        return _existing_branch("Warehouse Porac")
    if "malabanias" in text or "angeles" in text:
        return _existing_branch("COMFORT Angeles")
    if "baguio" in text:
        return _existing_branch("COMFORT Baguio")
    if "cagayan" in text:
        return _existing_branch("COMFORT Cagayan")
    if "tagaytay" in text:
        return _existing_branch("COMFORT Tagaytay")
    if "subic" in text:
        return _existing_branch("COMFORT Subic") or _existing_branch("Subic")
    if "marikina" in text:
        candidate = "OTEC Marikina" if (company or "").startswith("OTEC") else "COMFORT Marikina"
        return _existing_branch(candidate)
    if "friendship" in text:
        candidate = "OTEC Friendship" if (company or "").startswith("OTEC") else "COMFORT Friendship"
        return _existing_branch(candidate) or _existing_branch("Friendship Branch")
    return None


def _warehouses(child_doctype: str, parent: str) -> list[str]:
    return frappe.get_all(
        child_doctype,
        filters={"parent": parent},
        pluck="warehouse",
    )


def _set_document_branch(doctype: str, child_doctype: str, name: str, branch: str) -> None:
    frappe.db.set_value(doctype, name, "branch", branch, update_modified=False)
    frappe.db.set_value(
        child_doctype,
        {"parent": name},
        "branch",
        branch,
        update_modified=False,
    )


def execute() -> None:
    for row in frappe.get_all(
        "Purchase Order",
        filters={"branch": ["is", "not set"]},
        fields=["name", "company", "supplier"],
    ):
        warehouses = _warehouses("Purchase Order Item", row.name)
        branch = _branch_from_text(row.company, row.supplier, *warehouses)
        if branch:
            _set_document_branch("Purchase Order", "Purchase Order Item", row.name, branch)

    for row in frappe.get_all(
        "Purchase Receipt",
        filters={"branch": ["is", "not set"]},
        fields=["name", "company", "supplier"],
    ):
        po_branches = frappe.db.sql_list(
            """
            select distinct po.branch
              from `tabPurchase Receipt Item` pri
              join `tabPurchase Order` po on po.name = pri.purchase_order
             where pri.parent = %s and ifnull(po.branch, '') != ''
            """,
            row.name,
        )
        branch = po_branches[0] if len(po_branches) == 1 else None
        if not branch:
            warehouses = _warehouses("Purchase Receipt Item", row.name)
            branch = _branch_from_text(row.company, row.supplier, *warehouses)
        if branch:
            _set_document_branch("Purchase Receipt", "Purchase Receipt Item", row.name, branch)

    for name in frappe.get_all(
        "Landed Cost Voucher",
        filters={"branch": ["is", "not set"]},
        pluck="name",
    ):
        branches = frappe.db.sql_list(
            """
            select distinct pr.branch
              from `tabLanded Cost Purchase Receipt` lcpr
              join `tabPurchase Receipt` pr on pr.name = lcpr.receipt_document
             where lcpr.parent = %s and ifnull(pr.branch, '') != ''
            """,
            name,
        )
        if len(branches) == 1:
            _set_document_branch("Landed Cost Voucher", "Landed Cost Item", name, branches[0])

    frappe.clear_cache()
