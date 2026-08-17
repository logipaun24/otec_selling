from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


PURCHASE_APPROVERS = {"Purchase Manager", "General Manager", "Business Owner"}
RECEIPT_CREATORS = {"Inventory Controller", "Purchase User", "Stock User"}
RECEIPT_APPROVERS = {
    "Inventory Controller Supervisor",
    "Stock Manager",
    "General Manager",
    "Business Owner",
}
LCV_CREATORS = {"Stock Manager", "Accounts User"}
LCV_APPROVERS = {"Accounts Manager", "General Manager", "Business Owner"}

CHARGE_ACCOUNT_FIELDS = {
    "Freight Cost": "custom_lcv_freight_account",
    "Customs Duty": "custom_lcv_customs_duty_account",
    "Import Tax": "custom_lcv_import_tax_account",
    "Brokerage Fee": "custom_lcv_brokerage_account",
    "Port Charges": "custom_lcv_port_charges_account",
    "Trucking Cost": "custom_lcv_trucking_account",
    "Insurance Cost": "custom_lcv_insurance_account",
    "Other Charges": "custom_lcv_other_charges_account",
}


def _roles(user: str | None = None) -> set[str]:
    return set(frappe.get_roles(user or frappe.session.user))


def _require_any_role(allowed: set[str], operation: str) -> None:
    if frappe.session.user == "Administrator":
        return
    if not (_roles() & allowed):
        frappe.throw(
            _("You need one of these roles to {0}: {1}").format(
                operation, ", ".join(sorted(allowed))
            ),
            frappe.PermissionError,
        )


def _enforce_separation_of_duties(doc: Document, approver_roles: set[str]) -> None:
    if frappe.session.user == "Administrator":
        return
    if frappe.session.user == doc.owner:
        frappe.throw(_("You cannot approve and submit a document that you created."))
    _require_any_role(approver_roles, _("approve this document"))


def _set_child_branch(doc: Document, table_field: str = "items") -> None:
    if not doc.meta.has_field("branch"):
        return
    if not doc.branch:
        frappe.throw(_("Branch is mandatory."))
    for row in doc.get(table_field) or []:
        if row.meta.has_field("branch"):
            if row.branch and row.branch != doc.branch:
                frappe.throw(
                    _("Row {0}: Branch must match the document Branch {1}.").format(
                        row.idx, doc.branch
                    )
                )
            row.branch = doc.branch


def validate_purchase_order(doc: Document, method: str | None = None) -> None:
    _set_child_branch(doc)


def before_submit_purchase_order(doc: Document, method: str | None = None) -> None:
    _enforce_separation_of_duties(doc, PURCHASE_APPROVERS)


def _derive_receipt_branch(doc: Document) -> str | None:
    branches = set()
    for row in doc.items:
        if row.purchase_order:
            branch = frappe.db.get_value("Purchase Order", row.purchase_order, "branch")
            if branch:
                branches.add(branch)
    if len(branches) > 1:
        frappe.throw(_("A Purchase Receipt cannot combine Purchase Orders from different Branches."))
    return next(iter(branches), None)


def validate_purchase_receipt(doc: Document, method: str | None = None) -> None:
    if not doc.branch:
        doc.branch = _derive_receipt_branch(doc)
    _set_child_branch(doc)


def before_submit_purchase_receipt(doc: Document, method: str | None = None) -> None:
    _enforce_separation_of_duties(doc, RECEIPT_APPROVERS)


def _active_lcv_for_receipt(receipt: str, exclude: str | None = None) -> str | None:
    rows = frappe.db.sql(
        """
        select lcv.name
          from `tabLanded Cost Voucher` lcv
          join `tabLanded Cost Purchase Receipt` lpr on lpr.parent = lcv.name
         where lpr.receipt_document = %s
           and lcv.docstatus != 2
           and (%s is null or lcv.name != %s)
         order by lcv.creation
         limit 1
        """,
        (receipt, exclude, exclude),
    )
    return rows[0][0] if rows else None


