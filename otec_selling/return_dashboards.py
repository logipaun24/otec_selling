"""Permission-aware, site-local workspaces for personal and managed-team RMAs."""

import json

import frappe

API_NAME = "otec_sales_return_dashboard"
STAGES = {
	"all": ("All Requests", []),
	"approval": ("Pending Approval", [["workflow_state", "=", "RMA Pending Approval"]]),
	"owner_approval": ("Business Owner Approval", [["workflow_state", "=", "RMA Pending Business Owner"]]),
	"awaiting": ("Awaiting Receipt", [["docstatus", "=", 1], ["receive_status", "=", "Not Received"]]),
	"partial": ("Partially Received", [["docstatus", "=", 1], ["receive_status", "=", "Partially Received"]]),
	"received": ("Fully Received", [["docstatus", "=", 1], ["receive_status", "=", "Received"]]),
	"credit": (
		"Credit Pending",
		[["docstatus", "=", 1], ["credit_status", "in", ["Not Credited", "Partially Credited"]]],
	),
	"settlement": ("Settlement Pending", [["docstatus", "=", 1], ["status", "=", "Settlement Pending"]]),
	"closed": ("Closed", [["docstatus", "=", 1], ["status", "=", "Closed"]]),
	"draft": ("Draft", [["workflow_state", "=", "RMA Draft"]]),
	"rejected": ("Rejected", [["workflow_state", "=", "RMA Rejected"]]),
	"cancelled": ("Cancelled", [["docstatus", "=", 2]]),
}

# Executed by Frappe's restricted Server Script API. Transaction reads MUST use
# get_list so native role/User Permissions and the app's RMA query hooks apply.
API_BODY = """
actor = frappe.session.user
if actor == "Guest":
    frappe.throw("Sign in to view sales returns.")
mode = frappe.form_dict.get("mode") or "my"
if mode not in ("my", "team"):
    frappe.throw("Invalid dashboard scope.")
stage = frappe.form_dict.get("stage") or "all"
if stage not in STAGES:
    frappe.throw("Invalid return status filter.")
base_filters = []
ownership_filters = []
teams = []
if mode == "my":
    ownership_filters = [["owner", "=", actor], ["sales_user", "=", actor], ["requested_by", "=", actor]]
else:
    actors = frappe.get_all("Sales Access Hierarchy", filters={"user": actor, "active": 1},
        fields=["name", "position", "company", "branch", "sales_team_group"], limit_page_length=2)
    roles = frappe.get_all("Has Role", filters={"parent": actor, "parenttype": "User"}, pluck="role")
    if len(actors) != 1:
        frappe.throw("Team Sales Returns requires one active Sales Access Hierarchy assignment.")
    hierarchy = actors[0]
    required_role = {"Team Leader": "Sales Team Leader", "Supervisor": "Sales Supervisor"}.get(hierarchy.position)
    if not required_role or required_role not in roles:
        frappe.throw("Team Sales Returns is for assigned Team Leaders and Supervisors.")
    company_scope = [hierarchy.company] if hierarchy.company else []
    branch_scope = [hierarchy.branch] if hierarchy.branch else []
    teams = [hierarchy.sales_team_group] if hierarchy.sales_team_group else []
    for row in frappe.get_all("Sales Hierarchy Company Access", filters={"parent": hierarchy.name,
        "parenttype": "Sales Access Hierarchy", "parentfield": "allowed_companies"}, fields=["company"]):
        if row.company and row.company not in company_scope:
            company_scope.append(row.company)
    for row in frappe.get_all("Sales Hierarchy Branch Access", filters={"parent": hierarchy.name,
        "parenttype": "Sales Access Hierarchy", "parentfield": "allowed_branches"}, fields=["branch"]):
        if row.branch and row.branch not in branch_scope:
            branch_scope.append(row.branch)
    for row in frappe.get_all("Sales Hierarchy Team Access", filters={"parent": hierarchy.name,
        "parenttype": "Sales Access Hierarchy", "parentfield": "allowed_sales_teams"}, fields=["sales_team_group"]):
        if row.sales_team_group and row.sales_team_group not in teams:
            teams.append(row.sales_team_group)
    if not company_scope or not branch_scope or not teams:
        base_filters.append(["name", "=", ""])  # Fail closed, never all teams.
    else:
        base_filters.extend([["company", "in", company_scope], ["branch", "in", branch_scope],
            ["sales_team_group", "in", teams]])
    chosen_team = frappe.form_dict.get("team") or ""
    if chosen_team:
        if chosen_team not in teams:
            frappe.throw("That team is not in your managed-team assignments.")
        base_filters.append(["sales_team_group", "=", chosen_team])
date_from = frappe.form_dict.get("date_from") or ""
date_to = frappe.form_dict.get("date_to") or ""
if date_from:
    date_from = frappe.utils.getdate(date_from)
    base_filters.append(["request_date", ">=", date_from])
if date_to:
    date_to = frappe.utils.getdate(date_to)
    base_filters.append(["request_date", "<=", date_to])
if date_from and date_to and date_from > date_to:
    frappe.throw("Request Date From must be on or before Request Date To.")
customers = frappe.get_list("Sales Return Request", filters=base_filters, or_filters=ownership_filters,
    fields=["customer"], group_by="customer", order_by="customer asc", limit_page_length=0)
if frappe.form_dict.get("customer"):
    base_filters.append(["customer", "=", frappe.form_dict.customer])
cards = []
selected_count = 0
for key in STAGES:
    spec = STAGES[key]
    result = frappe.get_list("Sales Return Request", filters=base_filters + spec[1],
        or_filters=ownership_filters, fields=[{"COUNT": "name", "as": "total"}], limit_page_length=1)
    total = frappe.utils.cint(result[0].total) if result else 0
    cards.append({"key": key, "label": spec[0], "count": total})
    if key == stage:
        selected_count = total
offset = max(0, min(frappe.utils.cint(frappe.form_dict.get("offset")), 1000000))
rows = frappe.get_list("Sales Return Request", filters=base_filters + STAGES[stage][1],
    or_filters=ownership_filters, fields=["name", "request_date", "customer", "sales_team_group",
        "workflow_state", "status", "receive_status", "credit_status", "refund_status"],
    order_by="request_date desc, creation desc, name desc", limit_start=offset, limit_page_length=20)
frappe.response["message"] = {"cards": cards, "rows": rows, "total": selected_count,
    "teams": sorted(teams), "customers": [row.customer for row in customers if row.customer],
    "offset": offset, "page_size": 20,
    "notice": "No managed teams are assigned. A default team is not required; add Allowed Sales Teams." if mode == "team" and not teams else ""}
"""

