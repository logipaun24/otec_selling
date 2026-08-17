from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _ensure_role(role: str) -> None:
    if not frappe.db.exists("Role", role):
        frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
            ignore_permissions=True
        )


def _property_setter(doctype: str, fieldname: str, prop: str, value, prop_type: str) -> None:
    filters = {
        "doc_type": doctype,
        "field_name": fieldname,
        "property": prop,
    }
    name = frappe.db.exists("Property Setter", filters)
    if name:
        doc = frappe.get_doc("Property Setter", name)
        doc.value = value
        doc.property_type = prop_type
        doc.save(ignore_permissions=True)
        return
    frappe.get_doc(
        {
            "doctype": "Property Setter",
            "doctype_or_field": "DocField",
            "doc_type": doctype,
            "field_name": fieldname,
            "property": prop,
            "value": value,
            "property_type": prop_type,
        }
    ).insert(ignore_permissions=True)


def _permission(doctype: str, role: str, **values) -> None:
    filters = {"parent": doctype, "role": role, "permlevel": 0}
    name = frappe.db.exists("Custom DocPerm", filters)
    doc = frappe.get_doc("Custom DocPerm", name) if name else frappe.new_doc("Custom DocPerm")
    doc.parent = doctype
    doc.parenttype = "DocType"
    doc.parentfield = "permissions"
    doc.role = role
    doc.permlevel = 0
    for field in (
        "read",
        "write",
        "create",
        "submit",
        "cancel",
        "amend",
        "delete",
        "report",
        "export",
        "import",
        "share",
        "print",
        "email",
    ):
        if doc.meta.has_field(field):
            doc.set(field, int(values.get(field, 0)))
    if name:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)


def _ensure_workflow_master(doctype: str, name_field: str, names: set[str]) -> None:
    for name in names:
        if not frappe.db.exists(doctype, name):
            frappe.get_doc({"doctype": doctype, name_field: name}).insert(ignore_permissions=True)


def _workflow(name: str, document_type: str, states: list[dict], transitions: list[dict]) -> None:
    for other in frappe.get_all(
        "Workflow",
        filters={"document_type": document_type, "name": ["!=", name]},
        pluck="name",
    ):
        frappe.db.set_value("Workflow", other, "is_active", 0)

    if frappe.db.exists("Workflow", name):
        workflow = frappe.get_doc("Workflow", name)
        workflow.set("states", [])
        workflow.set("transitions", [])
    else:
        workflow = frappe.new_doc("Workflow")
        workflow.workflow_name = name
        workflow.document_type = document_type

    workflow.is_active = 1
    workflow.workflow_state_field = "workflow_state"
    workflow.send_email_alert = 0
    workflow.override_status = 0
    workflow.enable_action_confirmation = 1
    for row in states:
        workflow.append("states", row)
    for row in transitions:
        workflow.append("transitions", row)
    if workflow.is_new():
        workflow.insert(ignore_permissions=True)
    else:
        workflow.save(ignore_permissions=True)


def _transitions(
    pending_state: str,
    creator_roles: list[str],
    approver_roles: list[str],
) -> list[dict]:
    rows = []
    for role in creator_roles + approver_roles:
        rows.append(
            {
                "state": "Draft",
                "action": "Request Approval",
                "next_state": pending_state,
                "allowed": role,
                "allow_self_approval": 1,
            }
        )
    for role in approver_roles:
        rows.extend(
            [
                {
                    "state": pending_state,
                    "action": "Approve",
                    "next_state": "Approved",
                    "allowed": role,
                    "allow_self_approval": 0,
                },
                {
                    "state": pending_state,
                    "action": "Reject",
                    "next_state": "Rejected",
                    "allowed": role,
                    "allow_self_approval": 0,
                },
                {
                    "state": "Approved",
                    "action": "Cancel",
                    "next_state": "Cancelled",
                    "allowed": role,
                    "allow_self_approval": 0,
                },
            ]
        )
    for role in creator_roles + approver_roles:
        rows.append(
            {
                "state": "Rejected",
                "action": "Revise",
                "next_state": "Draft",
                "allowed": role,
                "allow_self_approval": 1,
            }
        )
    return rows


