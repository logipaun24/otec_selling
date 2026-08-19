const OTEC_ITEM_FIELDS = [
	"item_name",
	"otec_main_product_category",
	"otec_secondary_product_category",
	"otec_series",
	"otec_minimum_sqm",
	"otec_sqm_rate",
	"otec_operable_available",
	"otec_operable_rate",
	"otec_glass_specification",
	"otec_frame_specification",
	"otec_color",
];

frappe.ui.form.on("OTEC Quotation", {
	refresh(frm) {
		frm.set_query("contact_person", () => ({
			query: "frappe.contacts.doctype.contact.contact.contact_query",
			filters: { link_doctype: "Customer", link_name: frm.doc.customer },
		}));
	},
	total_manual_markup: calculate_quotation,
	delivery_fee: calculate_quotation,
	installation_fee: calculate_quotation,
	apply_vat: calculate_quotation,
	vat_rate: calculate_quotation,
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
			glass_specification: item.otec_glass_specification,
			frame_specification: item.otec_frame_specification,
			color: item.otec_color,
		};
		if (!item.otec_operable_available) values.operable = 0;
		await frappe.model.set_value(cdt, cdn, values);
		calculate_quotation(frm);
	},
	width_m: calculate_quotation,
	height_m: calculate_quotation,
	sets: calculate_quotation,
	operable: calculate_quotation,
	items_remove: calculate_quotation,
});

function calculate_quotation(frm) {
	const rows = frm.doc.items || [];
	const shortfalls = {};
	const counts = {};

	for (const row of rows) {
		row.actual_sqm = flt(row.width_m) * flt(row.height_m);
		row.sqm_shortfall = Math.max(flt(row.minimum_sqm) - row.actual_sqm, 0);
		const category = row.main_product_category || "Uncategorized";
		shortfalls[category] = flt(shortfalls[category]) + row.sqm_shortfall;
		counts[category] = flt(counts[category]) + 1;
	}

	const markup_per_row = rows.length ? flt(frm.doc.total_manual_markup) / rows.length : 0;
	let items_subtotal = 0;
	let total_sets = 0;

	for (const row of rows) {
		const category = row.main_product_category || "Uncategorized";
		row.allocated_sqm = counts[category] ? shortfalls[category] / counts[category] : 0;
		row.allocated_sqm_amount = row.allocated_sqm * flt(row.sqm_rate);
		row.base_line_amount = row.actual_sqm * flt(row.sqm_rate) * flt(row.sets);
		row.operable_amount = row.operable && row.operable_available
			? flt(row.operable_rate) * flt(row.sets)
			: 0;
		row.allocated_markup = markup_per_row;
		row.amount = row.base_line_amount + row.allocated_sqm_amount
			+ row.operable_amount + row.allocated_markup;
		row.unit_rate = flt(row.sets) ? row.amount / flt(row.sets) : 0;
		items_subtotal += row.amount;
		total_sets += flt(row.sets);
	}

	const before_vat = items_subtotal + flt(frm.doc.delivery_fee) + flt(frm.doc.installation_fee);
	const vat_amount = frm.doc.apply_vat ? before_vat * flt(frm.doc.vat_rate) / 100 : 0;
	frm.doc.total_sets = total_sets;
	frm.doc.items_subtotal = items_subtotal;
	frm.doc.vat_amount = vat_amount;
	frm.doc.grand_total = before_vat + vat_amount;
	frm.refresh_fields();
}
