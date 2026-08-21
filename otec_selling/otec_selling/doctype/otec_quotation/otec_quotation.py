from collections import defaultdict
import json
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate


PRICING_APPROVER_ROLES = {"System Manager", "Business Owner", "Sales Master Manager"}


class OTECQuotation(Document):
    def validate(self):
        self.set_item_master_values()
        self.calculate_totals()
        if self.docstatus == 0 and self.status not in ("Draft", "For Approval"):
            self.status = "Draft"

    def before_submit(self):
        if not self.approved_shop_drawing:
            frappe.throw(_("Attach the approved shop drawing before approving this quotation."))
        approval_rows = [row.idx for row in self.items if row.pricing_approval_required]
        if approval_rows and not PRICING_APPROVER_ROLES.intersection(frappe.get_roles()):
            frappe.throw(
                _("Pricing approval is required for quotation row(s): {0}.").format(
                    ", ".join(str(idx) for idx in approval_rows)
                )
            )
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
        for row in self.items:
            if not row.item_code:
                continue
            values = frappe.db.get_value("Item", row.item_code, fields, as_dict=True) or {}
            row.item_name = values.get("item_name") or row.item_code
            row.main_product_category = values.get("otec_main_product_category")
            row.secondary_product_category = values.get("otec_secondary_product_category")
            row.series = values.get("otec_series")
            row.minimum_sqm = flt(values.get("otec_minimum_sqm"))
            row.frame_specification = values.get("otec_frame_specification")
            row.addon_notes = values.get("otec_addon_notes")
            if not row.color:
                row.color = values.get("otec_color")

            configuration = _get_configuration(row.item_code, row.configuration)
            if configuration:
                row.configuration = configuration.name
                row.aluminum_thickness = configuration.aluminum_thickness
                row.glass_specification = configuration.glass_specification
                row.sqm_rate = flt(configuration.sqm_rate)
                row.operable_available = configuration.operable_available
                row.operable_rate = flt(configuration.operable_rate)
                row.pricing_approval_required = configuration.requires_approval
                row.pricing_approval_reason = configuration.approval_reason
            else:
                row.aluminum_thickness = values.get("otec_aluminum_thickness")
                row.glass_specification = values.get("otec_glass_specification")
                row.sqm_rate = flt(values.get("otec_sqm_rate"))
                row.operable_available = values.get("otec_operable_available")
                row.operable_rate = flt(values.get("otec_operable_rate"))
                row.pricing_approval_required = 1
                row.pricing_approval_reason = _("No active product configuration is available.")
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

        addon_amounts = self._validate_and_price_addons()
        row_count = len(self.items)
        markup_per_row = flt(self.total_manual_markup) / row_count if row_count else 0
        items_subtotal = 0
        total_sets = 0

        for category, rows in category_rows.items():
            max_shortfall = max((row.sqm_shortfall for row in rows), default=0)
            eligible = [row for row in rows if row.sqm_shortfall < max_shortfall]
            eligible_actual_sqm = sum(row.actual_sqm for row in eligible)
            for row in rows:
                if not eligible:
                    # A single row (or rows tied at the same shortfall) has no
                    # other category row to receive the minimum-SQM difference.
                    row.allocated_sqm = row.sqm_shortfall
                elif row.sqm_shortfall >= max_shortfall:
                    row.allocated_sqm = 0
                else:
                    row.allocated_sqm = (
                        category_shortfall[category] * row.actual_sqm / eligible_actual_sqm
                        if eligible_actual_sqm else 0
                    )
                row.allocated_sqm_amount = row.allocated_sqm * flt(row.sqm_rate)
                row.base_line_amount = row.actual_sqm * flt(row.sqm_rate) * flt(row.sets)
                row.operable_amount = (
                    flt(row.operable_rate) * flt(row.sets)
                    if row.operable and row.operable_available else 0
                )
                row.allocated_markup = markup_per_row
                row.addon_amount = addon_amounts.get(row.name, 0)
                row.amount = (
                    row.base_line_amount + row.allocated_sqm_amount + row.operable_amount
                    + row.allocated_markup + row.addon_amount
                )
                row.unit_rate = row.amount / flt(row.sets) if flt(row.sets) else 0
                items_subtotal += row.amount
                total_sets += flt(row.sets)

        self.total_sets = total_sets
        self.items_subtotal = items_subtotal
        before_vat = items_subtotal + flt(self.delivery_fee) + flt(self.installation_fee)
        self.vat_amount = before_vat * flt(self.vat_rate) / 100 if self.apply_vat else 0
        self.grand_total = before_vat + self.vat_amount

    def _validate_and_price_addons(self):
        item_rows = self._reconcile_addon_item_links()
        amounts = defaultdict(float)
        summaries = defaultdict(list)
        selected_by_row = defaultdict(set)

        for addon_row in self.quotation_addons:
            item_row = item_rows.get(addon_row.quotation_item_row_id)
            if not item_row:
                frappe.throw(_("Add-on {0} is not linked to a valid quotation item row.").format(addon_row.add_on))
            if addon_row.add_on in selected_by_row[item_row.name]:
                frappe.throw(_("Add-on {0} is selected more than once for row {1}.").format(addon_row.add_on, item_row.idx))
            selected_by_row[item_row.name].add(addon_row.add_on)

            rule = frappe.db.get_value(
                "OTEC Item Add-on Rule",
                {"item_code": item_row.item_code, "add_on": addon_row.add_on, "active": 1},
                ["pricing_basis", "rate_override", "default_quantity", "requires_approval", "notes", "incompatible_add_ons"],
                as_dict=True,
            )
            if not rule:
                frappe.throw(_("Add-on {0} is not allowed for item {1}.").format(addon_row.add_on, item_row.item_code))
            master = frappe.db.get_value("OTEC Add-on", addon_row.add_on, ["rate", "active"], as_dict=True)
            if not master or not master.active:
                frappe.throw(_("Add-on {0} is inactive.").format(addon_row.add_on))

            addon_row.item_code = item_row.item_code
            addon_row.pricing_basis = rule.pricing_basis
            addon_row.rate = flt(rule.rate_override) or flt(master.rate)
            addon_row.quantity = _addon_quantity(addon_row, item_row, rule)
            addon_row.amount = addon_row.quantity * addon_row.rate
            addon_row.requires_approval = rule.requires_approval
            addon_row.notes = rule.notes
            amounts[item_row.name] += addon_row.amount
            summaries[item_row.name].append(f"{addon_row.add_on} × {addon_row.quantity:g}")
            if rule.requires_approval:
                item_row.pricing_approval_required = 1
                item_row.pricing_approval_reason = _append_reason(item_row.pricing_approval_reason, rule.notes or _("Add-on pricing requires approval."))

        for item_row in self.items:
            required = frappe.get_all(
                "OTEC Item Add-on Rule",
                filters={"item_code": item_row.item_code, "active": 1, "required": 1},
                pluck="add_on",
            )
            missing = sorted(set(required) - selected_by_row[item_row.name])
            if missing:
                frappe.throw(_("Row {0} requires add-on(s): {1}.").format(item_row.idx, ", ".join(missing)))
            for addon_row in [a for a in self.quotation_addons if a.quotation_item_row_id == item_row.name]:
                incompatible_text = frappe.db.get_value(
                    "OTEC Item Add-on Rule",
                    {"item_code": item_row.item_code, "add_on": addon_row.add_on, "active": 1},
                    "incompatible_add_ons",
                )
                conflicts = set(_addon_names(incompatible_text)).intersection(selected_by_row[item_row.name])
                if conflicts:
                    frappe.throw(_("Add-on {0} conflicts with {1} on row {2}.").format(addon_row.add_on, ", ".join(sorted(conflicts)), item_row.idx))
            item_row.addons = ", ".join(summaries[item_row.name])
        return amounts

    def _reconcile_addon_item_links(self):
        """Keep add-ons attached when Frappe renames new child rows on save."""
        for item_row in self.items:
            if not item_row.quotation_row_key:
                item_row.quotation_row_key = frappe.generate_hash(length=16)

        rows_by_name = {row.name: row for row in self.items}
        rows_by_key = {row.quotation_row_key: row for row in self.items}
        rows_by_item = defaultdict(list)
        for item_row in self.items:
            rows_by_item[item_row.item_code].append(item_row)

        for addon_row in self.quotation_addons:
            item_row = rows_by_key.get(addon_row.quotation_item_row_key)
            if not item_row:
                item_row = rows_by_name.get(addon_row.quotation_item_row_id)
            if not item_row:
                # Backward compatibility for add-ons created before stable row
                # keys existed. Only repair an unambiguous item match.
                candidates = rows_by_item.get(addon_row.item_code, [])
                if len(candidates) == 1:
                    item_row = candidates[0]
            if item_row:
                addon_row.quotation_item_row_id = item_row.name
                addon_row.quotation_item_row_key = item_row.quotation_row_key

        return rows_by_name


