from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ITEM_FIELDS = {
    "Item": [
        {
            "fieldname": "otec_quotation_pricing_section",
            "label": "OTEC Quotation Pricing",
            "fieldtype": "Section Break",
            "insert_after": "description",
            "collapsible": 1,
        },
        {
            "fieldname": "otec_main_product_category",
            "label": "Main Product Category",
            "fieldtype": "Select",
            "options": "\nWindows\nDoors\nCurtain Wall",
            "insert_after": "otec_quotation_pricing_section",
        },
        {
            "fieldname": "otec_secondary_product_category",
            "label": "Secondary Product Category",
            "fieldtype": "Data",
            "insert_after": "otec_main_product_category",
        },
        {
            "fieldname": "otec_series",
            "label": "Series",
            "fieldtype": "Data",
            "insert_after": "otec_secondary_product_category",
        },
        {
            "fieldname": "otec_pricing_column",
            "fieldtype": "Column Break",
            "insert_after": "otec_series",
        },
        {
            "fieldname": "otec_minimum_sqm",
            "label": "Minimum SQM",
            "fieldtype": "Float",
            "precision": 4,
            "non_negative": 1,
            "insert_after": "otec_pricing_column",
        },
        {
            "fieldname": "otec_sqm_rate",
            "label": "Rate per SQM",
            "fieldtype": "Currency",
            "non_negative": 1,
            "insert_after": "otec_minimum_sqm",
        },
        {
            "fieldname": "otec_operable_available",
            "label": "Operable Available",
            "fieldtype": "Check",
            "insert_after": "otec_sqm_rate",
        },
        {
            "fieldname": "otec_operable_rate",
            "label": "Operable Rate",
            "fieldtype": "Currency",
            "non_negative": 1,
            "depends_on": "eval:doc.otec_operable_available",
            "insert_after": "otec_operable_available",
        },
        {
            "fieldname": "otec_specs_section",
            "label": "Default Specifications",
            "fieldtype": "Section Break",
            "insert_after": "otec_operable_rate",
            "collapsible": 1,
        },
        {
            "fieldname": "otec_glass_specification",
            "label": "Glass Specification",
            "fieldtype": "Data",
            "insert_after": "otec_specs_section",
        },
        {
            "fieldname": "otec_frame_specification",
            "label": "Frame Specification",
            "fieldtype": "Data",
            "insert_after": "otec_glass_specification",
        },
        {
            "fieldname": "otec_color",
            "label": "Color",
            "fieldtype": "Data",
            "insert_after": "otec_frame_specification",
        },
    ]
}


def setup_otec_quotation():
    # OTEC Quotation previously existed as an empty custom DocType fixture.
    # Reload the version-controlled standard schema after fixtures are imported.
    frappe.reload_doc("otec_selling", "doctype", "otec_quotation", force=True)
    frappe.reload_doc("otec_selling", "doctype", "otec_quotation_item", force=True)
    create_custom_fields(ITEM_FIELDS, update=True)
    _install_print_format()


def _install_print_format():
    template_path = Path(
        frappe.get_app_path(
            "otec_selling", "templates", "print_formats", "otec_initial_quotation.html"
        )
    )
    html = template_path.read_text(encoding="utf-8")
    name = "OTEC Initial Quotation"

    if frappe.db.exists("Print Format", name):
        print_format = frappe.get_doc("Print Format", name)
        print_format.update(
            {
                "doc_type": "OTEC Quotation",
                "module": "OTEC Selling",
                "custom_format": 1,
                "print_format_type": "Jinja",
                "html": html,
                "disabled": 0,
            }
        )
        print_format.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Print Format",
                "name": name,
                "doc_type": "OTEC Quotation",
                "module": "OTEC Selling",
                "custom_format": 1,
                "print_format_type": "Jinja",
                "html": html,
            }
        ).insert(ignore_permissions=True)

    frappe.db.set_value(
        "DocType", "OTEC Quotation", "default_print_format", name, update_modified=False
    )
