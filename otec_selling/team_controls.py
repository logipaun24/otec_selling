"""Site-local team controls; the same restricted code is tested and deployed."""

import frappe

DOCTYPES = ("Sales Order", "Pick List", "Delivery Note", "Sales Invoice", "Sales Return Request")
CORE = """
def team_field(record):
    return "sales_team_group" if record.doctype == "Sales Return Request" else "custom_sales_team_group"

def assigned_teams(user, company, branch):
    rows = frappe.get_all("Sales Access Hierarchy", filters={"user": user, "active": 1},
        fields=["name", "position", "company", "branch", "sales_team_group"], limit_page_length=2)
    if len(rows) != 1:
        return []
    h = rows[0]
    companies = [h.company] if h.company else []
    branches = [h.branch] if h.branch else []
    teams = [h.sales_team_group] if h.sales_team_group else []
    for dt, field, parentfield, values in (
        ("Sales Hierarchy Company Access", "company", "allowed_companies", companies),
        ("Sales Hierarchy Branch Access", "branch", "allowed_branches", branches),
        ("Sales Hierarchy Team Access", "sales_team_group", "allowed_sales_teams", teams)):
        if field == "sales_team_group" and h.position not in ("Team Leader", "Supervisor", "Business Owner"):
            continue
        for row in frappe.get_all(dt, filters={"parent": h.name, "parenttype": "Sales Access Hierarchy",
            "parentfield": parentfield}, fields=[field]):
            if row.get(field) and row.get(field) not in values:
                values.append(row.get(field))
    if company not in companies or (h.position != "Business Owner" and branch not in branches):
        return []
    if h.position == "Business Owner":
        return frappe.get_all("Sales Team Group", filters={"company": company, "branch": branch, "active": 1},
            pluck="name", order_by="name")
    return frappe.get_all("Sales Team Group", filters={"name": ["in", teams], "company": company,
        "branch": branch, "active": 1}, pluck="name", order_by="name") if teams else []

def source_documents(record):
    refs = []
    if record.doctype == "Sales Return Request":
        if record.get("source_doctype") in ("Sales Invoice", "Delivery Note") and record.get("source_document"):
            refs.append([record.source_doctype, record.source_document])
        for field, dt in (("sales_invoice", "Sales Invoice"), ("delivery_note", "Delivery Note"), ("sales_order", "Sales Order")):
            if record.get(field): refs.append([dt, record.get(field)])
    if record.get("return_against") and record.doctype in ("Delivery Note", "Sales Invoice"):
        refs.append([record.doctype, record.return_against])
    if record.doctype != "Sales Order":
        for row in record.get("locations" if record.doctype == "Pick List" else "items", []):
            name = row.get("sales_order") or row.get("against_sales_order")
            if name: refs.append(["Sales Order", name])
            if record.doctype == "Sales Invoice" and row.get("delivery_note"):
                refs.append(["Delivery Note", row.delivery_note])
    documents = []
    seen = []
    for dt, name in refs:
        if [dt, name] not in seen:
            seen.append([dt, name])
            documents.append(frappe.get_doc(dt, name))
    return documents

def validate_team(record, required=False, filling_legacy=False, team_field=team_field,
    assigned_teams=assigned_teams, source_documents=source_documents):
    field = team_field(record)
    team = record.get(field) or ""
    previous = record.get_doc_before_save() if not filling_legacy else None
    approved_states = ("Approved for Fulfillment", "RMA Approved")
    if previous and (previous.docstatus == 1 or previous.get("workflow_state") in approved_states):
        if (previous.get(field) or "") != team:
            frappe.throw("Team ownership is locked after approval. Use the audited missing-team correction or cancel/amend.")
        if previous.docstatus == 1:
            return  # Existing submitted records can continue status/receipt updates.
    required = required or record.docstatus == 1 or record.get("workflow_state") in approved_states
    sources = source_documents(record)
    if sources:
        source_teams = []
        for source in sources:
            if source.company != record.company:
                frappe.throw("The source sale belongs to another company.")
            value = source.get(team_field(source)) or ""
            if value not in source_teams: source_teams.append(value)
        if len(source_teams) > 1:
            frappe.throw("Sources have different or incomplete teams. Correct missing source teams and split different teams into separate documents.")
        inherited = source_teams[0]
        if not inherited:
            if required or team:
                frappe.throw("Assign the original sale's team before approving this document. Do not use the processor's team.")
            return
        if team and team != inherited:
            frappe.throw("The team must match the original sale: " + inherited)
        record.set(field, inherited)
        return
    if record.doctype in ("Pick List", "Sales Return Request") or record.get("is_return"):
        if required: frappe.throw("A linked original sale with an assigned team is required.")
        return
    branch = record.get("branch") or record.get("custom_branch")
    owner = record.get("custom_sales_user") or record.get("owner") or frappe.session.user
    choices = assigned_teams(owner, record.get("company"), branch)
    if not team and len(choices) == 1:
        team = choices[0]
        record.set(field, team)
    if team and team not in choices:
        frappe.throw("Select a team assigned to the sale's owner for this company and branch.")
    roles = frappe.get_all("Has Role", filters={"parent": frappe.session.user, "parenttype": "User"}, pluck="role")
    if team and frappe.session.user != "Administrator" and not any(r in roles for r in ("System Manager", "Business Owner")):
        if team not in assigned_teams(frappe.session.user, record.get("company"), branch):
            frappe.throw("You cannot assign a sale to a team outside your own scope.")
    if required and not team:
        frappe.throw("Select an accountable Sales Team before approval/submission. Multi-team managers do not need a default team.")
"""

