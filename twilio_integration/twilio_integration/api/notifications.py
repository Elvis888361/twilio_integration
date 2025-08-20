import frappe
from twilio_integration.twilio_integration.api.whatsapp_documents import WhatsAppNotificationChannel

def get_notification_config():
    """Configure WhatsApp as a notification channel"""
    return {
        "WhatsApp": WhatsAppNotificationChannel
    }

@frappe.whitelist()
def send_whatsapp_notification(recipients, subject, message, reference_doctype=None, reference_name=None):
    """Send WhatsApp notification"""
    try:
        channel = WhatsAppNotificationChannel()
        
        # Ensure recipients is a list
        if isinstance(recipients, str):
            recipients = [recipients]
        
        results = channel.send(recipients, subject, message)
        
        # Log notification
        for result in results:
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": subject,
                "email_content": message,
                "for_user": result["recipient"],
                "type": "WhatsApp",
                "document_type": reference_doctype,
                "document_name": reference_name,
                "status": "Sent" if result["success"] else "Error"
            }).insert(ignore_permissions=True)
        
        return results
        
    except Exception as e:
        frappe.log_error(f"WhatsApp notification failed: {str(e)}")
        return []