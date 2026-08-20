import frappe
from frappe.tests import IntegrationTestCase


class TestOTECQuotation(IntegrationTestCase):
    def test_category_sqm_and_markup_are_allocated_per_row(self):
        doc = frappe.new_doc("OTEC Quotation")
        doc.total_manual_markup = 3000
        doc.delivery_fee = 1000
        doc.installation_fee = 2000
        doc.apply_vat = 1
        doc.vat_rate = 12
        for actual_width, minimum_sqm in ((1.0, 1.5), (2.0, 1.0), (3.0, 1.0)):
            row = doc.append("items", {})
            row.main_product_category = "Windows"
            row.width_m = actual_width
            row.height_m = 1
            row.minimum_sqm = minimum_sqm
            row.sqm_rate = 100
            row.sets = 1
        doc.calculate_totals()

        self.assertEqual(doc.items[0].allocated_sqm, 0.5 / 3)
        self.assertEqual(doc.items[0].allocated_markup, 1000)
        self.assertEqual(doc.total_sets, 3)
        self.assertAlmostEqual(doc.grand_total, (600 + 50 + 3000 + 3000) * 1.12)
