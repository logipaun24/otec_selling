frappe.ui.form.on("OTEC Quotation", {
	refresh(frm) {
		frm.set_query("contact_person", () => ({
			query: "frappe.contacts.doctype.contact.contact.contact_query",
			filters: { link_doctype: "Customer", link_name: frm.doc.customer },
		}));
		frm.set_query("item_code", "items", () => ({ filters: { item_group: "OTEC Products" } }));

		if (frm.doc.docstatus === 0) {
			frm.add_custom_btn(__("Configure Selected Item"), () => {
				const selected = frm.fields_dict.items.grid.get_selected_children();
				if (selected.length !== 1) {
					frappe.msgprint(__("Select exactly one quotation item row."));
					return;
				}
				open_product_configurator(frm, selected[0].doctype, selected[0].name);
			});
		}
		if (frm.__otec_computations_stale === undefined) {
			frm.__otec_computations_stale = frm.is_new();
		}
		render_computation_status(frm);
	},

	items_remove(frm, cdt, cdn) {
		remove_row_addons(frm, cdn);
		mark_computations_stale(frm);
	},

	refresh_computations(frm) {
		return calculate_totals(frm);
	},

	total_manual_markup: mark_computations_stale,
	delivery_fee: mark_computations_stale,
	installation_fee: mark_computations_stale,
	apply_vat: mark_computations_stale,
	vat_rate: mark_computations_stale,

	after_save(frm) {
		mark_computations_current(frm, __("Saved with current computations"));
	},
});

frappe.ui.form.on("OTEC Quotation Item", {
	async item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		remove_row_addons(frm, row.name);
		mark_computations_stale(frm);
		if (!row.item_code) return;
		await open_product_configurator(frm, cdt, cdn);
	},

	configure_product(frm, cdt, cdn) {
		open_product_configurator(frm, cdt, cdn);
	},

	width_m: mark_computations_stale,
	height_m: mark_computations_stale,
	panels: mark_computations_stale,
	sets: mark_computations_stale,
	operable: mark_computations_stale,
});

