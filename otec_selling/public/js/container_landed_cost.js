frappe.ui.form.on("Container Landed Cost", {
    refresh(frm) {
        if (frm.doc.docstatus !== 0) return;

        frm.add_custom_button(__("Fetch Submitted Receipts"), () => {
            if (frm.is_new()) {
                frappe.msgprint(__("Save the document first."));
                return;
            }
            frappe.call({
                method: "otec_selling.purchasing_lifecycle.fetch_container_landed_cost_items",
                args: { docname: frm.doc.name },
                freeze: true,
                freeze_message: __("Fetching submitted Purchase Receipts..."),
                callback(r) {
                    if (r.message) frappe.msgprint(r.message);
                    frm.reload_doc();
                },
            });
        });

        if ((frm.doc.items || []).length) {
            frm.add_custom_button(__("Compute CBM Allocation"), () => {
                const run = () => frappe.call({
                    method: "otec_selling.purchasing_lifecycle.compute_container_landed_cost",
                    args: { docname: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Validating CBM and allocating charges..."),
                    callback() { frm.reload_doc(); },
                });
                frm.is_dirty() ? frm.save().then(run) : run();
            });
        }

        if (frm.doc.status === "Computed" && !frm.doc.landed_cost_voucher) {
            frm.add_custom_button(__("Create Landed Cost Voucher"), () => {
                frappe.confirm(__("Create a draft Landed Cost Voucher using the CBM allocation?"), () => {
                    frappe.call({
                        method: "otec_selling.purchasing_lifecycle.create_lcv_from_container",
                        args: { docname: frm.doc.name },
                        freeze: true,
                        freeze_message: __("Creating draft Landed Cost Voucher..."),
                        callback(r) {
                            if (r.message) frappe.set_route("Form", "Landed Cost Voucher", r.message);
                        },
                    });
                });
            });
        }
    },
});

frappe.ui.form.on("Container Landed Cost Item", {
    cbm_per_unit(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, "total_cbm", flt(row.received_qty) * flt(row.cbm_per_unit));
    },
});
