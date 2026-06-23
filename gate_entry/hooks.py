app_name = "gate_entry"
app_title = "Gate Entry"
app_publisher = "Gurudatt Kulkarni"
app_description = "An erpnext security gate module for recording material and people movement"
app_email = "connect@gurudatt.in"
app_license = "mit"

# Apps
# ------------------

# Gate Entry requires ERPNext as it adds custom fields to ERPNext doctypes
required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "gate_entry",
# 		"logo": "/assets/gate_entry/logo.png",
# 		"title": "Gate Entry",
# 		"route": "/gate_entry",
# 		"has_permission": "gate_entry.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/gate_entry/css/gate_pass.css"
# app_include_js = "/assets/gate_entry/js/gate_entry.js"

# include js, css files in header of web template
# web_include_css = "/assets/gate_entry/css/gate_entry.css"
# web_include_js = "/assets/gate_entry/js/gate_entry.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "gate_entry/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Gate Pass": "public/js/gate_pass_custom_ui.js",
	"Stock Entry": "public/js/stock_entry_external_transfer.js",
}


# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "gate_entry/public/icons.svg"

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

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "gate_entry.utils.jinja_methods",
# 	"filters": "gate_entry.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "gate_entry.install.before_install"
after_install = "gate_entry.setup.install.after_install"
after_migrate = "gate_entry.setup.install.after_migrate"

# Uninstallation
# ------------

before_uninstall = "gate_entry.setup.uninstall.before_uninstall"
after_uninstall = "gate_entry.setup.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "gate_entry.utils.before_app_install"
# after_app_install = "gate_entry.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "gate_entry.utils.before_app_uninstall"
# after_app_uninstall = "gate_entry.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "gate_entry.notifications.get_notification_config"

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

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events
# These handlers clean up Gate Pass references when receipts are deleted/cancelled
doc_events = {
	"Purchase Receipt": {
		"on_submit": "gate_entry.gate_entry.doctype.gate_pass.gate_pass.on_purchase_receipt_submit",
		"on_trash": "gate_entry.gate_entry.doctype.gate_pass.gate_pass.on_purchase_receipt_trash",
		"on_cancel": "gate_entry.gate_entry.doctype.gate_pass.gate_pass.on_purchase_receipt_cancel",
	},
	"Subcontracting Receipt": {
		"on_trash": "gate_entry.gate_entry.doctype.gate_pass.gate_pass.on_subcontracting_receipt_trash",
		"on_cancel": "gate_entry.gate_entry.doctype.gate_pass.gate_pass.on_subcontracting_receipt_cancel",
	},
	"Stock Entry": {
		"on_submit": "gate_entry.gate_entry.doctype.gate_pass.gate_pass.on_stock_entry_submit",
		"on_trash": "gate_entry.gate_entry.doctype.gate_pass.gate_pass.on_stock_entry_trash",
		"on_cancel": "gate_entry.gate_entry.doctype.gate_pass.gate_pass.on_stock_entry_cancel",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"gate_entry.tasks.all"
# 	],
# 	"daily": [
# 		"gate_entry.tasks.daily"
# 	],
# 	"hourly": [
# 		"gate_entry.tasks.hourly"
# 	],
# 	"weekly": [
# 		"gate_entry.tasks.weekly"
# 	],
# 	"monthly": [
# 		"gate_entry.tasks.monthly"
# 	],
# }

# Testing
# -------

before_tests = "gate_entry.tests.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "gate_entry.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "gate_entry.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------
# Allow Purchase Receipts and Subcontracting Receipts to be deleted
# even if they have a link to Gate Pass
ignore_links_on_delete = ["Gate Pass"]

# Document Links
# -----------------------------------------------------------
# Define connections between doctypes that will appear in the Connections section
document_links = {
	"Gate Pass": [
		{"link_doctype": "Purchase Receipt", "link_fieldname": "gate_pass"},
		{"link_doctype": "Subcontracting Receipt", "link_fieldname": "gate_pass"},
		{"link_doctype": "Stock Entry", "link_fieldname": "gate_pass"},
	],
	"Purchase Receipt": [
		{"link_doctype": "Gate Pass", "link_fieldname": "gate_pass"},
	],
	"Subcontracting Receipt": [
		{"link_doctype": "Gate Pass", "link_fieldname": "subcontracting_receipt"},
	],
	"Stock Entry": [
		{"link_doctype": "Gate Pass", "link_fieldname": "stock_entry"},
	],
}

# Request Events
# ----------------
# before_request = ["gate_entry.utils.before_request"]
# after_request = ["gate_entry.utils.after_request"]

# Job Events
# ----------
# before_job = ["gate_entry.utils.before_job"]
# after_job = ["gate_entry.utils.after_job"]

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
# 	"gate_entry.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
