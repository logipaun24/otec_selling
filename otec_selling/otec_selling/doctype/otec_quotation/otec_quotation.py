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
            "otec_operable_rate", "otec_aluminum_thickness", "otec_glass_specification",
            "otec_frame_specification", "otec_color", "otec_addon_notes",
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
            row.aluminum_thickness = values.get("otec_aluminum_thickness")
            row.glass_specification = values.get("otec_glass_specification")
            row.frame_specification = values.get("otec_frame_specification")
            row.color = values.get("otec_color")
            row.addon_notes = values.get("otec_addon_notes")
            if not row.operable_available:
                row.operable = 0

    def calculate_totals(self):
        category_shortfall = defaultdict(float)
        category_actual_sqm = defaultdict(float)
        category_rows = defaultdict(list)

        for row in self.items:
            row.actual_sqm = flt(row.width_m) * flt(row.height_m)
            row.sqm_shortfall = max(flt(row.minimum_sqm) - row.actual_sqm, 0)
            category = row.main_product_category or "Uncategorized"
            category_shortfall[category] += row.sqm_shortfall
            category_actual_sqm[category] += row.actual_sqm
            category_rows[category].append(row)

        row_count = len(self.items)
        markup_per_row = flt(self.total_manual_markup) / row_count if row_count else 0
        items_subtotal = 0
        total_sets = 0

        for category, rows in category_rows.items():
            # Rows tied for the highest shortfall receive none of the pool;
            # everyone else splits it proportionally to actual SQM.
            max_shortfall = max((row.sqm_shortfall for row in rows), default=0)
            eligible = [row for row in rows if row.sqm_shortfall < max_shortfall]
            eligible_actual_sqm = sum(row.actual_sqm for row in eligible)
            for row in rows:
                if row.sqm_shortfall >= max_shortfall:
                    row.allocated_sqm = 0
                else:
                    row.allocated_sqm = (
                        category_shortfall[category] * row.actual_sqm / eligible_actual_sqm
                        if eligible_actual_sqm
                        else 0
                    )
                row.allocated_sqm_amount = row.allocated_sqm * flt(row.sqm_rate)
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


@frappe.whitelist()
def calculate_quotation(doc):
    """Compute item master values and totals from the form's current state.

    Used by the "Calculate Totals" button: the document dict is sent from
    the client, recomputed server-side, and the results returned so the
    form can be refreshed. No record is saved.
    """
    data = frappe._dict(doc)
    # Build an unsaved document from the submitted data so edits made in
    # the form (including on a previously saved quotation) are respected.
    data["name"] = None
    quotation = frappe.get_doc(data)
    quotation.set_item_master_values()
    quotation.calculate_totals()
    return {
        "items": [row.as_dict() for row in quotation.items],
        "total_sets": quotation.total_sets,
        "items_subtotal": quotation.items_subtotal,
        "vat_amount": quotation.vat_amount,
        "grand_total": quotation.grand_total,
    }
