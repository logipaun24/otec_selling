# Branch fulfillment and commercial approval

This repository update takes effect after installing the updated app and running
site migration. A GitHub push alone does not update an ERPNext site.

## Process

1. Sales creates the Quotation and Sales Order with the existing sales owner,
   team, company and branch fields.
2. The responsible TL or Supervisor approves within their commercial scope.
   Both may approve their own transactions. Existing exception flags still
   require Business Owner approval; the patch does not change discount limits.
3. For branch-local fulfillment, any TL or Supervisor assigned to that branch
   may process its delivery Pick Lists and Delivery Notes, including other teams'
   approved orders. Use the new **Branch Fulfillment** workspace.
4. Pick List: Draft → Send to Warehouse → For Picking → Start Picking → Picking
   → Confirm Picked → Picked. At a branch, the TL/Supervisor performs these actions;
   the existing action label does not mean physical transfer to a central warehouse.
5. Create the Delivery Note from the approved order/picked items, verify actual
   warehouses and quantities, and submit. Existing stock validations still apply.
6. Accounting continues invoicing, credit notes and payments under its existing
   permissions. This update grants no additional accounting posting rights.
7. For returns, request and approve the RMA first. A branch TL/Supervisor may
   create and submit the return receipt into the assigned branch-local warehouse.
   Credit-only exceptions still require Business Owner approval.

## Access boundaries

| Activity | TL / Supervisor | Central warehouse staff |
| --- | --- | --- |
| Commercial editing/approval | Own transactions and assigned teams, within company/branch scope | Unchanged |
| Read approved orders/RMAs | Entire assigned branch | Unchanged |
| Read Pick Lists/Delivery Notes | Entire assigned branch | Unchanged |
| Branch delivery picking and dispatch/return receipt | Entire assigned branch, local warehouses | Existing rights |
| Central fulfillment | Only with an existing Stock role and explicit Warehouse User Permission | Existing rights |
| Stock Entry, reconciliation, manufacturing picking, accounting | No new rights | Unchanged |

An active, unambiguous Sales Access Hierarchy record and matching TL/Supervisor
role are required. Primary and child-table company/branch/team assignments are
combined. A default team is not required for branch fulfillment; managing several
teams does not confer commercial access to every team in the branch.

Each branch must have `custom_default_branch_warehouse` configured. Its warehouse
subtree defines local stock. Actual item warehouses and linked Sales Order routes
are checked on save and submit. A central-fulfillment flag cannot be cleared on a
Pick List to bypass its source order. Warehouse User Permissions must apply to
the actual document type (or all types); native User Permissions remain enforced.

## Migration and audit

The idempotent installer runs after fixtures on install and migrate. It grants
read/create/write/submit/print on Pick List and Delivery Note to existing TL/Sup
roles, plus read/select on supporting stock masters. It does not assign Stock
Manager, change existing users' hierarchy assignments, or grant cancellation.
Stock Reservation Entry read/create/write/submit is limited by server guards to
matching items of submitted delivery Pick Lists within the same fulfillment scope.
The existing auto-reservation step is retained. Return receipts are excluded from
outgoing central-route checks; normal return/RMA and DR paper checks remain active.
Serial and Batch Bundle read/create/write/submit supports picking and delivery
within the same scope, not manufacturing or Stock Entry bundles. Unsaved parent
documents may prepare local bundles; central parents must be saved first.

`Fulfillment Workflow User` is a helper role with **no document permissions**. It
allows the common Pick List states to be edited by existing sales/stock roles;
normal permissions and branch guards still control saving and submission. It is
synchronized for existing users at migration and on subsequent User saves.

The obsolete Quotation approval-scope Server Script is disabled in favor of
server-side document hooks. Existing commercial conditions are preserved and
self-approval cannot override the Business Owner exception flag.

New submissions stamp commercial approver/time/self-approval or fulfillment
operator/time. Native `owner` preserves the creator. Historical records are not
backfilled. Existing cancellation and accounting policies remain unchanged.

Before production rollout, run CI and stage a full transaction using an actual
TL, Supervisor, representative and warehouse user. Include another branch,
multiple managed teams, central stock, a flagged exception, and a branch return.
Back up the site, deploy the selected commit, run `bench --site <site> migrate`,
and restart/build through the hosting provider's normal deployment process.
