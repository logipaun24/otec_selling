# Item-level physical returns

Original Delivery Note rows show read-only **Returned Qty** and **Qty Retained by
Client**, in the original row's delivery UOM. Original quantities, prices, taxes
and amounts remain unchanged. Returns are summed in stock UOM and converted using
the original row's conversion factor; duplicate item codes remain separate.

Only submitted return Delivery Notes linked by `return_against` and `dn_detail`
count. Draft/cancelled receipts, approval-only RMAs and credit-only transactions do
not count. Cancelling a receipt recalculates the source. Historical over-returns
show a negative retained quantity rather than silently hiding the discrepancy.

The three existing delivery print formats show these balances in each quantity
cell. Price columns, print-token/status checks and DR serial handling are preserved.
Reprinting remains subject to the existing policy. Retained quantity is a balance,
not proof of signed customer acceptance.

Setup runs after fixtures on install/migrate. Three site-local Server Scripts
(Before Validate / After Submit / After Cancel) maintain the display fields.
Server Scripts must remain enabled. Setup backfills submitted original DNs.
Only derived fields, three print layouts and feature configuration are changed.

A targeted rollout can execute `setup_delivery_item_returns` from the reviewed
module on the selected site after backup, without replacing shared-bench app code.
Reload an open original DN after its return is submitted or cancelled. Users with
saved grid layouts can add the fields with the grid's column selector.