HTML = """<section class="returns-dashboard" data-mode="MODE">
<p>Request counts—not quantities. Receipt, credit and settlement cards may overlap.</p>
<div class="filters">
<label>Request Date From<input type="date" data-filter="date_from"></label>
<label>Request Date To<input type="date" data-filter="date_to"></label>
<label>Customer<select data-filter="customer"><option value="">All customers</option></select></label>
<label data-team-label>Sales Team<select data-filter="team"><option value="">All managed teams</option></select></label>
<label>Status<select data-filter="stage"><option value="all">All Requests</option></select></label>
<button type="button" data-refresh>Refresh</button><button type="button" data-reset>Clear filters</button>
</div>
<p data-message role="status" aria-live="polite"></p>
<div class="cards" aria-label="Return status counts"></div>
<div class="table-wrap"><table><thead><tr><th>Request</th><th>Request Date</th><th>Customer</th><th>Team</th><th>Approval</th><th>Status</th><th>Receipt</th><th>Credit</th><th>Refund</th></tr></thead><tbody></tbody></table></div>
<div class="pager"><button type="button" data-prev>Previous</button><span data-page></span><button type="button" data-next>Next</button></div>
</section>"""

JS = """(() => {
const root = root_element.querySelector('.returns-dashboard');
if (!root || root.dataset.ready) return;
root.dataset.ready = '1';
const mode = root.dataset.mode;
const filters = Object.fromEntries([...root.querySelectorAll('[data-filter]')].map(el => [el.dataset.filter, el]));
const message = root.querySelector('[data-message]');
const body = root.querySelector('tbody');
const cards = root.querySelector('.cards');
const previous = root.querySelector('[data-prev]');
const next = root.querySelector('[data-next]');
let offset = 0, generation = 0;
if (mode === 'my') root.querySelector('[data-team-label]').hidden = true;
function options(select, values, label) {
    const selected = select.value;
    select.replaceChildren(new Option(label, ''));
    values.forEach(value => select.add(new Option(value, value)));
    if (values.includes(selected)) select.value = selected;
}
async function refresh() {
    const ticket = ++generation;
    message.textContent = 'Loading sales returns…';
    previous.disabled = next.disabled = true;
    const args = {mode, offset};
    Object.entries(filters).forEach(([key, input]) => { args[key] = input.value; });
    try {
        const response = await frappe.call({method: 'otec_sales_return_dashboard', args});
        if (ticket !== generation) return;
        const data = response.message;
        options(filters.customer, data.customers, 'All customers');
        options(filters.team, data.teams, 'All managed teams');
        const selectedStage = args.stage || 'all';
        filters.stage.replaceChildren();
        cards.replaceChildren();
        data.cards.forEach(card => {
            filters.stage.add(new Option(card.label, card.key));
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'card';
            button.setAttribute('aria-pressed', String(card.key === selectedStage));
            const value = document.createElement('strong');
            value.textContent = card.count.toLocaleString();
            const label = document.createElement('span'); label.textContent = card.label;
            button.append(value, label);
            button.onclick = () => { filters.stage.value = card.key; offset = 0; refresh(); };
            cards.append(button);
        });
        filters.stage.value = selectedStage;
        body.replaceChildren();
        data.rows.forEach(row => {
            const tr = document.createElement('tr');
            ['name','request_date','customer','sales_team_group','workflow_state','status','receive_status','credit_status','refund_status'].forEach(field => {
                const td = document.createElement('td');
                if (field === 'name') {
                    const link = document.createElement('a');
                    link.href = '/desk/sales-return-request/' + encodeURIComponent(row.name);
                    link.textContent = row.name; td.append(link);
                } else td.textContent = row[field] || '—';
                tr.append(td);
            });
            body.append(tr);
        });
        message.textContent = data.notice || (data.total ? '' : 'No sales returns match these filters.');
        root.querySelector('[data-page]').textContent = data.total
            ? `${data.offset + 1}-${data.offset + data.rows.length} of ${data.total}` : '0 requests';
        previous.disabled = data.offset === 0;
        next.disabled = data.offset + data.rows.length >= data.total;
    } catch (error) {
        if (ticket !== generation) return;
        body.replaceChildren(); cards.replaceChildren();
        root.querySelector('[data-page]').textContent = '';
        message.textContent = 'Unable to load returns. Check your permissions and filter values, then refresh.';
    }
}
Object.values(filters).forEach(input => input.addEventListener('change', () => { offset = 0; refresh(); }));
root.querySelector('[data-refresh]').onclick = () => { offset = 0; refresh(); };
root.querySelector('[data-reset]').onclick = () => {
    Object.values(filters).forEach(input => { input.value = ''; });
    filters.stage.value = 'all'; offset = 0; refresh();
};
previous.onclick = () => { offset = Math.max(0, offset - 20); refresh(); };
next.onclick = () => { offset += 20; refresh(); };
refresh();
})();"""

