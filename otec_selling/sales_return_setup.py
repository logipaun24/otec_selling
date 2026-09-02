import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


CUSTOM_FIELDS = {
    "Company": [
        {
            "fieldname": "custom_sales_return_quarantine_warehouse",
            "label": "Sales Return Quarantine Warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "insert_after": "default_warehouse_for_sales_return",
        }
    ],
    "Delivery Note": [
        {
            "fieldname": "sales_return_request",
            "label": "Sales Return Request",
            "fieldtype": "Link",
            "options": "Sales Return Request",
            "insert_after": "return_against",
            "read_only": 1,
            "no_copy": 1,
        }
    ],
    "Sales Invoice": [
        {
            "fieldname": "sales_return_request",
            "label": "Sales Return Request",
            "fieldtype": "Link",
            "options": "Sales Return Request",
            "insert_after": "return_against",
            "read_only": 1,
            "no_copy": 1,
        }
    ],
    "Payment Entry": [
        {
            "fieldname": "sales_return_request",
            "label": "Sales Return Request",
            "fieldtype": "Link",
            "options": "Sales Return Request",
            "insert_after": "party_name",
            "read_only": 1,
            "no_copy": 1,
        }
    ],
}


def setup_sales_returns():
    frappe.reload_doc("otec_selling", "doctype", "sales_return_request_item", force=True)
    frappe.reload_doc("otec_selling", "doctype", "sales_return_request", force=True)
    create_custom_fields(CUSTOM_FIELDS, update=True)
    _ensure_workflow_records()
    frappe.clear_cache(doctype="Sales Return Request")


def _ensure_named(doctype: str, name: str):
    if not frappe.db.exists(doctype, name):
        fieldname = "workflow_state_name" if doctype == "Workflow State" else "workflow_action_name"
        frappe.get_doc({"doctype": doctype, fieldname: name}).insert(ignore_permissions=True)


def _ensure_workflow_records():
    states = ["RMA Draft", "RMA Pending Approval", "RMA Pending Business Owner", "RMA Approved", "RMA Rejected", "RMA Cancelled"]
    actions = ["Request Return Approval", "Approve Return", "Reject Return", "Revise Return"]
    for state in states:
        _ensure_named("Workflow State", state)
    for action in actions:
        _ensure_named("Workflow Action Master", action)

    name = "Sales Return Request Approval"
    values = {
            "doctype": "Workflow",
            "workflow_name": name,
            "document_type": "Sales Return Request",
            "workflow_state_field": "workflow_state",
            "is_active": 1,
            "override_status": 0,
            "send_email_alert": 1,
            "states": [
                *[{"state": "RMA Draft", "doc_status": "0", "allow_edit": role} for role in ("Sales User", "Sales Team Leader", "Sales Supervisor")],
                *[{"state": "RMA Pending Approval", "doc_status": "0", "allow_edit": role} for role in ("Sales Team Leader", "Sales Supervisor")],
                {"state": "RMA Pending Business Owner", "doc_status": "0", "allow_edit": "Business Owner"},
                {"state": "RMA Approved", "doc_status": "1", "allow_edit": "Sales Supervisor"},
                *[{"state": "RMA Rejected", "doc_status": "0", "allow_edit": role} for role in ("Sales User", "Sales Team Leader", "Sales Supervisor")],
                {"state": "RMA Cancelled", "doc_status": "2", "allow_edit": "Sales Supervisor"},
            ],
            "transitions": [
                {"state": "RMA Draft", "action": "Request Return Approval", "next_state": "RMA Pending Approval", "allowed": "Sales User", "condition": 'doc.creator_hierarchy_position == "Sales Representative"'},
                {"state": "RMA Draft", "action": "Approve Return", "next_state": "RMA Approved", "allowed": "Sales Team Leader", "condition": "doc.requires_business_owner_approval == 0", "allow_self_approval": 1},
                {"state": "RMA Draft", "action": "Approve Return", "next_state": "RMA Approved", "allowed": "Sales Supervisor", "condition": "doc.requires_business_owner_approval == 0", "allow_self_approval": 1},
                {"state": "RMA Draft", "action": "Approve Return", "next_state": "RMA Pending Business Owner", "allowed": "Sales Team Leader", "condition": "doc.requires_business_owner_approval == 1", "allow_self_approval": 1},
                {"state": "RMA Draft", "action": "Approve Return", "next_state": "RMA Pending Business Owner", "allowed": "Sales Supervisor", "condition": "doc.requires_business_owner_approval == 1", "allow_self_approval": 1},
                {"state": "RMA Pending Approval", "action": "Approve Return", "next_state": "RMA Approved", "allowed": "Sales Team Leader", "condition": "doc.requires_business_owner_approval == 0"},
                {"state": "RMA Pending Approval", "action": "Approve Return", "next_state": "RMA Approved", "allowed": "Sales Supervisor", "condition": "doc.requires_business_owner_approval == 0"},
                {"state": "RMA Pending Approval", "action": "Approve Return", "next_state": "RMA Pending Business Owner", "allowed": "Sales Team Leader", "condition": "doc.requires_business_owner_approval == 1"},
                {"state": "RMA Pending Approval", "action": "Approve Return", "next_state": "RMA Pending Business Owner", "allowed": "Sales Supervisor", "condition": "doc.requires_business_owner_approval == 1"},
                {"state": "RMA Pending Approval", "action": "Reject Return", "next_state": "RMA Rejected", "allowed": "Sales Team Leader"},
                {"state": "RMA Pending Approval", "action": "Reject Return", "next_state": "RMA Rejected", "allowed": "Sales Supervisor"},
                {"state": "RMA Pending Business Owner", "action": "Approve Return", "next_state": "RMA Approved", "allowed": "Business Owner"},
                {"state": "RMA Pending Business Owner", "action": "Reject Return", "next_state": "RMA Rejected", "allowed": "Business Owner"},
                {"state": "RMA Rejected", "action": "Revise Return", "next_state": "RMA Draft", "allowed": "Sales User", "allow_self_approval": 1},
                {"state": "RMA Rejected", "action": "Revise Return", "next_state": "RMA Draft", "allowed": "Sales Team Leader", "allow_self_approval": 1},
                {"state": "RMA Rejected", "action": "Revise Return", "next_state": "RMA Draft", "allowed": "Sales Supervisor", "allow_self_approval": 1}
            ],
        }
    if frappe.db.exists("Workflow", name):
        workflow = frappe.get_doc("Workflow", name)
        workflow.update(values)
        workflow.set("states", values["states"])
        workflow.set("transitions", values["transitions"])
        workflow.save(ignore_permissions=True)
    else:
        frappe.get_doc(values).insert(ignore_permissions=True)
