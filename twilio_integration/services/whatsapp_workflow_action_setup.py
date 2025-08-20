import frappe
import json

def create_whatsapp_workflow_action_doctype():
    doc_json = {
        "doctype": "DocType",
        "name": "WhatsApp Workflow Action",
        "module": "Twilio Integration",
        "custom": 0,
        "istable": 0,
        "is_submittable": 0,
        "autoname": "naming_series:",
        "naming_rule": "By \"Naming Series\" field",
        "editable_grid": 1,
        "track_changes": 1,
        "title_field": "reference_name",
        "sort_field": "modified",
        "sort_order": "DESC",
        "fields": [
            {
                "fieldname": "naming_series",
                "fieldtype": "Select",
                "label": "Series",
                "options": "WFA-.YYYY.-",
                "reqd": 1
            },
            {
                "fieldname": "workflow_name",
                "fieldtype": "Link",
                "label": "Workflow",
                "options": "Workflow",
                "reqd": 1
            },
            {
                "fieldname": "reference_doctype",
                "fieldtype": "Link",
                "label": "Reference DocType",
                "options": "DocType",
                "reqd": 1
            },
            {
                "fieldname": "reference_name",
                "fieldtype": "Dynamic Link",
                "label": "Reference Name",
                "options": "reference_doctype",
                "reqd": 1
            },
            {
                "fieldname": "recipient_number",
                "fieldtype": "Data",
                "label": "WhatsApp Number",
                "reqd": 1
            },
            {
                "fieldname": "message_id",
                "fieldtype": "Data",
                "label": "WhatsApp Message ID",
                "read_only": 1
            },
            {
                "fieldname": "status",
                "fieldtype": "Select",
                "label": "Status",
                "options": "Pending\nApproved\nRejected\nExpired",
                "default": "Pending"
            },
            {
                "fieldname": "action_taken_by",
                "fieldtype": "Data",
                "label": "Action Taken By",
                "read_only": 1
            },
            {
                "fieldname": "action_taken_on",
                "fieldtype": "Datetime",
                "label": "Action Taken On",
                "read_only": 1
            },
            {
                "fieldname": "expires_on",
                "fieldtype": "Datetime",
                "label": "Expires On"
            }
        ],
        "permissions": [
            {
                "role": "System Manager",
                "read": 1,
                "write": 1,
                "create": 1,
                "delete": 1,
                "email": 1,
                "print": 1,
                "export": 1,
                "report": 1,
                "share": 1
            }
        ]
    }

    if not frappe.db.exists("DocType", "WhatsApp Workflow Action"):
        doc = frappe.get_doc(doc_json)
        doc.insert()
        frappe.db.commit()
        frappe.msgprint("✅ 'WhatsApp Workflow Action' DocType created.")
    else:
        frappe.msgprint("ℹ️ DocType already exists.")
