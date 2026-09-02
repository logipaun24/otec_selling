import frappe
from frappe.tests import IntegrationTestCase


class TestSalesReturnConfiguration(IntegrationTestCase):
    def test_rma_metadata_and_workflow_exist(self):
        meta = frappe.get_meta("Sales Return Request")
        self.assertTrue(meta.is_submittable)
        self.assertTrue(meta.has_field("receive_status"))
        self.assertTrue(meta.has_field("credit_status"))
        self.assertTrue(frappe.db.exists("Workflow", "Sales Return Request Approval"))

    def test_standard_documents_link_to_rma(self):
        for doctype in ("Delivery Note", "Sales Invoice", "Payment Entry"):
            self.assertTrue(frappe.get_meta(doctype).has_field("sales_return_request"))

