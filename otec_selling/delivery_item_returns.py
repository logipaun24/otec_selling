"""Physical returns per original DN row, expressed in that row's sales UOM."""

import frappe
from frappe.utils import flt


def quantities(qty, conversion_factor, returned_stock_qty):
	factor = flt(conversion_factor) or 1
	returned = max(flt(returned_stock_qty), 0) / factor
	return returned, flt(qty) - returned


def apply_balances(doc, method=None):
	returned = {}
	if not doc.is_new() and not doc.get("is_return"):
		returned = dict(
			frappe.db.sql(
				"""
			SELECT item.dn_detail, SUM(-item.stock_qty)
			FROM `tabDelivery Note Item` item
			JOIN `tabDelivery Note` receipt ON receipt.name = item.parent
			WHERE receipt.docstatus = 1 AND receipt.is_return = 1
			AND receipt.return_against = %s AND item.stock_qty < 0
			GROUP BY item.dn_detail
		""",
				doc.name,
			)
		)
	for row in doc.items:
		if doc.get("is_return") or doc.docstatus == 2:
			row.custom_returned_qty = row.custom_client_retained_qty = 0
		else:
			row.custom_returned_qty, row.custom_client_retained_qty = quantities(
				row.qty, row.conversion_factor, returned.get(row.name, 0)
			)


def sync_original(doc, method=None):
	name = doc.return_against if doc.get("is_return") else doc.name
	if not name:
		return
	# Serialize concurrent return/cancellation refreshes on the same original DN.
	frappe.db.sql("SELECT name FROM `tabDelivery Note` WHERE name=%s FOR UPDATE", name)
	original = frappe.get_doc("Delivery Note", name)
	apply_balances(original)
	for row in original.items:
		frappe.db.set_value(
			"Delivery Note Item",
			row.name,
			{
				"custom_returned_qty": row.custom_returned_qty,
				"custom_client_retained_qty": row.custom_client_retained_qty,
			},
			update_modified=False,
		)
	frappe.clear_document_cache("Delivery Note", name)


PRINT_MARKER = "<!-- OTEC ITEM RETURN BALANCE V1 -->"

# Site-local lifecycle scripts allow a targeted rollout without changing code
# for other sites sharing this bench. Reinstalled after fixtures on migration.
RETURN_QUERY = """
SELECT item.dn_detail, SUM(-item.stock_qty)
FROM `tabDelivery Note Item` item
JOIN `tabDelivery Note` receipt ON receipt.name = item.parent
WHERE receipt.docstatus = 1 AND receipt.is_return = 1
AND receipt.return_against = %s AND item.stock_qty < 0
GROUP BY item.dn_detail
"""
VALIDATE_SCRIPT = """
returned_by_row = dict(frappe.db.sql(RETURN_QUERY, doc.name)) if doc.name and not doc.is_return else {}
for row in doc.items:
    if doc.is_return or doc.docstatus == 2:
        row.custom_returned_qty = 0
        row.custom_client_retained_qty = 0
    else:
        factor = frappe.utils.flt(row.conversion_factor) or 1
        row.custom_returned_qty = max(frappe.utils.flt(returned_by_row.get(row.name, 0)), 0) / factor
        row.custom_client_retained_qty = frappe.utils.flt(row.qty) - row.custom_returned_qty
"""
SYNC_SCRIPT = """
original_name = doc.return_against if doc.is_return else doc.name
if original_name:
    frappe.db.sql("SELECT name FROM `tabDelivery Note` WHERE name=%s FOR UPDATE", original_name)
    original = frappe.get_doc("Delivery Note", original_name)
    returned_by_row = dict(frappe.db.sql(RETURN_QUERY, original_name))
    for row in original.items:
        factor = frappe.utils.flt(row.conversion_factor) or 1
        returned_qty = max(frappe.utils.flt(returned_by_row.get(row.name, 0)), 0) / factor
        retained_qty = frappe.utils.flt(row.qty) - returned_qty
        if original.docstatus == 2:
            returned_qty = 0
            retained_qty = 0
        frappe.db.set_value("Delivery Note Item", row.name, {
            "custom_returned_qty": returned_qty,
            "custom_client_retained_qty": retained_qty
        }, update_modified=False)
"""


def event_script(body):
	return "RETURN_QUERY = " + repr(RETURN_QUERY) + "\n" + body


PRINT_DETAIL = """
<!-- OTEC ITEM RETURN BALANCE V1 -->
{% if not doc.is_return and doc.docstatus == 1 %}
<div style="font-size:9px;line-height:1.3;white-space:normal;">
Returned: {{ item.get_formatted("custom_returned_qty", doc) }} {{ item.uom or "" }}<br>
Retained by client: {{ item.get_formatted("custom_client_retained_qty", doc) }} {{ item.uom or "" }}
</div>
{% endif %}
"""


def enhance_print(html):
	if PRINT_MARKER in html:
		return html
	anchor = '{{ item.get_formatted("qty", 0) }}'
	if anchor not in html:
		frappe.throw(
			"Delivery print layout changed: quantity anchor not found. Review the layout before updating."
		)
	# Keep the existing cell widths, amount columns and print authorization intact.
	# Include the original UOM before the detail, when it shares the quantity line.
	if anchor + " {{ item.uom }}" in html:
		anchor += " {{ item.uom }}"
	return html.replace(anchor, anchor + PRINT_DETAIL)


def setup_delivery_item_returns():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Delivery Note Item": [
				{
					"fieldname": "custom_returned_qty",
					"label": "Returned Qty",
					"fieldtype": "Float",
					"insert_after": "qty",
					"read_only": 1,
					"no_copy": 1,
					"allow_on_submit": 1,
					"in_list_view": 1,
					"columns": 1,
					"description": "Submitted physical returns, in this row's UOM.",
				},
				{
					"fieldname": "custom_client_retained_qty",
					"label": "Qty Retained by Client",
					"fieldtype": "Float",
					"insert_after": "custom_returned_qty",
					"read_only": 1,
					"no_copy": 1,
					"allow_on_submit": 1,
					"in_list_view": 1,
					"columns": 2,
					"description": "Original delivered quantity minus submitted physical returns. Not proof of delivery acceptance.",
				},
			]
		},
		update=True,
	)
	for label, event, body in (
		("Validate", "Before Validate", VALIDATE_SCRIPT),
		("Submit", "After Submit", SYNC_SCRIPT),
		("Cancel", "After Cancel", SYNC_SCRIPT),
	):
		name = "DN Item Return Balances - " + label
		script = (
			frappe.get_doc("Server Script", name)
			if frappe.db.exists("Server Script", name)
			else frappe.new_doc("Server Script")
		)
		script.update(
			{
				"name": name,
				"script_type": "DocType Event",
				"reference_doctype": "Delivery Note",
				"doctype_event": event,
				"disabled": 0,
				"script": event_script(body),
			}
		)
		script.save(ignore_permissions=True)
	for name in ("Delivery Note Standard", "Delivery Note with Item Image", "DR 2026"):
		if frappe.db.exists("Print Format", name):
			html = frappe.db.get_value("Print Format", name, "html") or ""
			updated = enhance_print(html)
			if updated != html:
				frappe.db.set_value("Print Format", name, "html", updated)
				frappe.clear_document_cache("Print Format", name)
	for name in frappe.get_all("Delivery Note", filters={"is_return": 0, "docstatus": 1}, pluck="name"):
		sync_original(frappe.get_doc("Delivery Note", name))
	frappe.clear_cache(doctype="Delivery Note")
	frappe.clear_cache(doctype="Delivery Note Item")