def _derive_lcv_branch(doc: Document) -> str | None:
    branches = set()
    for row in doc.purchase_receipts:
        if row.receipt_document_type != "Purchase Receipt":
            continue
        branch = frappe.db.get_value("Purchase Receipt", row.receipt_document, "branch")
        if branch:
            branches.add(branch)
    if len(branches) > 1:
        frappe.throw(_("One Landed Cost Voucher cannot combine Purchase Receipts from different Branches."))
    return next(iter(branches), None)


def validate_landed_cost_voucher(doc: Document, method: str | None = None) -> None:
    if not doc.branch:
        doc.branch = _derive_lcv_branch(doc)
    _set_child_branch(doc)

    if not doc.get("custom_allow_additional_landed_cost"):
        for row in doc.purchase_receipts:
            existing = _active_lcv_for_receipt(row.receipt_document, doc.name if not doc.is_new() else None)
            if existing:
                frappe.throw(
                    (
                        _("Purchase Receipt {0} already belongs to active Landed Cost Voucher {1}. ")
                        + _("Use 'Allow Additional Landed Cost' only for a reviewed incremental charge.")
                    ).format(row.receipt_document, existing),
                    title=_("Duplicate landed cost blocked"),
                )


def before_submit_landed_cost_voucher(doc: Document, method: str | None = None) -> None:
    _enforce_separation_of_duties(doc, LCV_APPROVERS)


def _sync_container_receiving(container_receiving: str) -> None:
    if not container_receiving or not frappe.db.exists("Container Receiving", container_receiving):
        return
    receipts = frappe.get_all(
        "Purchase Receipt",
        filters={"custom_container_receiving": container_receiving, "docstatus": ["!=", 2]},
        fields=["name", "docstatus"],
    )
    if not receipts:
        status = "Scanning"
    elif all(row.docstatus == 1 for row in receipts):
        status = "Completed"
    elif any(row.docstatus == 1 for row in receipts):
        status = "Partially Submitted"
    else:
        status = "Receipts Created"
    frappe.db.set_value("Container Receiving", container_receiving, "status", status)


def sync_container_receiving_from_receipt(doc: Document, method: str | None = None) -> None:
    _sync_container_receiving(doc.get("custom_container_receiving"))


def _sync_container_landed_cost(doc: Document, status: str, submit: bool = False, cancel: bool = False) -> None:
    names = frappe.get_all(
        "Container Landed Cost",
        filters={"landed_cost_voucher": doc.name},
        pluck="name",
    )
    for name in names:
        container = frappe.get_doc("Container Landed Cost", name)
        container.flags.from_lcv_sync = True
        container.flags.ignore_permissions = True
        container.status = status
        if submit and container.docstatus == 0:
            container.save(ignore_permissions=True)
            container.submit()
        elif cancel and container.docstatus == 1:
            container.cancel()
        else:
            container.save(ignore_permissions=True)


def after_submit_landed_cost_voucher(doc: Document, method: str | None = None) -> None:
    _sync_container_landed_cost(doc, "Submitted", submit=True)


def after_cancel_landed_cost_voucher(doc: Document, method: str | None = None) -> None:
    _sync_container_landed_cost(doc, "Cancelled", cancel=True)


def before_submit_container_landed_cost(doc: Document, method: str | None = None) -> None:
    if doc.flags.get("from_lcv_sync"):
        return
    if not doc.landed_cost_voucher or frappe.db.get_value(
        "Landed Cost Voucher", doc.landed_cost_voucher, "docstatus"
    ) != 1:
        frappe.throw(_("Submit the linked Landed Cost Voucher through its approval workflow first."))


def before_cancel_container_landed_cost(doc: Document, method: str | None = None) -> None:
    if doc.flags.get("from_lcv_sync"):
        return
    if doc.landed_cost_voucher and frappe.db.get_value(
        "Landed Cost Voucher", doc.landed_cost_voucher, "docstatus"
    ) != 2:
        frappe.throw(_("Cancel the linked Landed Cost Voucher first."))


