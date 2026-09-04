from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, now_datetime


SALES_APPROVER_ROLES = {"Sales Team Leader", "Sales Supervisor", "Business Owner", "System Manager"}
WAREHOUSE_ROLES = {"Stock User", "Stock Manager", "System Manager"}
ACCOUNTS_ROLES = {"Accounts User", "Accounts Manager", "System Manager"}


def _require_role(allowed_roles: set[str], action: str) -> None:
    if not allowed_roles.intersection(frappe.get_roles()):
        frappe.throw(_("You need one of these roles to {0}: {1}").format(action, ", ".join(sorted(allowed_roles))))


def _get_submitted_rma(name: str):
    doc = frappe.get_doc("Sales Return Request", name)
    doc.check_permission("read")
    if doc.docstatus != 1:
        frappe.throw(_("Sales Return Request {0} must be approved first.").format(name))
    return doc


def _available_qty(source_doctype: str, source, row) -> float:
    from erpnext.controllers.sales_and_purchase_return import get_returned_qty_map_for_row

    returned = get_returned_qty_map_for_row(source.name, source.customer, row.name, source_doctype)
    return max(flt(row.qty) - flt(returned.get("qty")), 0)


def get_source_details(source_doctype: str, source_name: str) -> dict:
    if source_doctype not in {"Delivery Note", "Sales Invoice"}:
        frappe.throw(_("The return source must be a Delivery Note or Sales Invoice."))
    source = frappe.get_doc(source_doctype, source_name)
    source.check_permission("read")
    if source.docstatus != 1 or source.get("is_return"):
        frappe.throw(_("Select a submitted, non-return {0}.").format(source_doctype))

    result = {
        "company": source.company,
        "customer": source.customer,
        "currency": source.get("currency") or frappe.get_cached_value("Company", source.company, "default_currency"),
        "branch": source.get("branch") or source.get("custom_branch") or "",
        "sales_user": source.get("custom_sales_user") or source.owner,
        "sales_team_group": source.get("custom_sales_team_group") or "",
        "sales_order": "",
        "delivery_note": source.name if source_doctype == "Delivery Note" else "",
        "sales_invoice": source.name if source_doctype == "Sales Invoice" else "",
        "items": [],
    }
    sales_orders = set()
    delivery_notes = set()
    for row in source.items:
        available = _available_qty(source_doctype, source, row)
        if available <= 0:
            continue
        sales_order = row.get("against_sales_order") or row.get("sales_order") or ""
        delivery_note = source.name if source_doctype == "Delivery Note" else row.get("delivery_note") or ""
        sales_orders.add(sales_order) if sales_order else None
        delivery_notes.add(delivery_note) if delivery_note else None
        result["items"].append(
            {
                "item_code": row.item_code,
                "item_name": row.item_name,
                "stock_uom": row.stock_uom,
                "sales_order": sales_order,
                "sales_order_item": row.get("so_detail") or "",
                "delivery_note": delivery_note,
                "delivery_note_item": row.name if source_doctype == "Delivery Note" else row.get("dn_detail") or "",
                "sales_invoice": source.name if source_doctype == "Sales Invoice" else row.get("against_sales_invoice") or "",
                "sales_invoice_item": row.name if source_doctype == "Sales Invoice" else "",
                "delivered_qty": flt(row.qty),
                "previously_returned_qty": flt(row.qty) - available,
                "available_qty": available,
                "requested_qty": available,
                "approved_qty": available,
                "rate": flt(row.rate),
                "warehouse": row.warehouse,
                "return_warehouse": frappe.get_cached_value("Company", source.company, "default_warehouse_for_sales_return"),
                "serial_no": row.get("serial_no"),
                "batch_no": row.get("batch_no"),
                "disposition": "Restock",
                "inspection_result": "Pending",
            }
        )
    if len(sales_orders) == 1:
        result["sales_order"] = next(iter(sales_orders))
    if not result["delivery_note"] and len(delivery_notes) == 1:
        result["delivery_note"] = next(iter(delivery_notes))
    return result


@frappe.whitelist()
def load_source_items(source_doctype: str, source_name: str) -> dict:
    return get_source_details(source_doctype, source_name)


@frappe.whitelist()
def make_request_from_source(source_doctype: str, source_name: str) -> dict:
    frappe.has_permission("Sales Return Request", "create", throw=True)
    details = get_source_details(source_doctype, source_name)
    if not details["items"]:
        frappe.throw(_("This document has no quantity available to return."))
    request = frappe.new_doc("Sales Return Request")
    request.update({key: value for key, value in details.items() if key != "items"})
    request.source_doctype = source_doctype
    request.source_document = source_name
    request.requested_by = frappe.session.user
    for row in details["items"]:
        request.append("items", row)
    return request.as_dict()


