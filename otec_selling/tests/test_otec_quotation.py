import json

import frappe
from frappe.tests import IntegrationTestCase

from otec_selling.otec_selling.doctype.otec_quotation.otec_quotation import calculate_quotation


# These tests exercise in-memory pricing math. Keeping them outside the
# DocType test module prevents Frappe from generating unrelated ERPNext test
# records merely to construct unsaved OTEC Quotation documents.
class TestOTECQuotation(IntegrationTestCase):
    def test_calculation_endpoint_accepts_serialized_desk_document(self):
        doc = frappe.new_doc("OTEC Quotation")
        row = doc.append("items", {})
        row.main_product_category = "Windows"
        row.width_m = 1
        row.height_m = 1
        row.minimum_sqm = 1.35
        row.sqm_rate = 8400
        row.sets = 1

        result = calculate_quotation(json.dumps(doc.as_dict()))

        self.assertAlmostEqual(result["items"][0]["amount"], 1.35 * 8400)

    def test_single_row_still_enforces_minimum_sqm(self):
        doc = frappe.new_doc("OTEC Quotation")
        row = doc.append("items", {})
        row.main_product_category = "Windows"
        row.width_m = 1
        row.height_m = 1
        row.minimum_sqm = 1.35
        row.sqm_rate = 8400
        row.sets = 1

        doc.calculate_totals()

        self.assertAlmostEqual(row.allocated_sqm, 0.35)
        self.assertAlmostEqual(row.amount, 1.35 * 8400)

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

        # Shortfall pool = 0.5 (row 1 only). Row 1 has the highest shortfall
        # so it receives none of the pool; rows 2+3 split it proportionally
        # to their actual SQM (eligible total = 2.0 + 3.0 = 5.0).
        self.assertEqual(doc.items[0].allocated_sqm, 0)
        self.assertAlmostEqual(doc.items[1].allocated_sqm, 0.5 * (2.0 / 5.0))
        self.assertAlmostEqual(doc.items[2].allocated_sqm, 0.5 * (3.0 / 5.0))
        self.assertEqual(doc.items[0].allocated_markup, 1000)
        self.assertEqual(doc.total_sets, 3)
        self.assertAlmostEqual(doc.grand_total, (600 + 50 + 3000 + 3000) * 1.12)
