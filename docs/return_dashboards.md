# Sales return dashboards

Open **My Sales Returns** or **Team Sales Returns** from the workspace sidebar.
Click a status card to filter the paginated request list. Request links open the
RMA. Request Date From/To are inclusive; blank dates include all dates. Customer,
status and (for team mode) managed-team filters apply to the list. Cards retain
the same date/customer/team scope while allowing a different status to be selected.

My scope is owner OR requested_by OR sales_user equals the authenticated user.
Team scope requires one active TL/Supervisor hierarchy and matching role; its
primary and allowed companies/branches/teams are combined. No default team is
required. Missing team assignments produce an empty dashboard, not branch-wide
access. A team filter cannot expand these assignments. All RMA reads use
`frappe.get_list`, including counts and customer choices, so native permissions
and app query restrictions still apply. The API accepts no target-user override.

Cards count requests, not units or monetary totals. Receipt, credit and settlement
cards may overlap because they describe separate stages of the same RMA. Receipt
cards follow the RMA's recorded receive_status, including completed requests that
do not require a physical receipt. Draft/rejected/cancelled requests have their
own filters. Approval workflow-state labels are explicit, not obsolete shortcuts.

Setup creates two workspaces, two Custom HTML Blocks and one authenticated Server
Script API. It changes no user roles, hierarchy assignments, transactions or existing
dashboards. It runs after fixtures on install/migrate and supports a targeted
site-only rollout without replacing code on other sites sharing the bench.
Server Scripts must remain enabled. Refresh the browser after installation.
