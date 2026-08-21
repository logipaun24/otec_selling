from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from otec_selling.quotation_catalog import setup_catalog

ALUMINUM_THICKNESS = "\n1.4\n1.6\n1.8\n2.0\n3.0\n4.0"

GLASS_TYPES = (
	"\n5mm + 20A + 5mm\n5mm + 14A + 5mm\n5mm + 12A + 5mm"
	"\n8mm\n6mm\n6mm + 12A + 6mm\n6mm + 1.52pvb + 6mm"
	"\nNylon Mesh\nMetal\nA10 Uchannel"
)

STOCK_COLORS = "\nGray\nBlack\nBrown"

# Add-on options with their rates, from the OTEC price list (June 3, 2026).
ADDONS = [
	{
		"addon_name": "Integrated Grills",
		"rate": 2700,
		"description": "Per SQM. For windows with integrated grills.",
	},
	{
		"addon_name": "High Visibility Metal Screen",
		"rate": 2500,
		"description": "Per panel (Slide Up windows).",
	},
	{"addon_name": "Fixed Metal Screen", "rate": 2500, "description": "Per panel (Glass Louver)."},
	{"addon_name": "Key Lockset", "rate": 2500, "description": "Folding / Sliding / Swing doors."},
	{"addon_name": "Key Lockset (Narrow)", "rate": 2000, "description": "Folding Narrow (45*16)."},
	{"addon_name": "Pair of Big Handles", "rate": 2000, "description": "Sliding doors."},
	{"addon_name": "Locksets (208 Series)", "rate": 8000, "description": "3 Tracks 208 Series sliding."},
	{"addon_name": "Buffers / Soft Close", "rate": 1800, "description": "Each (Narrow Frames)."},
	{
		"addon_name": "Ground Rail Buffer",
		"rate": 960,
		"description": "With ground rail buffer (Narrow Frames).",
	},
	{"addon_name": "Handle Key Lock", "rate": 2000, "description": "Telescopic sliding."},
	{
		"addon_name": "Linkage (No Bottom Track)",
		"rate": 6600,
		"description": "Telescopic sliding, no bottom track.",
	},
	{"addon_name": "Mirror Type Slim Profile", "rate": 2500, "description": "Per SQM. Ghost Door."},
	{"addon_name": "Soft Screen", "rate": 4306, "description": "Per SQM. Slide and Swing."},
	{"addon_name": "Aluminum Strips in Insulated Glass", "rate": 800, "description": "Per SQM."},
]

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
			"label": "Legacy Default Specifications",
			"fieldtype": "Section Break",
			"insert_after": "otec_operable_rate",
			"collapsible": 1,
			"hidden": 1,
		},
		{
			"fieldname": "otec_aluminum_thickness",
			"label": "Aluminum Thickness",
			"fieldtype": "Select",
			"options": ALUMINUM_THICKNESS,
			"insert_after": "otec_specs_section",
			"hidden": 1,
		},
		{
			"fieldname": "otec_glass_specification",
			"label": "Glass Specification",
			"fieldtype": "Select",
			"options": GLASS_TYPES,
			"insert_after": "otec_aluminum_thickness",
			"hidden": 1,
		},
		{
			"fieldname": "otec_frame_specification",
			"label": "Frame Specification",
			"fieldtype": "Data",
			"insert_after": "otec_glass_specification",
			"hidden": 1,
		},
		{
			"fieldname": "otec_color",
			"label": "Color",
			"fieldtype": "Select",
			"options": STOCK_COLORS,
			"insert_after": "otec_frame_specification",
			"hidden": 1,
		},
		{
			"fieldname": "otec_addon_information_section",
			"label": "OTEC Quotation Add-on Information",
			"fieldtype": "Section Break",
			"insert_after": "otec_color",
			"collapsible": 1,
		},
		{
			"fieldname": "otec_addon_notes",
			"label": "Add-on Notes",
			"fieldtype": "Text",
			"insert_after": "otec_addon_information_section",
			"description": "Surcharges and options from the OTEC price list (grills, screens, locksets, handles, minimum SQM rules, dimension limits, etc.).",
		},
		{
			"fieldname": "otec_addons",
			"label": "Legacy Available Add-ons",
			"fieldtype": "Small Text",
			"insert_after": "otec_addon_notes",
			"hidden": 1,
			"read_only": 1,
			"description": "Legacy field retained for compatibility. Use OTEC Item Add-on Rules.",
		},
		{
			"fieldname": "otec_specification_options_section",
			"label": "OTEC Quotation Specification Options",
			"fieldtype": "Section Break",
			"insert_after": "otec_addons",
			"collapsible": 1,
		},
		{
			"fieldname": "otec_allowed_aluminum_thicknesses",
			"label": "Allowed Aluminum Thicknesses",
			"fieldtype": "Table MultiSelect",
			"options": "OTEC Item Aluminum Option",
			"insert_after": "otec_specification_options_section",
		},
		{
			"fieldname": "otec_allowed_glass_types",
			"label": "Allowed Glass Types",
			"fieldtype": "Table MultiSelect",
			"options": "OTEC Item Glass Type Option",
			"insert_after": "otec_allowed_aluminum_thicknesses",
		},
		{
			"fieldname": "otec_allowed_glass_colors",
			"label": "Allowed Glass Colors",
			"fieldtype": "Table MultiSelect",
			"options": "OTEC Item Glass Color Option",
			"insert_after": "otec_allowed_glass_types",
		},
	]
}


def setup_otec_quotation():
	# OTEC Quotation previously existed as an empty custom DocType fixture.
	# Reload the version-controlled standard schema after fixtures are imported.
	frappe.reload_doc("otec_selling", "doctype", "otec_add_on", force=True)
	frappe.reload_doc("otec_selling", "doctype", "otec_product_configuration", force=True)
	frappe.reload_doc("otec_selling", "doctype", "otec_item_add_on_rule", force=True)
	frappe.reload_doc("otec_selling", "doctype", "otec_aluminum_thickness", force=True)
	frappe.reload_doc("otec_selling", "doctype", "otec_glass_type", force=True)
	frappe.reload_doc("otec_selling", "doctype", "otec_glass_color", force=True)
	frappe.reload_doc("otec_selling", "doctype", "otec_item_aluminum_option", force=True)
	frappe.reload_doc("otec_selling", "doctype", "otec_item_glass_type_option", force=True)
	frappe.reload_doc("otec_selling", "doctype", "otec_item_glass_color_option", force=True)
	frappe.reload_doc("otec_selling", "doctype", "otec_quotation_item", force=True)
	frappe.reload_doc("otec_selling", "doctype", "otec_quotation_add_on", force=True)
	frappe.reload_doc("otec_selling", "doctype", "otec_quotation", force=True)
	create_custom_fields(ITEM_FIELDS, update=True)
	_seed_addons()
	setup_catalog()
	_install_print_format()


def _seed_addons():
	for addon in ADDONS:
		name = addon["addon_name"]
		if frappe.db.exists("OTEC Add-on", name):
			frappe.db.set_value("OTEC Add-on", name, "rate", addon["rate"])
		else:
			frappe.get_doc(
				{
					"doctype": "OTEC Add-on",
					"addon_name": name,
					"rate": addon["rate"],
					"description": addon.get("description"),
				}
			).insert(ignore_permissions=True)
	frappe.db.commit()


def _install_print_format():
	template_path = Path(
		frappe.get_app_path("otec_selling", "templates", "print_formats", "otec_initial_quotation.html")
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

	frappe.db.set_value("DocType", "OTEC Quotation", "default_print_format", name, update_modified=False)