def _get_configuration(item_code, configuration_name=None):
    if configuration_name:
        configuration = frappe.db.get_value(
            "OTEC Product Configuration", configuration_name,
            ["name", "item_code", "aluminum_thickness", "glass_specification", "sqm_rate",
             "operable_available", "operable_rate", "requires_approval", "approval_reason", "active"],
            as_dict=True,
        )
        if not configuration or not configuration.active or configuration.item_code != item_code:
            frappe.throw(_("The selected product configuration is not valid for item {0}.").format(item_code))
        return configuration
    configurations = _active_configurations(item_code)
    default = next((row for row in configurations if row.is_default), None)
    return default or (configurations[0] if configurations else None)


def _active_configurations(item_code):
    rows = frappe.get_all(
        "OTEC Product Configuration",
        filters={"item_code": item_code, "active": 1},
        fields=["name", "configuration_label", "item_code", "aluminum_thickness", "glass_specification",
                "sqm_rate", "operable_available", "operable_rate", "requires_approval", "approval_reason",
                "is_default", "effective_from", "effective_to"],
        order_by="is_default desc, configuration_label asc",
    )
    today = getdate(nowdate())
    return [row for row in rows if (not row.effective_from or getdate(row.effective_from) <= today)
            and (not row.effective_to or getdate(row.effective_to) >= today)]