CSS = """.returns-dashboard{font:14px system-ui;color:var(--text-color,#333);padding:12px}
.filters{display:flex;flex-wrap:wrap;gap:12px;align-items:end}.filters label{display:flex;flex-direction:column;gap:5px;font-size:12px}
input,select,button{font:inherit;color:inherit;background:var(--control-bg,#fff);border:1px solid var(--border-color,#ddd);border-radius:6px;padding:8px}
button{cursor:pointer}button:disabled{opacity:.5;cursor:default}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}
.card{text-align:left;min-height:85px}.card strong{display:block;font-size:26px;margin-bottom:6px}.card[aria-pressed=true]{border-color:#2490ef;background:var(--blue-50,#edf6ff)}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{text-align:left;padding:10px;border-bottom:1px solid var(--border-color,#ddd)}
a{color:var(--primary,#2490ef)}.pager{display:flex;gap:15px;align-items:center;justify-content:end;margin-top:15px}[hidden]{display:none!important}"""


def api_script():
	return "STAGES = " + repr(STAGES) + "\n" + API_BODY


def setup_return_dashboards():
	name = "OTEC Sales Return Dashboard API"
	script = (
		frappe.get_doc("Server Script", name)
		if frappe.db.exists("Server Script", name)
		else frappe.new_doc("Server Script")
	)
	script.update(
		{
			"name": name,
			"script_type": "API",
			"api_method": API_NAME,
			"allow_guest": 0,
			"disabled": 0,
			"script": api_script(),
		}
	)
	script.save(ignore_permissions=True)
	for title, mode, roles in (
		("My Sales Returns", "my", ["Sales User", "Sales Team Leader", "Sales Supervisor", "System Manager"]),
		("Team Sales Returns", "team", ["Sales Team Leader", "Sales Supervisor"]),
	):
		block_name = "OTEC " + title
		block = (
			frappe.get_doc("Custom HTML Block", block_name)
			if frappe.db.exists("Custom HTML Block", block_name)
			else frappe.new_doc("Custom HTML Block")
		)
		block.update(
			{
				"name": block_name,
				"private": 0,
				"html": HTML.replace('data-mode="MODE"', 'data-mode="' + mode + '"'),
				"script": JS,
				"style": CSS,
			}
		)
		block.set("roles", [{"role": role} for role in roles])
		block.save(ignore_permissions=True)
		workspace = (
			frappe.get_doc("Workspace", title)
			if frappe.db.exists("Workspace", title)
			else frappe.new_doc("Workspace")
		)
		workspace.update(
			{
				"name": title,
				"label": title,
				"title": title,
				"public": 1,
				"module": "OTEC Selling",
				"icon": "refresh",
				"content": json.dumps(
					[
						{"id": "returns-title", "type": "header", "data": {"text": title, "col": 12}},
						{
							"id": "returns-dashboard",
							"type": "custom_block",
							"data": {"custom_block_name": block_name, "col": 12},
						},
					]
				),
			}
		)
		workspace.set("roles", [{"role": role} for role in roles])
		workspace.set("custom_blocks", [{"custom_block_name": block_name, "label": block_name}])
		workspace.save(ignore_permissions=True)
		setup_dashboard_navigation(title, roles)
	frappe.clear_cache()


