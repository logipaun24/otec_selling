from __future__ import annotations

import json
from datetime import date

import frappe
from frappe.utils.file_manager import save_file


BATCH_ID = "OTEC-SALES-TEST-20260818-A"
COMPANY = "Comfort Hotel Supplies"
CUSTOMER_GROUP = "TEST Customers - CHS"
TERRITORY = "TEST Philippines - CHS"
PAYMENT_TERM = "TEST Net 30 - CHS"
PAYMENT_TEMPLATE = "TEST 30 Days - CHS"
CASH_TEMPLATE = "TEST Cash - CHS"
PRICE_LIST = "Standard Selling"
STOCK_WAREHOUSE = "R2L1S2 - CHS"
MANIFEST_FILE = f"{BATCH_ID}-manifest.json"


CUSTOMERS = (
    {
        "customer_name": "TEST Alpha Hotel Angeles",
        "customer_type": "Company",
        "city": "Angeles City",
        "branch": "COMFORT Angeles",
        "email": "alpha.hotel@example.invalid",
        "credit_limit": 100_000,
    },
    {
        "customer_name": "TEST Baguio Mountain Inn",
        "customer_type": "Company",
        "city": "Baguio City",
        "branch": "COMFORT Baguio",
        "email": "baguio.inn@example.invalid",
        "credit_limit": 75_000,
    },
    {
        "customer_name": "TEST Cagayan Business Hotel",
        "customer_type": "Company",
        "city": "Cagayan de Oro",
        "branch": "COMFORT Cagayan",
        "email": "cagayan.hotel@example.invalid",
        "credit_limit": 150_000,
    },
    {
        "customer_name": "TEST Friendship Suites",
        "customer_type": "Company",
        "city": "Angeles City",
        "branch": "COMFORT Friendship",
        "email": "friendship.suites@example.invalid",
        "credit_limit": 50_000,
    },
    {
        "customer_name": "TEST Manila Corporate Hotel",
        "customer_type": "Company",
        "city": "Marikina City",
        "branch": "COMFORT Marikina",
        "email": "manila.hotel@example.invalid",
        "credit_limit": 250_000,
    },
    {
        "customer_name": "TEST Subic Bay Resort",
        "customer_type": "Company",
        "city": "Subic",
        "branch": "COMFORT Subic",
        "email": "subic.resort@example.invalid",
        "credit_limit": 125_000,
    },
    {
        "customer_name": "TEST Tagaytay View Lodge",
        "customer_type": "Company",
        "city": "Tagaytay City",
        "branch": "COMFORT Tagaytay",
        "email": "tagaytay.lodge@example.invalid",
        "credit_limit": 80_000,
    },
    {
        "customer_name": "TEST Walk-in Cash Customer",
        "customer_type": "Individual",
        "city": "Porac",
        "branch": "Warehouse Porac",
        "email": "walkin.cash@example.invalid",
        "credit_limit": 5_000,
        "payment_template": CASH_TEMPLATE,
    },
)


ITEMS = (
    "CAAPGAK001",
    "CAPEBLKGLD001",
    "SKU008770",
    "SKU008830",
    "SKU000850",
    "CABSSQ25G001",
    "CABSBP12G001",
    "CABSOCP20G002",
    "CAG5LBLGRNTEA004",
    "CABLSC30ML002",
    "CAG5LBWGRNTEA004",
    "CABWSC30ML002",
)


def _ensure_customer_group() -> str:
    if not frappe.db.exists("Customer Group", CUSTOMER_GROUP):
        frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": CUSTOMER_GROUP,
                "parent_customer_group": "All Customer Groups",
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)
    return CUSTOMER_GROUP