def _default_expense_account(company: str) -> str | None:
    submitted = frappe.db.sql(
        """
        select tax.expense_account
          from `tabLanded Cost Taxes and Charges` tax
          join `tabLanded Cost Voucher` lcv on lcv.name = tax.parent
         where lcv.company = %s and lcv.docstatus = 1 and tax.expense_account is not null
         order by lcv.modified desc, tax.idx
         limit 1
        """,
        company,
    )
    if submitted:
        return submitted[0][0]
    default = frappe.db.get_value("Company", company, "default_expense_account")
    if default:
        return default
    return frappe.db.get_value(
        "Account",
        {"company": company, "root_type": "Expense", "is_group": 0},
        "name",
    )


def execute() -> None:
    roles = {
        "Inventory Controller",
        "Inventory Controller Supervisor",
        "Warehouse Picker",
        "Business Owner",
        "General Manager",
    }
    for role in roles:
        _ensure_role(role)

    create_custom_fields(
        {
            "Company": [
                {
                    "fieldname": "custom_lcv_account_mapping_section",
                    "label": "Landed Cost Account Mapping",
                    "fieldtype": "Section Break",
                    "insert_after": "default_expense_account",
                },
                *[
                    {
                        "fieldname": fieldname,
                        "label": label + " Account",
                        "fieldtype": "Link",
                        "options": "Account",
                        "insert_after": "custom_lcv_account_mapping_section" if index == 0 else previous,
                    }
                    for index, (label, fieldname, previous) in enumerate(
                        [
                            ("Freight", "custom_lcv_freight_account", "custom_lcv_account_mapping_section"),
                            ("Customs Duty", "custom_lcv_customs_duty_account", "custom_lcv_freight_account"),
                            ("Import Tax", "custom_lcv_import_tax_account", "custom_lcv_customs_duty_account"),
                            ("Brokerage", "custom_lcv_brokerage_account", "custom_lcv_import_tax_account"),
                            ("Port Charges", "custom_lcv_port_charges_account", "custom_lcv_brokerage_account"),
                            ("Trucking", "custom_lcv_trucking_account", "custom_lcv_port_charges_account"),
                            ("Insurance", "custom_lcv_insurance_account", "custom_lcv_trucking_account"),
                            ("Other Landed Charges", "custom_lcv_other_charges_account", "custom_lcv_insurance_account"),
                        ]
                    )
                ],
            ],
            "Purchase Order": [
                {
                    "fieldname": "branch",
                    "label": "Branch",
                    "fieldtype": "Link",
                    "options": "Branch",
                    "insert_after": "cost_center",
                    "reqd": 1,
                    "in_standard_filter": 1,
                }
            ],
            "Purchase Order Item": [
                {
                    "fieldname": "branch",
                    "label": "Branch",
                    "fieldtype": "Link",
                    "options": "Branch",
                    "insert_after": "project",
                    "read_only": 1,
                }
            ],
            "Purchase Receipt": [
                {
                    "fieldname": "branch",
                    "label": "Branch",
                    "fieldtype": "Link",
                    "options": "Branch",
                    "insert_after": "cost_center",
                    "reqd": 1,
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_container_receiving",
                    "label": "Container Receiving",
                    "fieldtype": "Link",
                    "options": "Container Receiving",
                    "insert_after": "branch",
                    "read_only": 1,
                    "no_copy": 1,
                },
                {
                    "fieldname": "custom_container_no",
                    "label": "Container Number",
                    "fieldtype": "Data",
                    "insert_after": "custom_container_receiving",
                    "read_only": 1,
                    "no_copy": 1,
                },
            ],
            "Purchase Receipt Item": [
                {
                    "fieldname": "branch",
                    "label": "Branch",
                    "fieldtype": "Link",
                    "options": "Branch",
                    "insert_after": "project",
                    "read_only": 1,
                }
            ],
            "Landed Cost Voucher": [
                {
                    "fieldname": "branch",
                    "label": "Branch",
                    "fieldtype": "Link",
                    "options": "Branch",
                    "insert_after": "company",
                    "reqd": 1,
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "custom_allow_additional_landed_cost",
                    "label": "Allow Additional Landed Cost",
                    "fieldtype": "Check",
                    "insert_after": "branch",
                    "description": "Use only for an approved incremental landed cost on a previously costed receipt.",
                },
            ],
            "Landed Cost Item": [
                {
                    "fieldname": "branch",
                    "label": "Branch",
                    "fieldtype": "Link",
                    "options": "Branch",
                    "insert_after": "cost_center",
                    "read_only": 1,
                }
            ],
            "Container Landed Cost": [
                {
                    "fieldname": "branch",
                    "label": "Branch",
                    "fieldtype": "Link",
                    "options": "Branch",
                    "insert_after": "company",
                    "reqd": 1,
                }
            ],
        },
        update=True,
    )

    _property_setter(
        "Container Receiving",
        "status",
        "options",
        "Draft\nScanning\nReceipts Created\nPartially Submitted\nCompleted\nCancelled",
        "Text",
    )
    _property_setter(
        "Container Landed Cost",
        "status",
        "options",
        "Draft\nComputed\nAwaiting LCV Approval\nSubmitted\nCancelled",
        "Text",
    )

    full = dict(read=1, write=1, create=1, submit=1, cancel=1, amend=1, delete=1, report=1, export=1, share=1, print=1, email=1)
    creator = dict(read=1, write=1, create=1, report=1, export=1, print=1, email=1)
    reader = dict(read=1, report=1, export=1, print=1)

    for role in ("Purchase Manager", "General Manager", "Business Owner"):
        _permission("Purchase Order", role, **full)
    for role in ("Inventory Controller",):
        _permission("Purchase Receipt", role, **creator)
        _permission("Container Receiving", role, **creator)
    for role in ("Inventory Controller Supervisor", "Stock Manager", "General Manager", "Business Owner"):
        _permission("Purchase Receipt", role, **full)
        _permission("Container Receiving", role, **full)
    _permission("Purchase Receipt", "Warehouse Picker", **reader)
    _permission("Container Receiving", "Warehouse Picker", **reader)
    for role in ("Stock Manager", "Accounts Manager", "General Manager", "Business Owner"):
        _permission("Landed Cost Voucher", role, **full)
        _permission("Container Landed Cost", role, **full)
    _permission("Landed Cost Voucher", "Accounts User", **creator)
    _permission("Container Landed Cost", "Accounts User", **creator)
    _permission("Container Landed Cost", "Inventory Controller Supervisor", **reader)

    workflow_states = {
        "Pending Purchase Approval",
        "Pending Receiving Approval",
        "Pending Landed Cost Approval",
        "Draft",
        "Approved",
        "Rejected",
        "Cancelled",
    }
    _ensure_workflow_master("Workflow State", "workflow_state_name", workflow_states)
    _ensure_workflow_master(
        "Workflow Action Master",
        "workflow_action_name",
        {"Request Approval", "Approve", "Reject", "Revise", "Cancel"},
    )

    _workflow(
        "Purchase Order Approval Workflow",
        "Purchase Order",
        [
            {"state": "Draft", "doc_status": "0", "allow_edit": "Purchase User"},
            {"state": "Pending Purchase Approval", "doc_status": "0", "allow_edit": "Purchase Manager"},
            {"state": "Approved", "doc_status": "1", "allow_edit": "Purchase Manager"},
            {"state": "Rejected", "doc_status": "0", "allow_edit": "Purchase User"},
            {"state": "Cancelled", "doc_status": "2", "allow_edit": "Purchase Manager"},
        ],
        _transitions(
            "Pending Purchase Approval",
            ["Purchase User"],
            ["Purchase Manager", "General Manager", "Business Owner"],
        ),
    )
    _workflow(
        "Purchase Receipt Approval Workflow",
        "Purchase Receipt",
        [
            {"state": "Draft", "doc_status": "0", "allow_edit": "Inventory Controller"},
            {"state": "Pending Receiving Approval", "doc_status": "0", "allow_edit": "Inventory Controller Supervisor"},
            {"state": "Approved", "doc_status": "1", "allow_edit": "Inventory Controller Supervisor"},
            {"state": "Rejected", "doc_status": "0", "allow_edit": "Inventory Controller"},
            {"state": "Cancelled", "doc_status": "2", "allow_edit": "Inventory Controller Supervisor"},
        ],
        _transitions(
            "Pending Receiving Approval",
            ["Inventory Controller", "Purchase User", "Stock User"],
            ["Inventory Controller Supervisor", "Stock Manager", "General Manager", "Business Owner"],
        ),
    )
    _workflow(
        "Landed Cost Voucher Approval Workflow",
        "Landed Cost Voucher",
        [
            {"state": "Draft", "doc_status": "0", "allow_edit": "Stock Manager"},
            {"state": "Pending Landed Cost Approval", "doc_status": "0", "allow_edit": "Accounts Manager"},
            {"state": "Approved", "doc_status": "1", "allow_edit": "Accounts Manager"},
            {"state": "Rejected", "doc_status": "0", "allow_edit": "Stock Manager"},
            {"state": "Cancelled", "doc_status": "2", "allow_edit": "Accounts Manager"},
        ],
        _transitions(
            "Pending Landed Cost Approval",
            ["Stock Manager", "Accounts User"],
            ["Accounts Manager", "General Manager", "Business Owner"],
        ),
    )

    for company in frappe.get_all("Company", pluck="name"):
        account = _default_expense_account(company)
        if not account:
            continue
        frappe.db.set_value(
            "Company",
            company,
            {
                "custom_lcv_freight_account": account,
                "custom_lcv_customs_duty_account": account,
                "custom_lcv_import_tax_account": account,
                "custom_lcv_brokerage_account": account,
                "custom_lcv_port_charges_account": account,
                "custom_lcv_trucking_account": account,
                "custom_lcv_insurance_account": account,
                "custom_lcv_other_charges_account": account,
            },
            update_modified=False,
        )

    for name in (
        "container_receiving_fetch_po_items",
        "container_receiving_create_purchase_receipts",
        "fetch_container_landed_cost_items",
        "compute_container_landed_cost_allocation",
        "create_landed_cost_voucher_from_container",
    ):
        if frappe.db.exists("Server Script", name):
            frappe.db.set_value("Server Script", name, "disabled", 1)
    for name in ("Container Receiving", "Container LCV Fetch Button"):
        if frappe.db.exists("Client Script", name):
            frappe.db.set_value("Client Script", name, "enabled", 0)

    split_name = "split_purchase_receipt_into_boxes"
    if frappe.db.exists("Server Script", split_name):
        split = frappe.get_doc("Server Script", split_name)
        marker = "# OTEC_ROLE_GUARD_V1"
        if marker not in split.script:
            split.script = (
                marker
                + "\nallowed_roles = ('Inventory Controller Supervisor', 'Stock Manager', 'General Manager', 'Business Owner')\n"
                + "if frappe.session.user != 'Administrator' and not any(role in frappe.get_roles() for role in allowed_roles):\n"
                + "    frappe.throw('You are not authorized to split received stock into box batches.')\n\n"
                + split.script
            )
            split.save(ignore_permissions=True)

    frappe.db.sql(
        """
        update `tabContainer Landed Cost` clc
        left join `tabLanded Cost Voucher` lcv on lcv.name = clc.landed_cost_voucher
           set clc.status = case
               when clc.docstatus = 2 then 'Cancelled'
               when lcv.docstatus = 1 then 'Submitted'
               when clc.landed_cost_voucher is not null then 'Awaiting LCV Approval'
               else clc.status
           end
        """
    )

    for name in frappe.get_all("Container Receiving", pluck="name"):
        from otec_selling.purchasing_lifecycle import _sync_container_receiving

        _sync_container_receiving(name)

    frappe.clear_cache()