async function open_product_configurator(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row?.item_code) {
		frappe.msgprint(__("Select an OTEC item first."));
		return;
	}
	const quotation_row_key = ensure_row_key(row);

	const response = await frappe.call({
		method: "otec_selling.otec_selling.doctype.otec_quotation.otec_quotation.get_product_configurator",
		args: { item_code: row.item_code },
		freeze: true,
		freeze_message: __("Loading product options..."),
	});
	const data = response.message || {};
	const configurations = data.configurations || [];
	const aluminum_options = data.aluminum_options || [];
	const glass_type_options = data.glass_type_options || [];
	const glass_color_options = data.glass_color_options || [];
	const rules = data.add_on_rules || [];
	if (!configurations.length) {
		frappe.msgprint(__("No active product configuration exists for {0}.", [row.item_code]));
		return;
	}

	const current_addons = {};
	for (const addon of frm.doc.quotation_addons || []) {
		if (addon.quotation_item_row_id === row.name) current_addons[addon.add_on] = addon;
	}
	const manual_rules = rules.filter((rule) =>
		["Per Piece", "Per Pair", "Manual Quantity"].includes(rule.pricing_basis)
	);
	const fields = [
		{
			fieldname: "configuration",
			fieldtype: "Select",
			label: __("Product Configuration"),
			options: configurations.map((config) => config.name),
			default:
				row.configuration ||
				configurations.find((config) => config.is_default)?.name ||
				configurations[0].name,
			reqd: 1,
		},
		{
			fieldname: "aluminum_thickness",
			fieldtype: "Select",
			label: __("Aluminum Thickness"),
			options: ["", ...aluminum_options.map((option) => option.name)],
			default: row.aluminum_thickness || "",
			reqd: 1,
		},
		{
			fieldname: "glass_type",
			fieldtype: "Select",
			label: __("Glass Type"),
			options: ["", ...glass_type_options.map((option) => option.name)],
			default: row.glass_type || "",
			reqd: 1,
		},
		{
			fieldname: "glass_color",
			fieldtype: "Select",
			label: __("Glass Color"),
			options: ["", ...glass_color_options.map((option) => option.name)],
			default: row.glass_color || "",
			reqd: 1,
		},
		{
			fieldname: "panels",
			fieldtype: "Int",
			label: __("Panels per Set"),
			default: row.panels || 1,
			reqd: 1,
		},
		{
			fieldname: "add_ons",
			fieldtype: "MultiCheck",
			label: __("Available Add-ons"),
			options: rules.map((rule) => ({
				label: `${rule.add_on} — ${format_currency(rule.rate)} ${rule.pricing_basis}${
					rule.requires_approval ? " • Approval required" : ""
				}`,
				value: rule.add_on,
				checked: Boolean(
					current_addons[rule.add_on] || rule.required || rule.default_selected
				),
			})),
		},
	];
	for (const [index, rule] of manual_rules.entries()) {
		fields.push({
			fieldname: `quantity_${index}`,
			fieldtype: "Float",
			label: __(`Quantity: ${rule.add_on}`),
			default: current_addons[rule.add_on]?.quantity || rule.default_quantity || 1,
			non_negative: 1,
		});
	}
	fields.push({ fieldname: "pricing_preview", fieldtype: "HTML" });

	const dialog = new frappe.ui.Dialog({
		title: __("Configure {0}", [row.item_name || row.item_code]),
		fields,
		primary_action_label: __("Apply Configuration"),
		async primary_action(values) {
			const configuration = configurations.find(
				(config) => config.name === values.configuration
			);
			const aluminum = aluminum_options.find(
				(option) => option.name === values.aluminum_thickness
			);
			const glass_type = glass_type_options.find(
				(option) => option.name === values.glass_type
			);
			const glass_color = glass_color_options.find(
				(option) => option.name === values.glass_color
			);
			const effective_rate =
				Number(configuration.sqm_rate || 0) +
				Number(aluminum.rate_per_sqm || 0) +
				Number(glass_type.rate_per_sqm || 0) +
				Number(glass_color.rate_per_sqm || 0);
			const approvals = [configuration, aluminum, glass_type, glass_color].filter(
				(entry) => entry.requires_approval
			);
			const selected = new Set(values.add_ons || []);
			for (const rule of rules.filter((entry) => entry.required)) selected.add(rule.add_on);

			await frappe.model.set_value(cdt, cdn, {
				configuration: configuration.name,
				aluminum_thickness: aluminum.name,
				glass_type: glass_type.name,
				glass_color: glass_color.name,
				base_product_sqm_rate: configuration.sqm_rate,
				aluminum_price_per_sqm: aluminum.rate_per_sqm,
				glass_type_price_per_sqm: glass_type.rate_per_sqm,
				glass_color_price_per_sqm: glass_color.rate_per_sqm,
				sqm_rate: effective_rate,
				operable_available: configuration.operable_available,
				operable_rate: configuration.operable_rate,
				pricing_approval_required: approvals.length > 0,
				pricing_approval_reason: approvals
					.map((entry) => entry.approval_reason)
					.filter(Boolean)
					.join("\n"),
				panels: values.panels || 1,
			});

			remove_row_addons(frm, row.name);
			for (const rule of rules.filter((entry) => selected.has(entry.add_on))) {
				const manual_index = manual_rules.findIndex(
					(entry) => entry.add_on === rule.add_on
				);
				const quantity = manual_index >= 0 ? values[`quantity_${manual_index}`] : 0;
				const child = frappe.model.add_child(
					frm.doc,
					"OTEC Quotation Add-on",
					"quotation_addons"
				);
				Object.assign(child, {
					quotation_item_row_id: row.name,
					quotation_item_row_key: quotation_row_key,
					item_code: row.item_code,
					add_on: rule.add_on,
					pricing_basis: rule.pricing_basis,
					quantity: quantity || rule.default_quantity || 1,
					rate: rule.rate,
					requires_approval: rule.requires_approval,
					notes: rule.notes,
				});
			}
			frm.refresh_field("quotation_addons");
			dialog.hide();
			mark_computations_stale(frm);
		},
	});

	const update_preview = () => {
		const config = configurations.find(
			(entry) => entry.name === dialog.get_value("configuration")
		);
		const aluminum = aluminum_options.find(
			(entry) => entry.name === dialog.get_value("aluminum_thickness")
		);
		const glass_type = glass_type_options.find(
			(entry) => entry.name === dialog.get_value("glass_type")
		);
		const glass_color = glass_color_options.find(
			(entry) => entry.name === dialog.get_value("glass_color")
		);
		if (!config || !aluminum || !glass_type || !glass_color) {
			dialog.fields_dict.pricing_preview.$wrapper.html(
				`<div class="text-muted mt-3">${__(
					"Select all specifications to preview the price."
				)}</div>`
			);
			return;
		}
		const approvals = [config, aluminum, glass_type, glass_color].filter(
			(entry) => entry.requires_approval
		);
		const approval = approvals.length
			? `<div class="alert alert-warning">${frappe.utils.escape_html(
					approvals
						.map((entry) => entry.approval_reason || __("Pricing approval required"))
						.join("; ")
			  )}</div>`
			: "";
		const effective_rate =
			Number(config.sqm_rate || 0) +
			Number(aluminum.rate_per_sqm || 0) +
			Number(glass_type.rate_per_sqm || 0) +
			Number(glass_color.rate_per_sqm || 0);
		dialog.fields_dict.pricing_preview.$wrapper.html(`
			<div class="mt-3 border rounded p-3">
				<strong>${frappe.utils.escape_html(config.configuration_label)}</strong><br>
				${__("Base product/system")}: ${format_currency(config.sqm_rate)}<br>
				${__("Aluminum {0} mm", [aluminum.name])}: +${format_currency(aluminum.rate_per_sqm)}<br>
				${__("Glass type — {0}", [glass_type.name])}: +${format_currency(glass_type.rate_per_sqm)}<br>
				${__("Glass color — {0}", [glass_color.name])}: +${format_currency(glass_color.rate_per_sqm)}<br>
				<strong>${__("Effective rate")}: ${format_currency(effective_rate)} / SQM</strong>
				${approval}
			</div>`);
	};
	dialog.fields_dict.configuration.df.onchange = update_preview;
	dialog.fields_dict.aluminum_thickness.df.onchange = update_preview;
	dialog.fields_dict.glass_type.df.onchange = update_preview;
	dialog.fields_dict.glass_color.df.onchange = update_preview;
	dialog.show();
	update_preview();
}

