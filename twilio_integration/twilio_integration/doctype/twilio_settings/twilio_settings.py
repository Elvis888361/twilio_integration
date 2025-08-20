# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils.password import get_decrypted_password

from six import string_types
import re
from json import loads, dumps
from random import randrange

from twilio.rest import Client
from ...utils import get_public_url

class TwilioSettings(Document):
    friendly_resource_name = "ERPNext"
    def validate(self):
        self.validate_twilio_account()
        if self.enable_workflow_actions or self.enable_customer_orders:
            webhook_urls = setup_whatsapp_webhooks()
            self.workflow_webhook_url = webhook_urls["workflow_webhook"]
            self.order_webhook_url = webhook_urls["order_webhook"]
        
        # Validate WhatsApp number format
        if self.whatsapp_no and not self.whatsapp_no.startswith('+'):
            frappe.throw(_("WhatsApp number must include country code (e.g., +1234567890)"))
    

    def on_update(self):
        # Single doctype records are created in DB at time of installation and those field values are set as null.
        # This condition make sure that we handle null.
        if not self.account_sid:
            return

        twilio = Client(self.account_sid, self.get_password("auth_token"))
        self.set_api_credentials(twilio)
        self.set_application_credentials(twilio)
        self.reload()
        if self.enable_workflow_actions or self.enable_customer_orders:
            self.setup_twilio_webhooks()

    def validate_twilio_account(self):
        try:
            twilio = Client(self.account_sid, self.get_password("auth_token"))
            twilio.api.accounts(self.account_sid).fetch()
            return twilio
        except Exception:
            frappe.throw(_("Invalid Account SID or Auth Token."))

    def set_api_credentials(self, twilio):
        """Generate Twilio API credentials if not exist and update them.
        """
        if self.api_key and self.api_secret:
            return
        new_key = self.create_api_key(twilio)
        self.api_key = new_key.sid
        self.api_secret = new_key.secret
        frappe.db.set_value('Twilio Settings', 'Twilio Settings', {
            'api_key': self.api_key,
            'api_secret': self.api_secret
        })

    def set_application_credentials(self, twilio):
        """Generate TwiML app credentials if not exist and update them.
        """
        credentials = self.get_application(twilio) or self.create_application(twilio)
        self.twiml_sid = credentials.sid
        frappe.db.set_value('Twilio Settings', 'Twilio Settings', 'twiml_sid', self.twiml_sid)

    def create_api_key(self, twilio):
        """Create API keys in twilio account.
        """
        try:
            return twilio.new_keys.create(friendly_name=self.friendly_resource_name)
        except Exception:
            frappe.log_error(title=_("Twilio API credential creation error."))
            frappe.throw(_("Twilio API credential creation error."))

    def get_twilio_voice_url(self):
        url_path = "/api/method/twilio_integration.twilio_integration.api.voice"
        return get_public_url(url_path)

    def get_application(self, twilio, friendly_name=None):
        """Get TwiML App from twilio account if exists.
        """
        friendly_name = friendly_name or self.friendly_resource_name
        applications = twilio.applications.list(friendly_name)
        return applications and applications[0]

    def create_application(self, twilio, friendly_name=None):
        """Create TwilML App in twilio account.
        """
        friendly_name = friendly_name or self.friendly_resource_name
        application = twilio.applications.create(
                        voice_method='POST',
                        voice_url=self.get_twilio_voice_url(),
                        friendly_name=friendly_name
                    )
        return application
    def setup_twilio_webhooks(self):
        """Configure webhooks in Twilio (requires manual setup)"""
        frappe.msgprint(_("""
        <strong>WhatsApp Webhook Configuration Required</strong><br><br>
        Please configure the following webhooks in your Twilio Console:<br><br>
        
        <strong>For Workflow Actions:</strong><br>
        URL: {0}<br><br>
        
        <strong>For Customer Orders:</strong><br>
        URL: {1}<br><br>
        
        <em>Go to Twilio Console > WhatsApp > Senders > [Your Number] > Webhook Configuration</em>
        """).format(self.workflow_webhook_url, self.order_webhook_url))
    
    @frappe.whitelist()
    def test_connection(self):
        """Test Twilio connection from the document"""
        return test_whatsapp_connection()
    
    def get_whatsapp_config(self):
        """Get WhatsApp configuration for whatsapp_no this settings"""
        return {
            "whatsapp_no": self.whatsapp_no,
            "workflow_actions_enabled": self.enable_workflow_actions,
            "customer_orders_enabled": self.enable_customer_orders,
            "session_timeout": self.session_timeout_hours or 2
        }
    
    def send_test_message(self, to_number, message="Test message from ERPNext"):
        """Send test WhatsApp message"""
        try:
            from twilio.rest import Client
            
            client = Client(self.account_sid, self.auth_token)
            
            message = client.messages.create(
                body=message,
                from_=f'whatsapp:{self.whatsapp_no}',
                to=f'whatsapp:{to_number}'
            )
            
            return {"success": True, "message_sid": message.sid}
            
        except Exception as e:
            frappe.log_error(f"Test message failed: {str(e)}")
            return {"success": False, "error": str(e)}


