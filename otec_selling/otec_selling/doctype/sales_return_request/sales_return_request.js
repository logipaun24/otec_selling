frappe.ui.form.on("Sales Return Request", {
    setup(frm) {
        const warehouse_filter = () => ({ filters: { company: frm.doc.company, is_group: 0, disabled: 0 } });
        frm.set_query("default_return_warehouse", warehouse_filter);
        frm.set_query("quarantine_warehouse", warehouse_filter);
        frm.set_query("return_warehouse", "items", warehouse_filter);
        frm.set_query("delivery_note", () => ({ filters: { customer: frm.doc.customer, company: frm.doc.company, docstatus: 1, is_return: 0 } }));
        frm.set_query("sales_invoice", () => ({ filters: { customer: frm.doc.customer, company: frm.doc.company, docstatus: 1, is_return: 0 } }));
    },
    refresh(frm) {
        if (frm.doc.docstatus !== 1) return;
        const roles = frappe.user_roles || [];
        if (["Stock User", "Stock Manager", "System Manager", "Sales Team Leader", "Sales Supervisor"].some(r => roles.includes(r)) && frm.doc.receive_status !== "Received") {
            frm.add_custom_button(__("Return Receipt"), () => open_mapped(frm, "otec_selling.sales_returns.make_return_delivery_note", "Delivery Note"), __("Create"));
        }
        if (["Accounts User", "Accounts Manager", "System Manager"].some(r => roles.includes(r))) {
            if (frm.doc.credit_status !== "Credited") {
                frm.add_custom_button(__("Credit Note"), () => open_mapped(frm, "otec_selling.sales_returns.make_credit_note", "Sales Invoice"), __("Create"));
            }
            if (frm.doc.credit_status !== "Not Credited" && frm.doc.return_type === "Refund" && frm.doc.refund_status !== "Refunded") {
                frm.add_custom_button(__("Refund Payment"), () => open_mapped(frm, "otec_selling.sales_returns.make_refund_payment", "Payment Entry"), __("Create"));
            }
            if (frm.doc.credit_status === "Credited" && frm.doc.return_type !== "Refund" && !frm.doc.settlement_completed) {
                frm.add_custom_button(__("Mark Settlement Complete"), () => frappe.call({
                    method: "otec_selling.sales_returns.mark_settlement_complete",
                    args: { name: frm.doc.name },
                    freeze: true,
                    callback: () => frm.reload_doc()
                }));
            }
        }
    }
});

function open_mapped(frm, method, doctype) {
    frappe.call({
        method,
        args: { name: frm.doc.name },
        freeze: true,
        callback(r) {
            if (!r.message) return;
            const docs = frappe.model.sync(r.message);
            frappe.set_route("Form", doctype, docs[0].name);
        }
    });
}