def _ensure_territory() -> str:
    if not frappe.db.exists("Territory", TERRITORY):
        frappe.get_doc(
            {
                "doctype": "Territory",
                "territory_name": TERRITORY,
                "parent_territory": "All Territories",
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)
    return TERRITORY


def _ensure_payment_terms() -> str:
    if not frappe.db.exists("Payment Term", PAYMENT_TERM):
        frappe.get_doc(
            {
                "doctype": "Payment Term",
                "payment_term_name": PAYMENT_TERM,
                "invoice_portion": 100,
                "due_date_based_on": "Day(s) after invoice date",
                "credit_days": 30,
                "description": f"Sample credit terms for {BATCH_ID}",
            }
        ).insert(ignore_permissions=True)
    if not frappe.db.exists("Payment Terms Template", PAYMENT_TEMPLATE):
        frappe.get_doc(
            {
                "doctype": "Payment Terms Template",
                "template_name": PAYMENT_TEMPLATE,
                "terms": [
                    {
                        "payment_term": PAYMENT_TERM,
                        "invoice_portion": 100,
                        "due_date_based_on": "Day(s) after invoice date",
                        "credit_days": 30,
                    }
                ],
            }
        ).insert(ignore_permissions=True)
    if not frappe.db.exists("Payment Terms Template", CASH_TEMPLATE):
        frappe.get_doc(
            {
                "doctype": "Payment Terms Template",
                "template_name": CASH_TEMPLATE,
                "terms": [
                    {
                        "payment_term": "COD",
                        "invoice_portion": 100,
                        "due_date_based_on": "Day(s) after invoice date",
                        "credit_days": 0,
                    }
                ],
            }
        ).insert(ignore_permissions=True)
    return PAYMENT_TEMPLATE


def _customer_by_name(customer_name: str) -> str | None:
    return frappe.db.get_value("Customer", {"customer_name": customer_name}, "name")


def _ensure_customer(spec: dict) -> str:
    customer = _customer_by_name(spec["customer_name"])
    payment_template = spec.get("payment_template", PAYMENT_TEMPLATE)
    if not customer:
        doc = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": spec["customer_name"],
                "customer_type": spec["customer_type"],
                "customer_group": CUSTOMER_GROUP,
                "territory": TERRITORY,
                "default_price_list": PRICE_LIST,
                "payment_terms": payment_template,
                "credit_limits": [
                    {
                        "company": COMPANY,
                        "credit_limit": spec["credit_limit"],
                        "bypass_credit_limit_check": 0,
                    }
                ],
            }
        )
        customer = doc.insert(ignore_permissions=True).name
    elif frappe.db.get_value("Customer", customer, "payment_terms") != payment_template:
        frappe.db.set_value(
            "Customer", customer, "payment_terms", payment_template, update_modified=False
        )

    address_title = f"{spec['customer_name']} - Billing"
    if not frappe.db.exists("Address", {"address_title": address_title}):
        frappe.get_doc(
            {
                "doctype": "Address",
                "address_title": address_title,
                "address_type": "Billing",
                "address_line1": f"TEST ADDRESS - {spec['branch']}",
                "city": spec["city"],
                "country": "Philippines",
                "email_id": spec["email"],
                "phone": "+63 999 000 0000",
                "links": [{"link_doctype": "Customer", "link_name": customer}],
            }
        ).insert(ignore_permissions=True)

    first_name = spec["customer_name"].removeprefix("TEST ").split()[0]
    last_name = "Test Contact"
    if not frappe.db.exists("Contact", {"first_name": first_name, "last_name": last_name}):
        frappe.get_doc(
            {
                "doctype": "Contact",
                "first_name": first_name,
                "last_name": last_name,
                "designation": "Test Purchasing Contact",
                "email_ids": [{"email_id": spec["email"], "is_primary": 1}],
                "phone_nos": [{"phone": "+63 999 000 0000", "is_primary_phone": 1}],
                "links": [{"link_doctype": "Customer", "link_name": customer}],
            }
        ).insert(ignore_permissions=True)
    return customer


def _item_rate(item_code: str) -> float:
    rate = frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "price_list": PRICE_LIST, "selling": 1},
        "price_list_rate",
        order_by="valid_from desc, modified desc",
    )
    if not rate:
        frappe.throw(f"Existing item {item_code} has no {PRICE_LIST} price.")
    return float(rate)