@frappe.whitelist()
def make_return_delivery_note(name: str) -> dict:
    _require_role(WAREHOUSE_ROLES | {"Sales Team Leader", "Sales Supervisor"}, _("receive a sales return"))
    request = _get_submitted_rma(name)
    if not request.delivery_note:
        frappe.throw(_("Set the Delivery Note before receiving physical goods."))

    from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return

    target = make_sales_return(request.delivery_note)
    by_source_row = {row.delivery_note_item: row for row in request.items if row.delivery_note_item}
    kept = []
    for item in target.items:
        rma_row = by_source_row.get(item.dn_detail)
        if not rma_row or rma_row.disposition == "Credit Only":
            continue
        quantity = max(flt(rma_row.approved_qty) - flt(rma_row.received_qty), 0)
        if quantity <= 0:
            continue
        item.qty = -quantity
        item.warehouse = rma_row.return_warehouse or request.default_return_warehouse
        item.serial_no = rma_row.serial_no
        item.batch_no = rma_row.batch_no
        kept.append(item)
    if not kept:
        frappe.throw(_("There are no approved physical quantities left to receive."))
    target.set("items", kept)
    target.sales_return_request = request.name
    target.set_warehouse = ""
    target.run_method("calculate_taxes_and_totals")
    from otec_selling.branch_operations import validate_operation

    validate_operation(target)
    return target.as_dict()


@frappe.whitelist()
def make_credit_note(name: str) -> dict:
    _require_role(ACCOUNTS_ROLES, _("create a return credit note"))
    request = _get_submitted_rma(name)
    if not request.sales_invoice:
        frappe.throw(_("Set the Sales Invoice before creating a Credit Note."))

    from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

    target = make_sales_return(request.sales_invoice)
    by_source_row = {row.sales_invoice_item: row for row in request.items if row.sales_invoice_item}
    kept = []
    for item in target.items:
        rma_row = by_source_row.get(item.sales_invoice_item)
        if not rma_row:
            continue
        eligible = min(flt(rma_row.approved_qty), flt(rma_row.received_qty) + flt(rma_row.credit_only_qty))
        quantity = max(eligible - flt(rma_row.credited_qty), 0)
        if quantity <= 0:
            continue
        item.qty = -quantity
        kept.append(item)
    if not kept:
        frappe.throw(_("There are no received or credit-only quantities left to credit."))
    target.set("items", kept)
    target.update_stock = 0
    target.sales_return_request = request.name
    target.run_method("calculate_taxes_and_totals")
    return target.as_dict()


@frappe.whitelist()
def make_refund_payment(name: str) -> dict:
    _require_role(ACCOUNTS_ROLES, _("refund a sales return"))
    request = _get_submitted_rma(name)
    credit_note = frappe.db.get_value(
        "Sales Invoice",
        {"sales_return_request": request.name, "docstatus": 1, "is_return": 1},
        "name",
        order_by="posting_date desc, creation desc",
    )
    if not credit_note:
        frappe.throw(_("Submit a Credit Note before creating the refund."))
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    payment = get_payment_entry("Sales Invoice", credit_note)
    payment.sales_return_request = request.name
    return payment.as_dict()


@frappe.whitelist()
def mark_settlement_complete(name: str) -> None:
    _require_role(ACCOUNTS_ROLES, _("complete a sales-return settlement"))
    request = _get_submitted_rma(name)
    if request.credit_status != "Credited":
        frappe.throw(_("The approved return must be fully credited first."))
    request.db_set({"settlement_completed": 1, "settled_by": frappe.session.user, "settled_on": now_datetime()})
    sync_request(request.name)