def _addon_quantity(addon_row, item_row, rule):
    basis = rule.pricing_basis
    if basis == "Per SQM":
        return flt(item_row.actual_sqm) * flt(item_row.sets)
    if basis == "Per Panel":
        return flt(item_row.panels) * flt(item_row.sets)
    if basis == "Per Set":
        return flt(item_row.sets)
    if basis == "Flat":
        return 1
    return flt(addon_row.quantity) or flt(rule.default_quantity) or 1


def _append_reason(current, reason):
    return f"{current}\n{reason}" if current and reason and reason not in current else (current or reason)


def _addon_amount(addons) -> float:
    """Compatibility helper for legacy tests and previously stored selections."""
    names = _addon_names(addons)
    if not names:
        return 0
    rates = frappe.db.get_values("OTEC Add-on", {"name": ["in", names]}, ["name", "rate"], as_dict=True)
    rate_map = {row["name"]: flt(row["rate"]) for row in rates}
    return sum(rate_map.get(name, 0) for name in names)


def _addon_names(addons) -> list[str]:
    if not addons:
        return []
    if isinstance(addons, (list, tuple, set)):
        return [str(name).strip() for name in addons if str(name).strip()]
    if isinstance(addons, str):
        value = addons.strip()
        if value.startswith("["):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(name).strip() for name in parsed if str(name).strip()]
            except (TypeError, ValueError):
                pass
        return [name.strip() for name in re.split(r"[,\n]+", value) if name.strip()]
    return []


@frappe.whitelist()
def get_product_configurator(item_code):
    configurations = _active_configurations(item_code)
    rules = frappe.get_all(
        "OTEC Item Add-on Rule",
        filters={"item_code": item_code, "active": 1},
        fields=["name", "add_on", "pricing_basis", "rate_override", "default_quantity", "required",
                "default_selected", "requires_approval", "notes"],
        order_by="add_on asc",
    )
    for rule in rules:
        master = frappe.db.get_value("OTEC Add-on", rule.add_on, ["rate", "description"], as_dict=True) or {}
        rule.rate = flt(rule.rate_override) or flt(master.get("rate"))
        rule.description = master.get("description")
    return {"configurations": configurations, "add_on_rules": rules}


@frappe.whitelist()
def calculate_quotation(doc):
    # Desk serializes frm.doc when it is sent through frappe.call. Accept that
    # JSON string as well as a mapping so the method also remains usable from
    # server-side callers.
    data = frappe._dict(frappe.parse_json(doc))
    data["name"] = None
    quotation = frappe.get_doc(data)
    quotation.set_item_master_values()
    quotation.calculate_totals()
    return {
        "items": [row.as_dict() for row in quotation.items],
        "quotation_addons": [row.as_dict() for row in quotation.quotation_addons],
        "total_sets": quotation.total_sets,
        "items_subtotal": quotation.items_subtotal,
        "vat_amount": quotation.vat_amount,
        "grand_total": quotation.grand_total,
    }