@frappe.whitelist()
def fetch_container_receiving_items(container_number: str) -> list[dict]:
    _require_any_role(RECEIPT_CREATORS | RECEIPT_APPROVERS, _("fetch container Purchase Orders"))
    if not container_number:
        frappe.throw(_("Container Number is required."))
    return frappe.db.sql(
        """
        select po.name as po_no, po.po_num, po.supplier, po.company, po.branch,
               poi.name as po_item, poi.item_code, poi.item_name,
               poi.qty as ordered_qty, ifnull(poi.received_qty, 0) as already_received_qty,
               poi.qty - ifnull(poi.received_qty, 0) as pending_qty,
               poi.uom, poi.stock_uom, poi.conversion_factor, poi.warehouse, poi.rate
          from `tabPurchase Order` po
          join `tabPurchase Order Item` poi on poi.parent = po.name
         where po.docstatus = 1
           and po.status not in ('Closed', 'Completed', 'Cancelled')
           and po.custom_container_no = %s
           and poi.qty > ifnull(poi.received_qty, 0)
         order by po.company, po.branch, po.supplier, po.po_num, poi.idx
        """,
        container_number,
        as_dict=True,
    )


@frappe.whitelist()
def create_container_purchase_receipts(docname: str) -> dict:
    _require_any_role(RECEIPT_CREATORS, _("create container Purchase Receipts"))
    doc = frappe.get_doc("Container Receiving", docname)
    doc.check_permission("write")

    existing = frappe.get_all(
        "Purchase Receipt",
        filters={"custom_container_receiving": doc.name, "docstatus": ["!=", 2]},
        pluck="name",
    )
    if existing:
        frappe.throw(
            _("Purchase Receipts already exist for this Container Receiving: {0}").format(
                ", ".join(existing)
            )
        )

    warehouse_map = {
        row.company: row.target_warehouse
        for row in doc.get("company_warehouse_mapping") or []
        if row.company and row.target_warehouse
    }
    if not warehouse_map:
        frappe.throw(_("Company Warehouse Mapping is required."))

    groups: dict[tuple[str, str, str], list] = defaultdict(list)
    for row in doc.items:
        if flt(row.arrived_qty) <= 0:
            continue
        branch = frappe.db.get_value("Purchase Order", row.po_no, "branch")
        if not branch:
            frappe.throw(_("Purchase Order {0} has no Branch.").format(row.po_no))
        if not row.company or not row.supplier or not row.po_no or not row.po_item:
            frappe.throw(_("Row {0}: Company, Supplier and Purchase Order links are required.").format(row.idx))
        if row.company not in warehouse_map:
            frappe.throw(_("No target warehouse is mapped for company {0}.").format(row.company))
        groups[(row.company, row.supplier, branch)].append(row)

    if not groups:
        frappe.throw(_("No arrived quantities were entered."))

    created = []
    for (company, supplier, branch), rows in groups.items():
        pr = frappe.new_doc("Purchase Receipt")
        pr.company = company
        pr.supplier = supplier
        pr.branch = branch
        pr.set_posting_time = 1
        pr.custom_container_no = doc.container_number
        pr.custom_container_receiving = doc.name
        for row in rows:
            pr.append(
                "items",
                {
                    "item_code": row.item_code,
                    "item_name": row.item_name,
                    "qty": flt(row.arrived_qty),
                    "uom": row.uom,
                    "stock_uom": row.stock_uom,
                    "conversion_factor": flt(row.conversion_factor) or 1,
                    "warehouse": warehouse_map[company],
                    "rate": flt(row.rate),
                    "purchase_order": row.po_no,
                    "purchase_order_item": row.po_item,
                    "branch": branch,
                },
            )
        pr.insert()
        created.append(pr.name)

    doc.db_set("status", "Receipts Created")
    return {"created_receipts": created}


