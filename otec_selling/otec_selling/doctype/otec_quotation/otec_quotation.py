from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class OTECQuotation(Document):
    def validate(self):
        self.set_item_master_values()
        self.calculate_totals()
        if self.docstatus == 0 and self.status not in ("Draft", "For Approval"):
            self.status = "Draft"

    def before_submit(self):
        if not self.approved_shop_drawing:
            frappe.throw(_("Attach the approved shop drawing before approving this quotation."))
        self.status = "Approved"

    def before_cancel(self):
        self.status = "Cancelled"

    def set_item_master_values(self):
        fields = [
            "item_name", "otec_main_product_category", "otec_secondary_product_category",
            "otec_series", "otec_minimum_sqm", "otec_sqm_rate", "otec_operable_available",
            "otec_operable_rate", "otec_glass_specification", "otec_frame_specification", "otec_color",
        ]
        previous = self.get_doc_before_save()
        previous_items = {
            row.name: row.item_code for row in (previous.items if previous else [])
        }
        for row in self.items:
            if not row.item_code:
                continue
            item_changed = previous_items.get(row.name) != row.item_code
            if not row.is_new() and not item_changed and row.item_name:
                continue
            values = frappe.db.get_value("Item", row.item_code, fields, as_dict=True) or {}
            row.item_name = values.get("item_name") or row.item_code
            row.main_product_category = values.get("otec_main_product_category")
            row.secondary_product_category = values.get("otec_secondary_product_category")
            row.series = values.get("otec_series")
            row.minimum_sqm = flt(values.get("otec_minimum_sqm"))
            row.sqm_rate = flt(values.get("otec_sqm_rate"))
            row.operable_available = flt(values.get("otec_operable_available"))
            row.operable_rate = flt(values.get("otec_operable_rate"))
            row.glass_specification = values.get("otec_glass_specification")
            row.frame_specification = values.get("otec_frame_specification")
            row.color = values.get("otec_color")
            if not row.operable_available:
                row.operable = 0

    def calculate_totals(self):
        category_shortfall = defaultdict(float)
        category_rows = defaultdict(list)

        for row in self.items:
            row.actual_sqm = flt(row.width_m) * flt(row.height_m)
            row.sqm_shortfall = max(flt(row.minimum_sqm) - row.actual_sqm, 0)
            category = row.main_product_category or "Uncategorized"
            category_shortfall[category] += row.sqm_shortfall
            category_rows[category].append(row)

        row_count = len(self.items)
        markup_per_row = flt(self.total_manual_markup) / row_count if row_count else 0
        items_subtotal = 0
        total_sets = 0

        for category, rows in category_rows.items():
            allocated_sqm = category_shortfall[category] / len(rows) if rows else 0
            for row in rows:
                row.allocated_sqm = allocated_sqm
                row.allocated_sqm_amount = allocated_sqm * flt(row.sqm_rate)
                row.base_line_amount = row.actual_sqm * flt(row.sqm_rate) * flt(row.sets)
                row.operable_amount = (
                    flt(row.operable_rate) * flt(row.sets) if row.operable and row.operable_available else 0
                )
                row.allocated_markup = markup_per_row
                row.amount = (
                    row.base_line_amount + row.allocated_sqm_amount + row.operable_amount + row.allocated_markup
                )
                row.unit_rate = row.amount / flt(row.sets) if flt(row.sets) else 0
                items_subtotal += row.amount
                total_sets += flt(row.sets)

        self.total_sets = total_sets
        self.items_subtotal = items_subtotal
        before_vat = items_subtotal + flt(self.delivery_fee) + flt(self.installation_fee)
        self.vat_amount = before_vat * flt(self.vat_rate) / 100 if self.apply_vat else 0
        self.grand_total = before_vat + self.vat_amount
