# simple_whatsapp_approval.py - SIMPLE WORKING SOLUTION
import frappe
from twilio.rest import Client
import hashlib

# Your credentials
STATIC_TWILIO_SID = "AC7b3d98150c02344e32fa5550a488aeda"
STATIC_TWILIO_TOKEN = "aa40c5f5460634a165829d823fa477a8"
STATIC_WHATSAPP_FROM = "+256770787451"

def send_approval_message(doc, method=None):
    """Main function called by ERPNext hooks"""
    try:
        if doc.doctype != "Sales Order":
            return
            
        phone = getattr(doc, 'custom_phone', None)
        if not phone:
            return
            
        # Generate token
        token = hashlib.md5(f"{doc.name}_{doc.creation}".encode()).hexdigest()[:6].upper()
        frappe.db.set_value("Sales Order", doc.name, "custom_approval_token", token)
        frappe.db.commit()
        
        # Send simple WhatsApp message with clear options
        send_simple_approval_message(phone, doc, token)
        
    except Exception as e:
        frappe.log_error(f"Error: {str(e)}", "Approval Error")

def send_simple_approval_message(phone, doc, token):
    """Send simple WhatsApp message with clear approval options"""
    try:
        if not phone.startswith('+'):
            phone = '+' + phone
            
        client = Client(STATIC_TWILIO_SID, STATIC_TWILIO_TOKEN)
        
        # Create simple, clear message
        message_text = f"""🔔 Sales Order Approval Required

📋 SO: {doc.name}
👤 Customer: {doc.customer}
💰 Amount: {doc.currency} {doc.grand_total:,.2f}
📅 Date: {doc.transaction_date}

Please reply with one of these:

✅ APPROVE {token}
❌ REJECT {token}

Just copy and send one of the options above."""
        
        # Send the message
        message = client.messages.create(
            body=message_text,
            from_=f"whatsapp:{STATIC_WHATSAPP_FROM}",
            to=f"whatsapp:{phone}"
        )
        
        frappe.log_error(f"Approval message sent - SID: {message.sid}, Token: {token}", "Message Sent")
        return message.sid
        
    except Exception as e:
        frappe.log_error(f"Send error: {str(e)}", "Send Error")
        raise e

@frappe.whitelist(allow_guest=True)
def handle_whatsapp_webhook():
    """Handle incoming WhatsApp responses"""
    try:
        # Get the message content
        message_body = frappe.form_dict.get('Body', '').upper().strip()
        from_number = frappe.form_dict.get('From', '').replace('whatsapp:', '').replace('+', '')
        
        # Log for debugging
        frappe.log_error(f"Received message: '{message_body}' from: {from_number}", "Webhook Received")
        frappe.log_error(f"Full webhook data: {dict(frappe.form_dict)}", "Full Webhook Data")
        
        # Process the message
        if message_body.startswith('APPROVE '):
            token = message_body.replace('APPROVE ', '').strip()
            process_approval(token, 'approve', from_number)
        elif message_body.startswith('REJECT '):
            token = message_body.replace('REJECT ', '').strip()
            process_approval(token, 'reject', from_number)
        else:
            # Send help message if they send something else
            if message_body and from_number:
                send_simple_message(from_number, "Please reply with 'APPROVE [TOKEN]' or 'REJECT [TOKEN]' to respond to approval requests.")
        
        return "OK"
        
    except Exception as e:
        frappe.log_error(f"Webhook error: {str(e)}", "Webhook Error")
        return "Error"

def process_approval(token, action, from_number):
    """Process the approval/rejection"""
    try:
        # Find sales order with this token
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={"custom_approval_token": token, "docstatus": 0},
            fields=["name", "customer", "grand_total", "currency", "workflow_state"]
        )
        
        if not sales_orders:
            send_simple_message(from_number, f"❌ Invalid or expired token: {token}")
            frappe.log_error(f"Invalid token: {token} from {from_number}", "Invalid Token")
            return
        
        so = sales_orders[0]
        doc = frappe.get_doc("Sales Order", so.name)
        
        # Process the action
        if action == 'approve':
            # Submit the document (approve it)
            if doc.docstatus == 0:  # Only if it's still draft
                doc.submit()
                confirmation_msg = f"✅ APPROVED!\n\nSales Order: {doc.name}\nCustomer: {doc.customer}\nAmount: {doc.currency} {doc.grand_total:,.2f}\n\n🎉 Order has been approved and submitted!"
                send_simple_message(from_number, confirmation_msg)
                frappe.log_error(f"APPROVED: {doc.name} by {from_number}", "Order Approved")
            else:
                send_simple_message(from_number, f"Order {doc.name} has already been processed.")
                
        elif action == 'reject':
            # Cancel the document (reject it)
            if doc.docstatus == 0:  # Only if it's still draft
                doc.cancel()
                confirmation_msg = f"❌ REJECTED!\n\nSales Order: {doc.name}\nCustomer: {doc.customer}\nAmount: {doc.currency} {doc.grand_total:,.2f}\n\nOrder has been rejected and cancelled."
                send_simple_message(from_number, confirmation_msg)
                frappe.log_error(f"REJECTED: {doc.name} by {from_number}", "Order Rejected")
            else:
                send_simple_message(from_number, f"Order {doc.name} has already been processed.")
        
        # Clear the token after processing
        if doc.docstatus != 0:  # Only clear if actually processed
            frappe.db.set_value("Sales Order", doc.name, "custom_approval_token", "")
            frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Processing error for token {token}: {str(e)}", "Processing Error")
        send_simple_message(from_number, f"❌ Error processing {action}. Please try again or contact support.")

def send_simple_message(phone, message):
    """Send simple WhatsApp message"""
    try:
        if not phone.startswith('+'):
            phone = '+' + phone
            
        client = Client(STATIC_TWILIO_SID, STATIC_TWILIO_TOKEN)
        
        response = client.messages.create(
            body=message,
            from_=f"whatsapp:{STATIC_WHATSAPP_FROM}",
            to=f"whatsapp:{phone}"
        )
        
        frappe.log_error(f"Message sent - SID: {response.sid}", "Message Sent")
        
    except Exception as e:
        frappe.log_error(f"Failed to send message: {str(e)}", "Send Failed")

@frappe.whitelist()
def test_approval_system(phone_number, sales_order_name):
    """Test the approval system"""
    try:
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
            
        doc = frappe.get_doc("Sales Order", sales_order_name)
        send_approval_message(doc)
        
        return {
            "status": "success",
            "message": f"Approval message sent to {phone_number}",
            "so_name": doc.name,
            "customer": doc.customer,
            "amount": f"{doc.currency} {doc.grand_total:,.2f}",
            "note": "Check your WhatsApp for the approval message. Reply with the provided APPROVE or REJECT commands."
        }
        
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Test failed: {str(e)}"
        }

@frappe.whitelist()
def check_webhook_setup():
    """Check if webhook is properly configured"""
    return {
        "webhook_url": "Set this in Twilio Console: https://your-domain.com/api/method/twilio_integration.services.simple_whatsapp_approval.handle_whatsapp_webhook",
        "current_form_dict": dict(frappe.form_dict) if frappe.form_dict else {},
        "note": "Make sure to set the webhook URL in your Twilio WhatsApp sandbox settings"
    }