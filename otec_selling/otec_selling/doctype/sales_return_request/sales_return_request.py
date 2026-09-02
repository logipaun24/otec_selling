import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from otec_selling.sales_returns import get_source_details, sync_request


class SalesReturnRequest(Document):
    def validate(self):
        self._set_source_values()
        self._set_hierarchy()
        self._validate_items()
        self._calculate_totals()

    def before_submit(self):
        if self.workflow_state != "RMA Approved":
            frappe.throw(_("Approve the return through the workflow before submitting it."))
        if not {"Sales Team Leader", "Sales Supervisor", "Business Owner", "System Manager"}.intersection(frappe.get_roles()):
            frappe.throw(_("Only an existing sales approver may approve an RMA."))
        self.approved_by = frappe.session.user
        self.approved_on = now_datetime()
        self.status = "Awaiting Return"

    def on_submit(self):
        sync_request(self.name)

    def before_cancel(self):
        for doctype in ("Delivery Note", "Sales Invoice", "Payment Entry"):
            if frappe.db.exists(doctype, {"sales_return_request": self.name, "docstatus": 1}):
                frappe.throw(_("Cancel linked submitted returns, credits, and refunds before cancelling this RMA."))
        self.status = "Cancelled"

    def _set_source_values(self):
        source_doctype = self.source_doctype
        source_name = self.source_document
        if self.sales_invoice:
            source_doctype, source_name = "Sales Invoice", self.sales_invoice
        elif self.delivery_note:
            source_doctype, source_name = "Delivery Note", self.delivery_note
        if not source_doctype or not source_name:
            frappe.throw(_("Select a Sales Invoice or Delivery Note."))
        self.source_doctype = source_doctype
        self.source_document = source_name
        details = get_source_details(source_doctype, source_name)
        if not self.items:
            self.update({key: value for key, value in details.items() if key != "items" and value})
            for row in details["items"]:
                self.append("items", row)
        if self.company != details["company"] or self.customer != details["customer"]:
            frappe.throw(_("The company and customer must match the source document."))
        if not self.default_return_warehouse:
            self.default_return_warehouse = frappe.get_cached_value("Company", self.company, "default_warehouse_for_sales_return")
        if not self.quarantine_warehouse:
            self.quarantine_warehouse = frappe.get_cached_value("Company", self.company, "custom_sales_return_quarantine_warehouse")
        self._link_invoice_items()

    def _link_invoice_items(self):
        if not self.sales_invoice:
            return
        invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
        if invoice.docstatus != 1 or invoice.is_return or invoice.customer != self.customer or invoice.company != self.company:
            frappe.throw(_("Select a submitted, non-return Sales Invoice for the same customer and company."))
        by_delivery_row = {row.dn_detail: row for row in invoice.items if row.dn_detail}
        by_item = {}
        for row in invoice.items:
            by_item.setdefault(row.item_code, []).append(row)
        for rma_row in self.items:
            if rma_row.sales_invoice_item:
                continue
            invoice_row = by_delivery_row.get(rma_row.delivery_note_item)
            if not invoice_row and len(by_item.get(rma_row.item_code, [])) == 1:
                invoice_row = by_item[rma_row.item_code][0]
            if invoice_row:
                rma_row.sales_invoice = invoice.name
                rma_row.sales_invoice_item = invoice_row.name

    def _set_hierarchy(self):
        if not self.requested_by:
            self.requested_by = frappe.session.user
        routing_user = self.sales_user or self.requested_by
        records = frappe.get_all(
            "Sales Access Hierarchy",
            filters={"user": routing_user, "active": 1},
            fields=["position", "reports_to", "branch", "sales_team_group"],
            limit=2,
        )
        if len(records) > 1:
            frappe.throw(_("The requester has more than one active Sales Access Hierarchy record."))
        if records:
            self.creator_hierarchy_position = records[0].position
            self.sales_user = routing_user
            self.branch = self.branch or records[0].branch
            self.sales_team_group = self.sales_team_group or records[0].sales_team_group
            self.has_team_leader = 0
            if records[0].position == "Sales Representative" and records[0].reports_to:
                manager_position = frappe.db.get_value("Sales Access Hierarchy", records[0].reports_to, "position")
                if not manager_position:
                    manager_position = frappe.db.get_value("Sales Access Hierarchy", {"user": records[0].reports_to, "active": 1}, "position")
                self.has_team_leader = 1 if manager_position == "Team Leader" else 0
        elif "Sales Supervisor" in frappe.get_roles(self.requested_by) or "System Manager" in frappe.get_roles(self.requested_by):
            self.creator_hierarchy_position = "Supervisor"
        elif "Sales Team Leader" in frappe.get_roles(self.requested_by):
            self.creator_hierarchy_position = "Team Leader"
        else:
            frappe.throw(_("Configure an active Sales Access Hierarchy record for sales user {0}.").format(routing_user))

    def _validate_items(self):
        if not self.items:
            frappe.throw(_("At least one return item is required."))
        self.requires_business_owner_approval = 0
        for row in self.items:
            if flt(row.requested_qty) <= 0:
                frappe.throw(_("Requested quantity must be greater than zero on row {0}.").format(row.idx))
            if flt(row.requested_qty) > flt(row.available_qty):
                frappe.throw(_("Requested quantity exceeds the available return quantity on row {0}.").format(row.idx))
            if flt(row.approved_qty) < 0 or flt(row.approved_qty) > flt(row.requested_qty):
                frappe.throw(_("Approved quantity must be between zero and the requested quantity on row {0}.").format(row.idx))
            if row.disposition == "Credit Only":
                row.credit_only_qty = row.approved_qty
                self.requires_business_owner_approval = 1
            else:
                row.credit_only_qty = 0
                if not row.return_warehouse:
                    row.return_warehouse = self.quarantine_warehouse if row.disposition == "Quarantine" else self.default_return_warehouse
                if not row.return_warehouse:
                    frappe.throw(_("Select a return warehouse for row {0}.").format(row.idx))
                warehouse = frappe.db.get_value("Warehouse", row.return_warehouse, ["company", "is_group"], as_dict=True)
                if not warehouse or warehouse.company != self.company or warehouse.is_group:
                    frappe.throw(_("Return warehouse on row {0} must be a non-group warehouse for {1}.").format(row.idx, self.company))

    def _calculate_totals(self):
        self.total_approved_amount = 0
        for row in self.items:
            row.amount = flt(row.approved_qty) * flt(row.rate)
            self.total_approved_amount += row.amount
        self.outstanding_settlement = max(flt(self.total_approved_amount) - flt(self.refunded_amount), 0)
