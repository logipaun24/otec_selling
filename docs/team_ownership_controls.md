# Accountable sales teams

Every approved/submitted Sales Order, sales Pick List, Delivery Note, Sales Invoice,
and Sales Return Request needs an accountable team. Incomplete drafts are allowed.
Independent orders/invoices/deliveries use the sales owner's active company/branch
team assignments; one choice is filled automatically. Managers with multiple
choices select a team on the saved draft. They need no default team.

Source-linked documents inherit the source team's ownership, not the warehouse
processor's team. Every linked order/delivery/invoice must agree. Mixed teams or
blank source teams block approval and submission; split mixed-team documents and
correct incomplete sources first. Existing fulfillment permissions and self-approval
conditions are unchanged. The additional validation also runs for API/import saves.

Approved ownership is locked. Submitted records with unchanged ownership may
continue normal receipt, credit and status updates, even if they predate this rule.
An existing assigned team cannot be rewritten with the correction API. Use the
normal authorized cancellation/amendment process for a genuine reassignment.

## Legacy corrections

System Managers and Business Owners with native write permission see **Ownership →
Assign Missing Team** on saved unassigned documents. A reason of at least ten
characters is required. The API locks the record, validates the team and sources,
fills only a blank team, and adds an audit comment with the actor and timestamp.
It does not change quantities, totals, accounts, or document status. Correct the
Sales Order first, then downstream documents; no automatic guessing between teams.

Team Sales Returns has a separate **Unassigned Returns — Needs Review** card.
Its records and count use native permissions plus the manager's company and branch
scope. It ignores the team selector because the records have no team, and excludes
cancelled records. It does not add unassigned returns to team totals or grant new
record access. Draft records hidden by native permissions remain hidden.

The installer creates named site-local Server Scripts and Client Scripts, and runs
after fixtures/migration. It does not update users, hierarchy records or transactions.
Deployment should include a database backup and a read-only legacy-gap audit. The
guards intentionally stop new downstream processing until missing source ownership
is resolved. Disabling the named OTEC Team Ownership scripts reverses enforcement;
configuration and correction comments remain auditable.