CORRECTION = """
roles = frappe.get_all("Has Role", filters={"parent": frappe.session.user, "parenttype": "User"}, pluck="role")
if frappe.session.user != "Administrator" and not any(r in roles for r in ("System Manager", "Business Owner")):
    frappe.throw("Only System Manager or Business Owner may correct legacy team ownership.")
dt = frappe.form_dict.get("doctype")
if dt not in ("Sales Order", "Pick List", "Delivery Note", "Sales Invoice", "Sales Return Request"):
    frappe.throw("Unsupported document.")
reason = (frappe.form_dict.get("reason") or "").strip()
if len(reason) < 10:
    frappe.throw("Provide a meaningful reason (at least 10 characters).")
record = frappe.get_doc(dt, frappe.form_dict.get("name"), for_update=True)
record.check_permission("write")
field = team_field(record)
if record.get(field) or record.docstatus == 2:
    frappe.throw("This action fills missing teams only; it cannot reassign or change cancelled documents.")
team = frappe.form_dict.get("team") or ""
if not team or not frappe.db.exists("Sales Team Group", team):
    frappe.throw("Select a valid team.")
record.set(field, team)
validate_team(record, required=True, filling_legacy=True)
frappe.db.set_value(dt, record.name, field, record.get(field))
record.add_comment("Comment", "Legacy team assignment: [unassigned] to " + frappe.utils.escape_html(record.get(field))
    + ". Reason: " + frappe.utils.escape_html(reason))
frappe.response["message"] = {"name": record.name, "team": record.get(field)}
"""

CHOICES = """
record = frappe.get_doc(frappe.form_dict.get("doctype"), frappe.form_dict.get("name"))
if record.doctype not in ("Sales Order", "Delivery Note", "Sales Invoice", "Sales Return Request", "Pick List"):
    frappe.throw("Unsupported document.")
record.check_permission("read")
choices = assigned_teams(record.get("custom_sales_user") or record.get("sales_user") or record.owner,
    record.company, record.get("branch") or record.get("custom_branch"))
roles = frappe.get_all("Has Role", filters={"parent": frappe.session.user, "parenttype": "User"}, pluck="role")
if frappe.session.user != "Administrator" and not any(r in roles for r in ("System Manager", "Business Owner")):
    actor_choices = assigned_teams(frappe.session.user, record.company, record.get("branch") or record.get("custom_branch"))
    choices = [t for t in choices if t in actor_choices]
frappe.response["message"] = choices
"""

CLIENT = """
frappe.ui.form.on(DOCTYPE, {
    refresh(frm) {
        const field = frm.doctype === 'Sales Return Request' ? 'sales_team_group' : 'custom_sales_team_group';
        if (frm.is_new()) return;
        frappe.call({method:'otec_team_choices', args:{doctype:frm.doctype,name:frm.doc.name}}).then(r => {
            const teams = r.message || [];
            frm.set_query(field, () => ({filters:{name:['in',teams]}}));
            const linked = frm.doc.return_against || (frm.doc.items || []).some(row => row.sales_order || row.against_sales_order || row.delivery_note);
            if (frm.doc.docstatus === 0 && ['Sales Order','Delivery Note','Sales Invoice'].includes(frm.doctype) && !linked) {
                frm.set_df_property(field, 'read_only', 0);
                if (!frm.doc[field]) frm.dashboard.set_headline_alert('Select the accountable Sales Team before approval. Linked documents must match their source.', 'orange');
            }
            if (!frm.doc[field] && frm.doc.docstatus !== 2 &&
                (frappe.user.has_role('System Manager') || frappe.user.has_role('Business Owner'))) {
                frm.add_custom_button('Assign Missing Team', () => frappe.prompt([
                    {fieldname:'team',label:'Confirmed Team',fieldtype:'Link',options:'Sales Team Group',reqd:1},
                    {fieldname:'reason',label:'Reason / ownership evidence',fieldtype:'Small Text',reqd:1}
                ], values => frappe.call({method:'otec_correct_missing_team', args:{doctype:frm.doctype,name:frm.doc.name,...values}})
                    .then(() => frm.reload_doc()), 'Audited Team Assignment', 'Assign'), 'Ownership');
            }
        });
    }
});
"""


def setup_team_controls():
	for dt in DOCTYPES:
		for event in ("Before Save", "Before Submit", "Before Save (Submitted Document)"):
			name = "OTEC Team Ownership - " + dt + " - " + event
			script = (
				frappe.get_doc("Server Script", name)
				if frappe.db.exists("Server Script", name)
				else frappe.new_doc("Server Script")
			)
			script.update(
				{
					"name": name,
					"script_type": "DocType Event",
					"reference_doctype": dt,
					"doctype_event": event,
					"disabled": 0,
					"script": CORE + "\nvalidate_team(doc, required=" + str(event == "Before Submit") + ")\n",
				}
			)
			script.save(ignore_permissions=True)
		name = "OTEC Team Selection - " + dt
		client = (
			frappe.get_doc("Client Script", name)
			if frappe.db.exists("Client Script", name)
			else frappe.new_doc("Client Script")
		)
		client.update(
			{
				"name": name,
				"dt": dt,
				"view": "Form",
				"enabled": 1,
				"script": CLIENT.replace("DOCTYPE", repr(dt)),
			}
		)
		client.save(ignore_permissions=True)
	for method, body in (("otec_team_choices", CHOICES), ("otec_correct_missing_team", CORRECTION)):
		name = "OTEC " + method
		script = (
			frappe.get_doc("Server Script", name)
			if frappe.db.exists("Server Script", name)
			else frappe.new_doc("Server Script")
		)
		script.update(
			{
				"name": name,
				"script_type": "API",
				"api_method": method,
				"allow_guest": 0,
				"disabled": 0,
				"script": CORE + "\n" + body,
			}
		)
		script.save(ignore_permissions=True)
	frappe.clear_cache()
