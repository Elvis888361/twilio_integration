# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now, add_days
import json


class WhatsAppWorkflowAction(Document):
    def before_insert(self):
        if not self.expires_on:
            self.expires_on = add_days(now(), 1)
    
    def after_insert(self):
        self.send_workflow_action_message()
    
    def send_workflow_action_message(self):
        """Send WhatsApp message with interactive buttons"""
        try:
            from twilio_integration.api.whatsapp_workflows import send_workflow_action_message
            message_id = send_workflow_action_message(self)
            if message_id:
                self.db_set('message_id', message_id)
        except Exception as e:
            frappe.log_error(f"Failed to send workflow action message: {str(e)}")
    
    def process_action(self, action, user_number):
        """Process the workflow action (Approve/Reject)"""
        if self.status != "Pending":
            return {"success": False, "message": "Action already processed"}
        
        if frappe.utils.now_datetime() > frappe.utils.get_datetime(self.expires_on):
            self.db_set('status', 'Expired')
            return {"success": False, "message": "Action has expired"}
        
        try:
            # Get the workflow document
            workflow_doc = frappe.get_doc(self.reference_doctype, self.reference_name)
            
            # Apply workflow action
            if action.lower() == 'approve':
                workflow_doc.run_method("approve")
                self.db_set('status', 'Approved')
            elif action.lower() == 'reject':
                workflow_doc.run_method("reject")
                self.db_set('status', 'Rejected')
            
            self.db_set('action_taken_by', user_number)
            self.db_set('action_taken_on', now())
            
            return {"success": True, "message": f"Document {action.lower()}d successfully"}
            
        except Exception as e:
            frappe.log_error(f"Workflow action failed: {str(e)}")
            return {"success": False, "message": "Failed to process action"}