def setup_dashboard_navigation(title, roles):
	"""v16 navigation is separate from Workspace; preserve existing sidebar items."""
	sidebar = (
		frappe.get_doc("Workspace Sidebar", title)
		if frappe.db.exists("Workspace Sidebar", title)
		else frappe.get_doc(
			{
				"doctype": "Workspace Sidebar",
				"title": title,
				"standard": 1,
				"app": "otec_selling",
				"module": "OTEC Selling",
				"header_icon": "refresh",
			}
		)
	)
	if not any(row.link_type == "Workspace" and row.link_to == title for row in sidebar.items):
		sidebar.append("items", {"type": "Link", "label": title, "link_type": "Workspace", "link_to": title})
		sidebar.save(ignore_permissions=True)
	if not frappe.db.exists("Desktop Icon", title):
		icon = frappe.get_doc(
			{
				"doctype": "Desktop Icon",
				"label": title,
				"standard": 1,
				"app": "otec_selling",
				"icon_type": "Link",
				"link_type": "Workspace Sidebar",
				"link_to": title,
				"icon": "refresh",
				"hidden": 0,
			}
		)
		icon.set("roles", [{"role": role} for role in roles])
		icon.insert(ignore_permissions=True)
	# Place these beside the site's existing sales shortcuts inside ERPNext.
	icon = frappe.get_doc("Desktop Icon", title)
	if icon.link_type == "Workspace Sidebar" and icon.link_to == title:
		parent = frappe.db.get_value("Desktop Icon", {"label": "Selling"}, "parent_icon")
		if parent and not icon.parent_icon:
			icon.parent_icon = parent
			icon.save(ignore_permissions=True)
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