def validate_linked_return(doc, method=None) -> None:
    request_name = doc.get("sales_return_request")
    if not request_name:
        return
    request = frappe.get_doc("Sales Return Request", request_name)
    if request.docstatus != 1:
        frappe.throw(_("Linked Sales Return Request must be approved."))
    if doc.doctype == "Delivery Note":
        if not doc.is_return or doc.return_against != request.delivery_note:
            frappe.throw(_("The linked Delivery Note must be a return against {0}.").format(request.delivery_note))
        allowed = {r.delivery_note_item: max(flt(r.approved_qty) - flt(r.received_qty), 0) for r in request.items}
        for row in doc.items:
            if abs(flt(row.qty)) > allowed.get(row.dn_detail, 0):
                frappe.throw(_("Row {0} exceeds the approved RMA quantity.").format(row.idx))
    elif doc.doctype == "Sales Invoice":
        if not doc.is_return or doc.return_against != request.sales_invoice:
            frappe.throw(_("The linked Sales Invoice must be a Credit Note against {0}.").format(request.sales_invoice))
        if doc.update_stock:
            frappe.throw(_("RMA Credit Notes cannot update stock. Use the Return Delivery Note for stock receipt."))
        allowed = {
            r.sales_invoice_item: max(
                min(flt(r.approved_qty), flt(r.received_qty) + flt(r.credit_only_qty)) - flt(r.credited_qty), 0
            )
            for r in request.items
        }
        for row in doc.items:
            if abs(flt(row.qty)) > allowed.get(row.sales_invoice_item, 0):
                frappe.throw(_("Row {0} exceeds the RMA quantity eligible for credit.").format(row.idx))
    elif doc.doctype == "Payment Entry":
        if doc.payment_type != "Pay" or doc.party_type != "Customer" or doc.party != request.customer:
            frappe.throw(_("An RMA refund must be a Pay transaction for customer {0}.").format(request.customer))


def sync_from_linked_document(doc, method=None) -> None:
    if doc.get("sales_return_request"):
        sync_request(doc.sales_return_request)


def sync_request(name: str) -> None:
    if not name or not frappe.db.exists("Sales Return Request", name):
        return
    request = frappe.get_doc("Sales Return Request", name)
    if request.docstatus != 1:
        return

    received = frappe._dict()
    for row in frappe.db.sql(
        """select dni.dn_detail, sum(abs(dni.qty)) qty
           from `tabDelivery Note Item` dni join `tabDelivery Note` dn on dn.name=dni.parent
           where dn.docstatus=1 and dn.is_return=1 and dn.sales_return_request=%s
           group by dni.dn_detail""",
        name,
        as_dict=True,
    ):
        received[row.dn_detail] = flt(row.qty)

    credited = frappe._dict()
    for row in frappe.db.sql(
        """select sii.sales_invoice_item, sum(abs(sii.qty)) qty
           from `tabSales Invoice Item` sii join `tabSales Invoice` si on si.name=sii.parent
           where si.docstatus=1 and si.is_return=1 and si.sales_return_request=%s
           group by sii.sales_invoice_item""",
        name,
        as_dict=True,
    ):
        credited[row.sales_invoice_item] = flt(row.qty)

    for row in request.items:
        frappe.db.set_value(
            row.doctype,
            row.name,
            {
                "received_qty": received.get(row.delivery_note_item, 0),
                "credited_qty": credited.get(row.sales_invoice_item, 0),
            },
            update_modified=False,
        )
        row.received_qty = received.get(row.delivery_note_item, 0)
        row.credited_qty = credited.get(row.sales_invoice_item, 0)

    physical = [r for r in request.items if r.disposition != "Credit Only" and flt(r.approved_qty) > 0]
    received_complete = all(flt(r.received_qty) >= flt(r.approved_qty) for r in physical)
    received_any = any(flt(r.received_qty) > 0 for r in physical)
    receive_status = "Received" if received_complete else ("Partially Received" if received_any else "Not Received")
    credit_complete = all(flt(r.credited_qty) >= flt(r.approved_qty) for r in request.items if flt(r.approved_qty) > 0)
    credit_any = any(flt(r.credited_qty) > 0 for r in request.items)
    credit_status = "Credited" if credit_complete else ("Partially Credited" if credit_any else "Not Credited")

    refund_total = flt(
        frappe.db.sql(
            """select coalesce(sum(paid_amount),0) from `tabPayment Entry`
               where docstatus=1 and payment_type='Pay' and sales_return_request=%s""",
            name,
        )[0][0]
    )
    total = flt(request.total_approved_amount)
    refund_status = "Not Required"
    if request.return_type == "Refund":
        refund_status = "Refunded" if refund_total >= total and total else ("Partially Refunded" if refund_total else "Pending")

    if not received_complete:
        status = "Partially Received" if received_any else "Awaiting Return"
    elif not credit_complete:
        status = "Credit Pending"
    elif request.return_type == "Refund" and refund_status != "Refunded":
        status = "Settlement Pending"
    elif request.return_type != "Refund" and not request.settlement_completed:
        status = "Settlement Pending"
    else:
        status = "Closed"

    request.db_set(
        {
            "receive_status": receive_status,
            "credit_status": credit_status,
            "refund_status": refund_status,
            "status": status,
            "refunded_amount": refund_total,
            "outstanding_settlement": max(total - refund_total, 0),
        },
        update_modified=False,
    )
