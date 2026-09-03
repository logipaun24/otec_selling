import frappe

from otec_selling.sales_order_ownership import backfill_sales_order_ownership


def execute():
	report = backfill_sales_order_ownership(dry_run=False)
	frappe.logger("otec_selling").info(
		"Sales Order ownership backfill updated %s records; %s remain unresolved",
		len(report["updated"]),
		len(report["unresolved"]),
	)