@frappe.whitelist()
def fetch_container_landed_cost_items(docname: str) -> str:
    _require_any_role(LCV_CREATORS | LCV_APPROVERS, _("fetch landed-cost items"))
    doc = frappe.get_doc("Container Landed Cost", docname)
    doc.check_permission("write")
    if doc.docstatus != 0:
        frappe.throw(_("Items can only be fetched while the document is Draft."))
    if not doc.container_no or not doc.company:
        frappe.throw(_("Company and Container No are required."))

    receipts = frappe.get_all(
        "Purchase Receipt",
        filters={
            "docstatus": 1,
            "company": doc.company,
            "custom_container_no": doc.container_no,
            "is_return": 0,
        },
        fields=["name", "supplier", "posting_date", "grand_total", "branch"],
    )
    if not receipts:
        frappe.throw(_("No submitted Purchase Receipts were found for this company and container."))

    branches = {row.branch for row in receipts if row.branch}
    if len(branches) != 1:
        frappe.throw(_("All selected Purchase Receipts must have exactly one common Branch."))
    branch = next(iter(branches))
    if doc.branch and doc.branch != branch:
        frappe.throw(
            _("Submitted Purchase Receipts belong to Branch {0}, not {1}.").format(
                branch, doc.branch
            )
        )

    doc.set("purchase_receipts", [])
    doc.set("items", [])
    for receipt in receipts:
        existing = _active_lcv_for_receipt(receipt.name)
        if existing:
            frappe.throw(
                _("Purchase Receipt {0} already belongs to active LCV {1}.").format(
                    receipt.name, existing
                )
            )
        doc.append(
            "purchase_receipts",
            {
                "purchase_receipt": receipt.name,
                "supplier": receipt.supplier,
                "posting_date": receipt.posting_date,
                "grand_total": receipt.grand_total,
            },
        )
        pr = frappe.get_doc("Purchase Receipt", receipt.name)
        for item in pr.items:
            if not item.purchase_order:
                continue
            if frappe.db.get_value("Purchase Order", item.purchase_order, "custom_container_no") != doc.container_no:
                continue
            doc.append(
                "items",
                {
                    "purchase_receipt": receipt.name,
                    "purchase_receipt_item": item.name,
                    "purchase_order": item.purchase_order,
                    "po_num": frappe.db.get_value("Purchase Order", item.purchase_order, "po_num"),
                    "supplier": pr.supplier,
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "batch_no": item.batch_no,
                    "warehouse": item.warehouse,
                    "received_qty": item.qty,
                    "uom": item.uom,
                    "original_rate": item.rate,
                    "original_amount": item.amount,
                    "original_valuation_rate": item.valuation_rate or item.rate,
                    "new_valuation_rate": item.valuation_rate or item.rate,
                    "final_landed_amount": item.amount,
                },
            )
    doc.branch = branch
    doc.status = "Draft"
    doc.save()
    return _("Fetched submitted receipts. Enter CBM per unit and compute allocation.")


@frappe.whitelist()
def compute_container_landed_cost(docname: str) -> dict:
    _require_any_role(LCV_CREATORS | LCV_APPROVERS, _("compute landed cost"))
    doc = frappe.get_doc("Container Landed Cost", docname)
    doc.check_permission("write")
    if doc.docstatus != 0 or not doc.items:
        frappe.throw(_("A Draft document with fetched items is required."))

    charge_fields = [
        "freight_cost",
        "customs_duty",
        "import_tax",
        "brokerage_fee",
        "port_charges",
        "trucking_cost",
        "insurance_cost",
        "other_charges",
    ]
    total_charges = sum(flt(doc.get(field)) for field in charge_fields)
    if total_charges <= 0:
        frappe.throw(_("Total landed charges must be greater than zero."))

    total_cbm = 0.0
    for row in doc.items:
        row.total_cbm = flt(row.received_qty) * flt(row.cbm_per_unit)
        if row.total_cbm <= 0:
            frappe.throw(_("Row {0}: CBM per unit must be greater than zero.").format(row.idx))
        total_cbm += row.total_cbm

    if flt(doc.total_container_cbm) <= 0:
        frappe.throw(_("Total Container CBM must be greater than zero."))
    tolerance = max(0.001, flt(doc.total_container_cbm) * 0.001)
    if abs(total_cbm - flt(doc.total_container_cbm)) > tolerance:
        frappe.throw(
            _("Item CBM ({0}) must equal Container CBM ({1}) within 0.1%.").format(
                total_cbm, doc.total_container_cbm
            )
        )

    allocation_fields = [
        ("freight_cost", "allocated_freight"),
        ("customs_duty", "allocated_customs_duty"),
        ("import_tax", "allocated_import_tax"),
        ("brokerage_fee", "allocated_brokerage_fee"),
        ("port_charges", "allocated_port_charges"),
        ("trucking_cost", "allocated_trucking_cost"),
        ("insurance_cost", "allocated_insurance_cost"),
        ("other_charges", "allocated_other_charges"),
    ]
    allocated_running = 0.0
    for index, row in enumerate(doc.items):
        share = flt(row.total_cbm) / total_cbm
        row.cbm_share_percent = share * 100
        row_total = 0.0
        for source, target in allocation_fields:
            value = flt(doc.get(source)) * share
            row.set(target, value)
            row_total += value
        if index == len(doc.items) - 1:
            row_total += total_charges - (allocated_running + row_total)
        row.total_allocated_charges = row_total
        allocated_running += row_total
        row.additional_cost_per_unit = row_total / flt(row.received_qty)
        row.new_valuation_rate = flt(row.original_valuation_rate) + row.additional_cost_per_unit
        row.final_landed_amount = flt(row.original_amount) + row_total

    doc.total_landed_charges = total_charges
    doc.total_item_cbm = total_cbm
    doc.cbm_difference = flt(doc.total_container_cbm) - total_cbm
    doc.status = "Computed"
    doc.save()
    return {"total_item_cbm": total_cbm, "total_landed_charges": total_charges}