function remove_row_addons(frm, row_name) {
	frm.doc.quotation_addons = (frm.doc.quotation_addons || []).filter(
		(addon) => addon.quotation_item_row_id !== row_name
	);
	frm.refresh_field("quotation_addons");
}

function ensure_row_key(row) {
	if (!row.quotation_row_key) row.quotation_row_key = frappe.utils.get_random(16);
	return row.quotation_row_key;
}

function mark_computations_stale(frm) {
	if (!frm || frm.doc.docstatus !== 0) return;
	frm.__otec_computations_stale = true;
	frm.__otec_last_computed_label = null;
	render_computation_status(frm);
}

function mark_computations_current(frm, label) {
	frm.__otec_computations_stale = false;
	frm.__otec_last_computed_label = label || __("Refreshed {0}", [frappe.datetime.now_time()]);
	render_computation_status(frm);
}

function render_computation_status(frm) {
	const field = frm.fields_dict.computation_status;
	if (!field?.$wrapper) return;
	const stale = frm.__otec_computations_stale;
	const color = stale ? "orange" : "green";
	const message = stale
		? __("Computations need refresh. Click Refresh Computations before reviewing totals.")
		: frm.__otec_last_computed_label || __("Computations are current.");
	field.$wrapper.html(`
		<div class="indicator ${color}" style="margin-top: 8px;">
			${frappe.utils.escape_html(message)}
		</div>`);
}

async function calculate_totals(frm) {
	if (!frm.doc.items || !frm.doc.items.length) {
		frappe.msgprint(__("Add quotation items before calculating totals."));
		return;
	}
	frappe.dom.freeze(__("Calculating totals..."));
	try {
		const result = await frappe.call({
			method: "otec_selling.otec_selling.doctype.otec_quotation.otec_quotation.calculate_quotation",
			args: { doc: frm.doc },
		});
		const data = result.message;
		if (!data) return;
		const rows_by_name = Object.fromEntries(
			(data.items || []).map((item) => [item.name, item])
		);
		const fields_to_apply = [
			"quotation_row_key",
			"item_name",
			"main_product_category",
			"secondary_product_category",
			"series",
			"configuration",
			"aluminum_thickness",
			"glass_type",
			"glass_color",
			"glass_specification",
			"frame_specification",
			"color",
			"base_product_sqm_rate",
			"aluminum_price_per_sqm",
			"glass_type_price_per_sqm",
			"glass_color_price_per_sqm",
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
			"pricing_approval_required",
			"pricing_approval_reason",
			"unit_rate",
			"amount",
		];
		for (const row of frm.doc.items || []) {
			const computed = rows_by_name[row.name];
			if (!computed) continue;
			for (const field of fields_to_apply)
				if (field in computed) row[field] = computed[field];
		}
		frm.clear_table("quotation_addons");
		for (const values of data.quotation_addons || []) {
			const child = frappe.model.add_child(
				frm.doc,
				"OTEC Quotation Add-on",
				"quotation_addons"
			);
			for (const field of [
				"quotation_item_row_id",
				"quotation_item_row_key",
				"item_code",
				"add_on",
				"pricing_basis",
				"quantity",
				"rate",
				"amount",
				"requires_approval",
				"notes",
			]) {
				child[field] = values[field];
			}
		}
		await frm.set_value("total_sets", data.total_sets);
		await frm.set_value("items_subtotal", data.items_subtotal);
		await frm.set_value("vat_amount", data.vat_amount);
		await frm.set_value("grand_total", data.grand_total);
		frm.refresh_fields();
		mark_computations_current(frm);
	} catch (error) {
		mark_computations_stale(frm);
		console.error(error);
	} finally {
		frappe.dom.unfreeze();
	}
}
