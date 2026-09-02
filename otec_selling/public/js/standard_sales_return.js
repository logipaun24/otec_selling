function add_rma_button(frm, source_doctype) {
    if (frm.doc.docstatus !== 1 || frm.doc.is_return) return;
    if (!frappe.model.can_create("Sales Return Request")) return;
    frm.add_custom_button(__("Sales Return Request"), () => {
        frappe.call({
            method: "otec_selling.sales_returns.make_request_from_source",
            args: { source_doctype, source_name: frm.doc.name },
            freeze: true,
            callback(r) {
                if (!r.message) return;
                const docs = frappe.model.sync(r.message);
                frappe.set_route("Form", "Sales Return Request", docs[0].name);
            }
        });
    }, __("Create"));
}

frappe.ui.form.on("Delivery Note", { refresh(frm) { add_rma_button(frm, "Delivery Note"); } });
frappe.ui.form.on("Sales Invoice", { refresh(frm) { add_rma_button(frm, "Sales Invoice"); } });