def _ensure_test_stock() -> str:
    existing = frappe.db.get_value(
        "Stock Entry",
        {"remarks": ["like", f"%{BATCH_ID}%"], "docstatus": ["!=", 2]},
        "name",
    )
    if existing:
        return existing

    company = frappe.db.get_value(
        "Company",
        COMPANY,
        ["stock_adjustment_account", "cost_center"],
        as_dict=True,
    )
    entry = frappe.get_doc(
        {
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "company": COMPANY,
            "posting_date": date.today(),
            "remarks": f"TEST DATA {BATCH_ID} - reversible opening stock for sales exercises",
        }
    )
    for item_code in ITEMS:
        item = frappe.db.get_value(
            "Item", item_code, ["stock_uom", "disabled", "is_stock_item"], as_dict=True
        )
        if not item or item.disabled or not item.is_stock_item:
            frappe.throw(f"Existing item {item_code} is not an active stock item.")
        selling_rate = _item_rate(item_code)
        qty = 20 if item.stock_uom in {"Gallon", "Box", "Carton"} else 500
        entry.append(
            "items",
            {
                "item_code": item_code,
                "t_warehouse": STOCK_WAREHOUSE,
                "qty": qty,
                "uom": item.stock_uom,
                "stock_uom": item.stock_uom,
                "conversion_factor": 1,
                "basic_rate": max(round(selling_rate * 0.55, 2), 0.01),
                "expense_account": company.stock_adjustment_account,
                "cost_center": company.cost_center,
            },
        )
    entry.insert(ignore_permissions=True)
    entry.submit()
    return entry.name


def _write_manifest(manifest: dict) -> str:
    content = json.dumps(manifest, indent=2, default=str)
    file_doc = save_file(MANIFEST_FILE, content, "Company", COMPANY, is_private=1)
    return file_doc.file_url


def seed_sales_sample_data() -> dict:
    """Create reversible CHS-only sales prerequisites without changing Item or Warehouse masters."""
    _ensure_customer_group()
    _ensure_territory()
    _ensure_payment_terms()
    customers = [_ensure_customer(spec) for spec in CUSTOMERS]
    stock_entry = _ensure_test_stock()
    manifest = {
        "batch_id": BATCH_ID,
        "company": COMPANY,
        "created_on": frappe.utils.now(),
        "preserve": ["Item", "Warehouse"],
        "customer_group": CUSTOMER_GROUP,
        "territory": TERRITORY,
        "payment_term": PAYMENT_TERM,
        "payment_terms_template": PAYMENT_TEMPLATE,
        "cash_payment_terms_template": CASH_TEMPLATE,
        "customers": customers,
        "items_used": list(ITEMS),
        "warehouse_used": STOCK_WAREHOUSE,
        "stock_entry": stock_entry,
    }
    manifest["manifest_file"] = _write_manifest(manifest)
    frappe.db.commit()
    return manifest


def preview_sales_sample_cleanup() -> dict:
    """Read-only cleanup preview. This function never cancels or deletes documents."""
    customers = frappe.get_all(
        "Customer", filters={"customer_group": CUSTOMER_GROUP}, pluck="name"
    )
    preview = {
        "batch_id": BATCH_ID,
        "customers": customers,
        "addresses": frappe.get_all(
            "Dynamic Link",
            filters={"link_doctype": "Customer", "link_name": ["in", customers]},
            fields=["parenttype", "parent"],
        )
        if customers
        else [],
        "quotations": frappe.get_all(
            "Quotation", filters={"quotation_to": "Customer", "party_name": ["in", customers]}, pluck="name"
        )
        if customers
        else [],
        "sales_orders": frappe.get_all("Sales Order", filters={"customer": ["in", customers]}, pluck="name")
        if customers
        else [],
        "delivery_notes": frappe.get_all("Delivery Note", filters={"customer": ["in", customers]}, pluck="name")
        if customers
        else [],
        "sales_invoices": frappe.get_all("Sales Invoice", filters={"customer": ["in", customers]}, pluck="name")
        if customers
        else [],
        "payment_entries": frappe.get_all(
            "Payment Entry",
            filters={"party_type": "Customer", "party": ["in", customers]},
            pluck="name",
        )
        if customers
        else [],
        "stock_entries": frappe.get_all(
            "Stock Entry", filters={"remarks": ["like", f"%{BATCH_ID}%"]}, fields=["name", "docstatus"]
        ),
        "protected_item_count": len(ITEMS),
        "protected_warehouses": [STOCK_WAREHOUSE],
    }
    return preview
