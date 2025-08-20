# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "whatsapp_erpnext"
app_title = "Twilio Integration"
app_publisher = "Frappe"
app_description = "Custom Frappe Application for Twilio Integration"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "developers@frappe.io"
app_license = "MIT"
fixtures = [{"dt": "Custom Field", "filters": [
		[
			"name", "in", [
				"Notification-twilio_number", "Voice Call Settings-twilio_number"
			]
		]
	]}
, "Property Setter"]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/twilio_integration/css/twilio_call_handler.css"
app_include_js = [
    "twilio_integration/public/js/notification_channels.js",
    "/assets/twilio_integration/js/twilio_call_handler.js"
]

# include js, css files in header of web template
# web_include_css = "/assets/twilio_integration/css/twilio_integration.css"
# web_include_js = "/assets/twilio_integration/js/twilio_integration.js"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}
doctype_js = {
	"Notification" : "public/js/Notification.js",
	"Voice Call Settings": "public/js/voice_call_settings.js"
}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

notification_config = "twilio_integration.twilio_integration.api.notifications.get_notification_config"

# Custom notification channel
notification_channels = ["WhatsApp"]

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "twilio_integration.install.before_install"
# after_install = "twilio_integration.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "twilio_integration.notifications.get_notification_config"

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


# WhatsApp Webhook Routes
# -----------------------
website_route_rules = [
	{
		"from_route": "/api/method/twilio_integration.api.whatsapp_workflows.handle_workflow_webhook", 
		"to_route": "twilio_integration.api.whatsapp_workflows.handle_workflow_webhook"
	},
	{
		"from_route": "/api/method/twilio_integration.api.whatsapp_orders.handle_order_webhook", 
		"to_route": "twilio_integration.api.whatsapp_orders.handle_order_webhook"
	},
	{
        "from_route": "/api/whatsapp/chatbot",
        "to_route": "twilio_integration.services.whatsapp_order_chatbot.handle_whatsapp_chatbot"
    }
]

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "*": {
        "on_update": "twilio_integration.twilio_integration.api.whatsapp_documents.add_whatsapp_button_to_form"
    },
    "Sales Order": {
        "before_save": "twilio_integration.services.simple_whatsapp_approval.send_approval_message",
        "on_submit": "twilio_integration.services.whatsapp_order_chatbot.on_sales_order_submit"

    },
    "WhatsApp Order Session": {
        "validate": "twilio_integration.services.whatsapp_order_chatbot.validate_session",
        "on_update": "twilio_integration.services.whatsapp_order_chatbot.on_session_update"
    },
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
        "twilio_integration.services.whatsapp_order_chatbot.cleanup_old_sessions"
    ],
	"hourly": [
		"twilio_integration.twilio_integration.doctype.twilio_settings.twilio_settings.cleanup_expired_sessions",
		"twilio_integration.services.whatsapp_order_chatbot.cleanup_inactive_sessions"
	]
}

# Testing
# -------

# before_tests = "twilio_integration.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "twilio_integration.event.get_events"
# }
#
whitelisted = [
    "twilio_integration.services.simple_whatsapp_approval.handle_whatsapp_response"
]
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "twilio_integration.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

override_doctype_class = {
	"Notification": "twilio_integration.overrides.notification.SendNotification",
	"frappe.integrations.whatsapp.send_whatsapp_message": "twilio_integration.services.whatsapp_order_chatbot.send_whatsapp_message"
}

# WhatsApp Integration Overrides
# -------------------------------
override_whitelisted_methods = {
	"frappe.desk.form.utils.add_comment": "twilio_integration.api.whatsapp_workflows.handle_comment_workflow_trigger"
}

# boot
# ----------
boot_session = "twilio_integration.boot.boot_session"

custom_fields = {
	"Customer": [
		{
			"fieldname": "whatsapp_number",
			"fieldtype": "Data",
			"label": "WhatsApp Number",
			"insert_after": "mobile_no"
		},
		{
			"fieldname": "enable_whatsapp_orders",
			"fieldtype": "Check",
			"label": "Enable WhatsApp Orders",
			"default": 0,
			"insert_after": "whatsapp_number"
		}
	],
	"Sales Order": [
		{
			"fieldname": "whatsapp_order_session",
			"fieldtype": "Link",
			"label": "WhatsApp Order Session",
			"options": "WhatsApp Order Session",
			"read_only": 1,
			"insert_after": "customer"
		}
	],
	"Workflow": [
		{
			"fieldname": "enable_whatsapp_actions",
			"fieldtype": "Check",
			"label": "Enable WhatsApp Actions",
			"default": 0,
			"insert_after": "is_active"
		},
		{
			"fieldname": "whatsapp_approvers",
			"fieldtype": "Table",
			"label": "WhatsApp Approvers",
			"options": "WhatsApp Workflow Approver",
			"depends_on": "enable_whatsapp_actions",
			"insert_after": "enable_whatsapp_actions"
		}
	]
}


# Data Import/Export
# ------------------
# Data to be imported/exported
data_import_tool = {
	"allowed_file_types": ["csv", "xlsx"],
	"allowed_doctypes": ["WhatsApp Order Session", "WhatsApp Workflow Action"]
}

# Email Integration
# -----------------
# Send WhatsApp notifications for certain email events
email_hooks = {
	"on_send": "twilio_integration.twilio_integration.api.whatsapp_workflows.send_whatsapp_on_email"
}

# Jinja Environment
# -----------------
# Add custom functions to Jinja environment
jenv = {
	"methods": [
		"twilio_integration.twilio_integration.api.whatsapp_workflows.get_workflow_actions:get_workflow_actions",
		"twilio_integration.twilio_integration.api.whatsapp_orders.get_order_status:get_order_status",
		"twilio_integration.services.whatsapp_order_chatbot.get_order_status"
	]
}

# Report Hooks
# ------------
# Override standard reports
override_report_methods = {
	"Sales Analytics": "twilio_integration.reports.sales_analytics.get_whatsapp_sales_data"
}

# Background Jobs
# ---------------
# Enqueue background jobs for heavy operations
background_jobs = {
	"whatsapp_bulk_send": {
		"queue": "default",
		"timeout": 300
	}
}
