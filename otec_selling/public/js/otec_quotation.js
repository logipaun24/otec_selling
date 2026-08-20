const OTEC_ITEM_FIELDS = [
	"item_name",
	"otec_main_product_category",
	"otec_secondary_product_category",
	"otec_series",
	"otec_minimum_sqm",
	"otec_sqm_rate",
	"otec_operable_available",
	"otec_operable_rate",
	"otec_aluminum_thickness",
	"otec_glass_specification",
	"otec_frame_specification",
	"otec_color",
	"otec_addon_notes",
	"otec_addons",
];

frappe.ui.form.on("OTEC Quotation", {
	refresh(frm) {
		frm.set_query("contact_person", () => ({
			query: "frappe.contacts.doctype.contact.contact.contact_query",
			filters: { link_doctype: "Customer", link_name: frm.doc.customer },
		}));

		if (frm.doc.docstatus === 0) {
			frm.add_custom_btn(__("Calculate Totals"), () => calculate_totals(frm));
		}
	},
});

frappe.ui.form.on("OTEC Quotation Item", {
	async item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) return;

		const result = await frappe.db.get_value("Item", row.item_code, OTEC_ITEM_FIELDS);
		const item = result.message || {};
		const values = {
			item_name: item.item_name,
			main_product_category: item.otec_main_product_category,
			secondary_product_category: item.otec_secondary_product_category,
			series: item.otec_series,
			minimum_sqm: item.otec_minimum_sqm,
			sqm_rate: item.otec_sqm_rate,
			operable_available: item.otec_operable_available,
			operable_rate: item.otec_operable_rate,
			aluminum_thickness: item.otec_aluminum_thickness,
			glass_specification: item.otec_glass_specification,
			frame_specification: item.otec_frame_specification,
			color: item.otec_color,
			addon_notes: item.otec_addon_notes,
			addons: item.otec_addons || [],
		};
		if (!item.otec_operable_available) values.operable = 0;
		await frappe.model.set_value(cdt, cdn, values);
	},
});

async function calculate_totals(frm) {
	if (!frm.doc.items || !frm.doc.items.length) {
		frappe.msgprint(__("Add quotation items before calculating totals."));
		return;
	}

	frappe.dom.freeze(__("Calculating totals..."));
	try {
		const result = await frappe.call({
			method:
				"otec_selling.otec_selling.doctype.otec_quotation.otec_quotation.calculate_quotation",
			args: { doc: frm.doc },
		});
		const data = result.message;
		if (!data) return;

		const rows_by_name = {};
		for (const item of data.items || []) {
			rows_by_name[item.name] = item;
		}

		const fields_to_apply = [
			"item_name",
			"main_product_category",
			"secondary_product_category",
			"series",
			"aluminum_thickness",
			"glass_specification",
			"frame_specification",
			"color",
			"addons",
			"addon_notes",
			"addon_amount",
			"minimum_sqm",
			"sqm_rate",
			"operable_available",
			"operable_rate",
			"actual_sqm",
			"sqm_shortfall",
			"allocated_sqm",
			"allocated_sqm_amount",
			"base_line_amount",
			"operable_amount",
			"allocated_markup",
			"unit_rate",
			"amount",
		];

		for (const row of frm.doc.items || []) {
			const computed = rows_by_name[row.name];
			if (!computed) continue;
			for (const field of fields_to_apply) {
				if (field in computed) {
					row[field] = computed[field];
				}
			}
		}

		frm.set_value("total_sets", data.total_sets);
		frm.set_value("items_subtotal", data.items_subtotal);
		frm.set_value("vat_amount", data.vat_amount);
		frm.set_value("grand_total", data.grand_total);
		frm.refresh_fields();
	} catch (error) {
		console.error(error);
		frappe.msgprint(__("Failed to calculate totals. Please check the items and try again."));
	} finally {
		frappe.dom.unfreeze();
	}
}
