import frappe

from otec_selling.fulfillment_ownership import backfill_fulfillment_ownership


def execute():
	report = backfill_fulfillment_ownership(dry_run=False)
	frappe.logger("otec_selling").info(
		"Fulfillment ownership backfill updated %s records; %s remain unresolved",
		len(report["updated"]),
		len(report["unresolved"]),
	)
