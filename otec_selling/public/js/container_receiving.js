frappe.ui.form.on("Container Receiving", {
    refresh(frm) {
        if (frm.doc.status === "Completed") return;

        frm.add_custom_button(__("Fetch PO Items"), () => {
            if (!frm.doc.container_number) {
                frappe.msgprint(__("Container Number is required."));
                return;
            }
            frappe.call({
                method: "otec_selling.purchasing_lifecycle.fetch_container_receiving_items",
                args: { container_number: frm.doc.container_number },
                freeze: true,
                freeze_message: __("Fetching outstanding Purchase Orders..."),
                callback(r) {
                    const rows = r.message || [];
                    frm.clear_table("items");
                    rows.forEach((source) => {
                        const row = frm.add_child("items");
                        Object.assign(row, source, { arrived_qty: 0 });
                    });
                    frm.set_value("status", rows.length ? "Scanning" : "Draft");
                    frm.refresh_field("items");
                    frm.dirty();
                    frappe.show_alert({
                        message: __("{0} outstanding PO row(s) fetched.", [rows.length]),
                        indicator: rows.length ? "green" : "orange",
                    });
                },
            });
        });

        if (!frm.is_new() && ["Draft", "Scanning"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Create Purchase Receipts"), () => {
                if (!(frm.doc.items || []).some((row) => flt(row.arrived_qty) > 0)) {
                    frappe.msgprint(__("Enter an Arrived Qty greater than zero first."));
                    return;
                }
                frappe.confirm(__("Create draft Purchase Receipts for the scanned quantities?"), () => {
                    const run = () => frappe.call({
                        method: "otec_selling.purchasing_lifecycle.create_container_purchase_receipts",
                        args: { docname: frm.doc.name },
                        freeze: true,
                        freeze_message: __("Creating draft Purchase Receipts..."),
                        callback(r) {
                            const receipts = (r.message && r.message.created_receipts) || [];
                            frappe.msgprint({
                                title: __("Purchase Receipts Created"),
                                indicator: "green",
                                message: receipts.map((name) =>
                                    `<a href="/app/purchase-receipt/${encodeURIComponent(name)}">${frappe.utils.escape_html(name)}</a>`
                                ).join("<br>"),
                            });
                            frm.reload_doc();
                        },
                    });
                    frm.is_dirty() ? frm.save().then(run) : run();
                });
            });
        }
    },

    scan_barcode(frm) {
        const scanned = (frm.doc.scan_barcode || "").trim();
        if (!scanned) return;
        const [po_num, item_code] = scanned.split("|").map((value) => value.trim());
        if (!po_num || !item_code) {
            frappe.msgprint(__("Invalid barcode. Expected PO-NUMBER|ITEM-CODE."));
            frm.set_value("scan_barcode", "");
            return;
        }
        const row = (frm.doc.items || []).find(
            (item) => String(item.po_num || "").trim() === po_num && item.item_code === item_code
        );
        if (!row) {
            frappe.msgprint(__("No matching outstanding PO row was found."));
            frm.set_value("scan_barcode", "");
            return;
        }
        frappe.prompt(
            [{
                label: __("Arrived Qty"),
                fieldname: "qty",
                fieldtype: "Float",
                reqd: 1,
                default: flt(row.pending_qty) - flt(row.arrived_qty),
            }],
            (values) => {
                const maximum = flt(row.pending_qty);
                const total = flt(row.arrived_qty) + flt(values.qty);
                if (flt(values.qty) <= 0 || total > maximum) {
                    frappe.msgprint(__("Arrived Qty must be positive and cannot exceed Pending Qty {0}.", [maximum]));
                    return;
                }
                frappe.model.set_value(row.doctype, row.name, "arrived_qty", total);
                frm.set_value("scan_barcode", "");
                frm.dirty();
            },
            __("Record Arrival"),
            __("Add")
        );
    },
});