def setup_whatsapp_webhooks():
    settings = frappe.get_single('Twilio Settings')
    
    if not settings.account_sid or not settings.auth_token:
        frappe.throw(_("Twilio credentials not configured"))
    
    base_url = frappe.utils.get_url()
    
    # WhatsApp webhook URLs
    workflow_webhook_url = f"{base_url}/api/method/twilio_integration.api.whatsapp_workflows.handle_workflow_webhook"
    order_webhook_url = f"{base_url}/api/method/twilio_integration.api.whatsapp_orders.handle_order_webhook"
    
    return {
        "workflow_webhook": workflow_webhook_url,
        "order_webhook": order_webhook_url
    }

@frappe.whitelist()
def get_webhook_urls():
    """Get webhook URLs for WhatsApp configuration"""
    return setup_whatsapp_webhooks()

def get_twilio_credentials():
    """Get Twilio credentials from settings"""
    settings = frappe.get_single('Twilio Settings')
    
    if not settings.account_sid or not settings.auth_token:
        frappe.throw(_("Twilio credentials not configured"))
    
    return settings.account_sid, settings.auth_token, settings.whatsapp_no

def is_whatsapp_enabled(feature):
    """Check if WhatsApp feature is enabled"""
    settings = frappe.get_single('Twilio Settings')
    
    if feature == "workflow_actions":
        return settings.enable_workflow_actions
    elif feature == "customer_orders":
        return settings.enable_customer_orders
    
    return False

@frappe.whitelist()
def test_whatsapp_connection():
    """Test WhatsApp connection"""
    try:
        from twilio.rest import Client
        account_sid, auth_token, whatsapp_no = get_twilio_credentials()
        
        client = Client(account_sid, auth_token)
        
        # Get account info to test connection
        account = client.api.accounts(account_sid).fetch()
        
        return {
            "success": True,
            "message": f"Connected successfully. Account: {account.friendly_name}",
            "status": account.status
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection failed: {str(e)}"
        }

@frappe.whitelist()
def cleanup_expired_sessions():
    """Clean up expired WhatsApp sessions"""
    try:
        # Mark expired workflow actions
        frappe.db.sql("""
            UPDATE `tabWhatsApp Workflow Action` 
            SET status = 'Expired' 
            WHERE status = 'Pending' 
            AND expires_on < NOW()
        """)
        
        # Mark expired order sessions  
        frappe.db.sql("""
            UPDATE `tabWhatsApp Order Session`
            SET status = 'Abandoned'
            WHERE status = 'Active'
            AND expires_on < NOW()
        """)
        
        frappe.db.commit()
        
        return {"success": True, "message": "Expired sessions cleaned up"}
        
    except Exception as e:
        frappe.log_error(f"Failed to cleanup sessions: {str(e)}")
        return {"success": False, "error": str(e)}