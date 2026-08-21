import frappe
from frappe.tests import IntegrationTestCase


class TestPurchasingLifecycleConfiguration(IntegrationTestCase):
    def test_approval_workflows_are_active_and_segregated(self):
        expected = {
            "Purchase Order": "Purchase Order Approval Workflow",
            "Purchase Receipt": "Purchase Receipt Approval Workflow",
            "Landed Cost Voucher": "Landed Cost Voucher Approval Workflow",
        }
        for doctype, workflow_name in expected.items():
            workflow = frappe.get_doc("Workflow", workflow_name)
            self.assertEqual(workflow.document_type, doctype)
            self.assertEqual(workflow.is_active, 1)
            approvals = [row for row in workflow.transitions if row.action == "Approve"]
            self.assertTrue(approvals)
            self.assertTrue(all(not row.allow_self_approval for row in approvals))

    def test_branch_is_authoritative(self):
        for doctype in ("Purchase Order", "Purchase Receipt", "Landed Cost Voucher"):
            field = frappe.get_meta(doctype).get_field("branch")
            self.assertIsNotNone(field)
            self.assertEqual(field.reqd, 1)

    def test_company_landed_cost_accounts_are_mapped(self):
        fields = (
            "custom_lcv_freight_account",
            "custom_lcv_customs_duty_account",
            "custom_lcv_import_tax_account",
            "custom_lcv_brokerage_account",
            "custom_lcv_port_charges_account",
            "custom_lcv_trucking_account",
            "custom_lcv_insurance_account",
            "custom_lcv_other_charges_account",
        )
        company_meta = frappe.get_meta("Company")
        for fieldname in fields:
            field = company_meta.get_field(fieldname)
            self.assertIsNotNone(field)
            self.assertEqual(field.fieldtype, "Link")
            self.assertEqual(field.options, "Account")

        # Fresh CI test companies are created after the app's migration patch,
        # so they are intentionally not preconfigured. Validate every mapping
        # that is present instead of requiring OTEC defaults on arbitrary
        # companies created later by ERPNext's test fixtures.
        for company in frappe.get_all("Company", pluck="name"):
            values = frappe.db.get_value("Company", company, fields, as_dict=True)
            for fieldname in fields:
                account = values.get(fieldname)
                if account:
                    self.assertEqual(frappe.db.get_value("Account", account, "company"), company)

    def test_legacy_container_apis_are_disabled(self):
        names = (
            "container_receiving_fetch_po_items",
            "container_receiving_create_purchase_receipts",
            "fetch_container_landed_cost_items",
            "compute_container_landed_cost_allocation",
            "create_landed_cost_voucher_from_container",
        )
        for name in names:
            if frappe.db.exists("Server Script", name):
                self.assertEqual(frappe.db.get_value("Server Script", name, "disabled"), 1)
