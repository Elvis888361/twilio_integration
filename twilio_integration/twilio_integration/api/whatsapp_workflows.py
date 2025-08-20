import frappe
from frappe import _
import json
from twilio.rest import Client
from twilio_integration.twilio_integration.doctype.twilio_settings.twilio_settings import get_twilio_credentials

@frappe.whitelist(allow_guest=True)
def handle_workflow_webhook():
    """Handle incoming WhatsApp workflow responses"""
    try:
        data = json.loads(frappe.request.data)
        
        # Extract message details
        message_body = data.get('Body', '')
        from_number = data.get('From', '').replace('whatsapp:', '')
        message_sid = data.get('MessageSid', '')
        
        # Check if it's an interactive message response
        if 'ButtonPayload' in data:
            payload_data = json.loads(data['ButtonPayload'])
            action_id = payload_data.get('action_id')
            action_type = payload_data.get('action_type')
            
            # Process the workflow action
            workflow_action = frappe.get_doc('WhatsApp Workflow Action', action_id)
            result = workflow_action.process_action(action_type, from_number)
            
            # Send confirmation message
            send_confirmation_message(from_number, result['message'])
            
        return "OK"
        
    except Exception as e:
        frappe.log_error(f"Workflow webhook error: {str(e)}")
        return "ERROR"

def send_workflow_action_message(workflow_action_doc):
    """Send interactive WhatsApp message with Approve/Reject buttons"""
    try:
        account_sid, auth_token, twilio_number = get_twilio_credentials()
        client = Client(account_sid, auth_token)
        
        # Get document details
        doc = frappe.get_doc(workflow_action_doc.reference_doctype, workflow_action_doc.reference_name)
        
        message_body = f"""
🔔 *Workflow Action Required*

Document: {workflow_action_doc.reference_doctype}
ID: {workflow_action_doc.reference_name}
Current Status: {doc.workflow_state if hasattr(doc, 'workflow_state') else 'Pending'}

Please choose an action:
        """
        
        # Create interactive buttons
        buttons_payload = {
            "type": "button",
            "body": {
                "text": message_body.strip()
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": json.dumps({
                                "action_id": workflow_action_doc.name,
                                "action_type": "approve"
                            }),
                            "title": "✅ Approve"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": json.dumps({
                                "action_id": workflow_action_doc.name,
                                "action_type": "reject"
                            }),
                            "title": "❌ Reject"
                        }
                    }
                ]
            }
        }
        
        message = client.messages.create(
            content_sid="HX...", # Use Twilio's interactive template
            content_variables=json.dumps(buttons_payload),
            from_=f'whatsapp:{twilio_number}',
            to=f'whatsapp:{workflow_action_doc.recipient_number}'
        )
        
        return message.sid
        
    except Exception as e:
        frappe.log_error(f"Failed to send workflow message: {str(e)}")
        return None

def send_confirmation_message(to_number, message):
    """Send confirmation message after action"""
    try:
        account_sid, auth_token, twilio_number = get_twilio_credentials()
        client = Client(account_sid, auth_token)
        
        client.messages.create(
            body=f"✅ {message}",
            from_=f'whatsapp:{twilio_number}',
            to=f'whatsapp:{to_number}'
        )
        
    except Exception as e:
        frappe.log_error(f"Failed to send confirmation: {str(e)}")

@frappe.whitelist()
def create_workflow_action(reference_doctype, reference_name, workflow_name, recipient_number):
    """Create a new workflow action request"""
    try:
        workflow_action = frappe.get_doc({
            "doctype": "WhatsApp Workflow Action",
            "workflow_name": workflow_name,
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "recipient_number": recipient_number
        }).insert()
        
        return {"success": True, "name": workflow_action.name}
        
    except Exception as e:
        frappe.log_error(f"Failed to create workflow action: {str(e)}")
        return {"success": False, "error": str(e)}
def check_workflow_state_change(doc, method):
    # Your logic here
    pass
