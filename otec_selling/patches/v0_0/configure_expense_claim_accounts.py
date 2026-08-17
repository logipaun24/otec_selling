import frappe


COMPANY_CONFIGS = {
    "OTEC International Trade Corporation": {
        "payable": "2110 - Creditors - OITC",
        "mappings": {
            "Calls": "5215 - Telephone Expenses - OITC",
            "Food": "5204 - Entertainment Expenses - OITC",
            "Medical": "5223 - Miscellaneous Expenses - OITC",
            "Others": "5223 - Miscellaneous Expenses - OITC",
            "Travel": "5216 - Travel Expenses - OITC",
        },
    },
    "Comfort Hotel Supplies": {
        "payable": "2110 - Creditors - CHS",
        "mappings": {
            "Calls": "5215 - Telephone Expenses - CHS",
            "Food": "5204 - Entertainment Expenses - CHS",
            "Medical": "5223 - Miscellaneous Expenses - CHS",
            "Others": "5223 - Miscellaneous Expenses - CHS",
            "Travel": "5216 - Travel Expenses - CHS",
        },
    },
}


def execute():
    for company_name, config in COMPANY_CONFIGS.items():
        if not frappe.db.exists("Company", company_name):
            continue

        required_accounts = [config["payable"], *config["mappings"].values()]
        missing_accounts = [
            account
            for account in required_accounts
            if not frappe.db.exists("Account", account)
        ]
        if missing_accounts:
            frappe.throw(
                f"Cannot configure Expense Claims for {company_name}. "
                f"Missing accounts: {', '.join(missing_accounts)}"
            )

        company = frappe.get_doc("Company", company_name)
        company.default_expense_claim_payable_account = config["payable"]
        company.save(ignore_permissions=True)

        for claim_type, default_account in config["mappings"].items():
            if not frappe.db.exists("Expense Claim Type", claim_type):
                continue

            expense_claim_type = frappe.get_doc("Expense Claim Type", claim_type)
            mapping = next(
                (row for row in expense_claim_type.accounts if row.company == company_name),
                None,
            )
            if mapping:
                mapping.default_account = default_account
            else:
                expense_claim_type.append(
                    "accounts",
                    {"company": company_name, "default_account": default_account},
                )
            expense_claim_type.save(ignore_permissions=True)
