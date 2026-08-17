app_name = "otec_selling"
app_title = "OTEC Selling"
app_publisher = "OTEC"
app_description = "OTEC sales hierarchy, workflow, fulfillment, billing, collection, and workspace customizations"
app_email = "ljpmallari@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "otec_selling",
# 		"logo": "/assets/otec_selling/logo.png",
# 		"title": "OTEC Selling",
# 		"route": "/otec_selling",
# 		"has_permission": "otec_selling.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/otec_selling/css/otec_selling.css"
# app_include_js = "/assets/otec_selling/js/otec_selling.js"

# include js, css files in header of web template
# web_include_css = "/assets/otec_selling/css/otec_selling.css"
# web_include_js = "/assets/otec_selling/js/otec_selling.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "otec_selling/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Container Receiving": "public/js/container_receiving.js",
    "Container Landed Cost": "public/js/container_landed_cost.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "otec_selling/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "otec_selling.utils.jinja_methods",
# 	"filters": "otec_selling.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "otec_selling.install.before_install"
after_sync = "otec_selling.patches.v0_0.configure_purchasing_lifecycle.execute"

# Uninstallation
# ------------

# before_uninstall = "otec_selling.uninstall.before_uninstall"
# after_uninstall = "otec_selling.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "otec_selling.utils.before_app_install"
# after_app_install = "otec_selling.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "otec_selling.utils.before_app_uninstall"
# after_app_uninstall = "otec_selling.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "otec_selling.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "otec_selling.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Purchase Order": {
        "validate": "otec_selling.purchasing_lifecycle.validate_purchase_order",
        "before_submit": "otec_selling.purchasing_lifecycle.before_submit_purchase_order",
    },
    "Purchase Receipt": {
        "validate": "otec_selling.purchasing_lifecycle.validate_purchase_receipt",
        "before_submit": "otec_selling.purchasing_lifecycle.before_submit_purchase_receipt",
        "after_submit": "otec_selling.purchasing_lifecycle.sync_container_receiving_from_receipt",
        "after_cancel": "otec_selling.purchasing_lifecycle.sync_container_receiving_from_receipt",
    },
    "Landed Cost Voucher": {
        "validate": "otec_selling.purchasing_lifecycle.validate_landed_cost_voucher",
        "before_submit": "otec_selling.purchasing_lifecycle.before_submit_landed_cost_voucher",
        "after_submit": "otec_selling.purchasing_lifecycle.after_submit_landed_cost_voucher",
        "after_cancel": "otec_selling.purchasing_lifecycle.after_cancel_landed_cost_voucher",
    },
    "Container Landed Cost": {
        "before_submit": "otec_selling.purchasing_lifecycle.before_submit_container_landed_cost",
        "before_cancel": "otec_selling.purchasing_lifecycle.before_cancel_container_landed_cost",
    },
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"otec_selling.tasks.all"
# 	],
# 	"daily": [
# 		"otec_selling.tasks.daily"
# 	],
# 	"hourly": [
# 		"otec_selling.tasks.hourly"
# 	],
# 	"weekly": [
# 		"otec_selling.tasks.weekly"
# 	],
# 	"monthly": [
# 		"otec_selling.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "otec_selling.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "otec_selling.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "otec_selling.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "otec_selling.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["otec_selling.utils.before_request"]
# after_request = ["otec_selling.utils.after_request"]

# Job Events
# ----------
# before_job = ["otec_selling.utils.before_job"]
# after_job = ["otec_selling.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"otec_selling.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


# Phase 6 portability manifest. Operational records (users, hierarchy rows,
# transactions, serial allocations, and company/branch master data) are
# intentionally excluded.
required_apps = ["erpnext"]

_selling_doctypes = [
    "Quotation", "Quotation Item", "Sales Order", "Sales Order Item",
    "Pick List", "Pick List Item", "Delivery Note", "Delivery Note Item",
    "Sales Invoice", "Sales Invoice Item", "Payment Entry", "Customer",
    "Branch", "Warehouse", "User",
]

_custom_doctypes = [
    "Branch Markup Setting", "Container Landed Cost",
    "Container Landed Cost Item", "Container Landed Cost Receipt",
    "Container Receiving", "Container Receiving Item",
    "Container Receiving Warehouse Mapping", "DR Paper Batch",
    "DR Paper Serial Log", "Employment Contract", "OTEC Quotation",
    "PO Box Detail", "Sales Access Hierarchy", "Sales Hierarchy Branch Access",
    "Sales Hierarchy Company Access", "Sales Hierarchy Team Access",
    "Sales Team Group", "Sample Issuance", "Sample Issuance Item",
]

_purchasing_doctypes = [
    "Company", "Purchase Order", "Purchase Order Item", "Purchase Receipt",
    "Purchase Receipt Item", "Landed Cost Voucher", "Landed Cost Item",
]

_hr_expense_doctypes = [
    "Employee Advance", "Expense Claim", "Expense Claim Detail",
    "Expense Claim Type",
]

_fixture_doctypes = _selling_doctypes + _purchasing_doctypes + _custom_doctypes

fixtures = [
    {"dt": "DocType", "filters": [["custom", "=", 1]]},
    {"dt": "Custom Field", "filters": [["dt", "in", _fixture_doctypes]]},
    {"dt": "Custom Field", "prefix": "hr_expense", "filters": [["dt", "in", _hr_expense_doctypes]]},
    {"dt": "Property Setter", "filters": [
        ["doc_type", "in", _fixture_doctypes],
        ["property", "!=", "title_field"],
    ]},
    {"dt": "Property Setter", "prefix": "hr_expense", "filters": [
        ["doc_type", "in", _hr_expense_doctypes],
        ["property", "!=", "title_field"],
    ]},
    {"dt": "Custom DocPerm", "filters": [["parent", "in", _fixture_doctypes]]},
    {"dt": "Client Script", "filters": [["dt", "in", _fixture_doctypes]]},
    {"dt": "Server Script", "filters": [["reference_doctype", "in", _fixture_doctypes]]},
    {"dt": "Workflow", "filters": [["document_type", "in", _selling_doctypes]]},
    {"dt": "Workflow", "prefix": "hr_expense", "filters": [["document_type", "=", "Expense Claim"]]},
    "Workflow State",
    "Workflow Action Master",
    {"dt": "Workspace", "filters": [["module", "=", "Selling"]]},
    {"dt": "Number Card", "filters": [["module", "=", "Selling"], ["is_standard", "=", 0]]},
    {"dt": "Dashboard Chart", "filters": [["module", "=", "Selling"], ["is_standard", "=", 0]]},
    {"dt": "Report", "filters": [["ref_doctype", "in", _fixture_doctypes], ["is_standard", "=", "No"]]},
    {"dt": "Report", "prefix": "hr_expense", "filters": [["ref_doctype", "=", "Expense Claim"], ["is_standard", "=", "No"]]},
    {"dt": "Print Format", "filters": [["doc_type", "in", _selling_doctypes], ["custom_format", "=", 1]]},
    {"dt": "Role", "filters": [["name", "in", [
        "Business Owner", "General Manager", "Senior Operations Manager",
        "Sales Master Manager", "Sales Supervisor", "Sales Team Leader",
        "Sales User", "Quotation Creator",
    ]]]},
]