def _company_charge_account(company: str, description: str) -> str:
    fieldname = CHARGE_ACCOUNT_FIELDS[description]
    account = frappe.db.get_value("Company", company, fieldname)
    if not account:
        frappe.throw(
            _("Configure {0} on Company {1} before creating the LCV.").format(
                frappe.get_meta("Company").get_label(fieldname), company
            )
        )
    account_company, is_group, root_type = frappe.db.get_value(
        "Account", account, ["company", "is_group", "root_type"]
    )
    if account_company != company or is_group or root_type != "Expense":
        frappe.throw(
            _("Mapped account {0} must be an Expense ledger account for company {1}.").format(
                account, company
            )
        )
    return account


@frappe.whitelist()
def create_lcv_from_container(docname: str) -> str:
    _require_any_role(LCV_CREATORS, _("create a Landed Cost Voucher"))
    doc = frappe.get_doc("Container Landed Cost", docname)
    doc.check_permission("write")
    if doc.docstatus != 0 or doc.status != "Computed":
        frappe.throw(_("Compute the Draft Container Landed Cost before creating an LCV."))
    if doc.landed_cost_voucher:
        frappe.throw(_("Landed Cost Voucher already created: {0}").format(doc.landed_cost_voucher))

    for row in doc.purchase_receipts:
        existing = _active_lcv_for_receipt(row.purchase_receipt)
        if existing:
            frappe.throw(_("Purchase Receipt {0} already belongs to active LCV {1}.").format(row.purchase_receipt, existing))

    charges = [
        ("Freight Cost", "freight_cost"),
        ("Customs Duty", "customs_duty"),
        ("Import Tax", "import_tax"),
        ("Brokerage Fee", "brokerage_fee"),
        ("Port Charges", "port_charges"),
        ("Trucking Cost", "trucking_cost"),
        ("Insurance Cost", "insurance_cost"),
        ("Other Charges", "other_charges"),
    ]
    lcv = frappe.new_doc("Landed Cost Voucher")
    lcv.company = doc.company
    lcv.branch = doc.branch
    lcv.posting_date = doc.posting_date
    lcv.posting_time = doc.posting_time
    lcv.distribute_charges_based_on = "Distribute Manually"
    for row in doc.purchase_receipts:
        lcv.append(
            "purchase_receipts",
            {
                "receipt_document_type": "Purchase Receipt",
                "receipt_document": row.purchase_receipt,
                "supplier": row.supplier,
                "grand_total": row.grand_total,
            },
        )
    for description, source in charges:
        amount = flt(doc.get(source))
        if amount:
            lcv.append(
                "taxes",
                {
                    "description": description,
                    "amount": amount,
                    "expense_account": _company_charge_account(doc.company, description),
                },
            )
    lcv.get_items_from_purchase_receipts()
    allocations = {row.purchase_receipt_item: flt(row.total_allocated_charges) for row in doc.items}
    for item in lcv.items:
        item.applicable_charges = allocations.get(item.purchase_receipt_item, 0)
        item.branch = doc.branch
    lcv.insert()
    doc.landed_cost_voucher = lcv.name
    doc.status = "Awaiting LCV Approval"
    doc.save()
    return lcv.name
