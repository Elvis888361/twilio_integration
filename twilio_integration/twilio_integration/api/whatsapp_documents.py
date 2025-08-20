import frappe
from frappe import _
import json
import os
import base64
from twilio.rest import Client
from twilio_integration.twilio_integration.doctype.twilio_settings.twilio_settings import get_twilio_credentials

@frappe.whitelist()
def send_document_via_whatsapp(reference_doctype, reference_name, recipients, message=None, print_format=None):
    """Send PDF document via WhatsApp to multiple recipients"""
    try:
        # Create WhatsApp Document Share record
        doc_share = frappe.get_doc({
            "doctype": "WhatsApp Document Share",
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "message": message or "",
            "recipients": recipients
        }).insert()
        
        # Generate PDF
        pdf_file = generate_pdf_for_document(reference_doctype, reference_name, print_format)
        doc_share.db_set('pdf_file', pdf_file)
        
        # Send to all recipients
        success_count = 0
        for recipient in doc_share.recipients:
            result = send_pdf_to_recipient(pdf_file, recipient, message, doc_share.name)
            if result['success']:
                success_count += 1
                recipient.db_set('delivery_status', 'Sent')
                recipient.db_set('message_id', result['message_id'])
                recipient.db_set('sent_on', frappe.utils.now())
            else:
                recipient.db_set('delivery_status', 'Failed')
                recipient.db_set('error_message', result['error'])
        
        # Update overall status
        if success_count == len(doc_share.recipients):
            doc_share.db_set('status', 'Sent')
        elif success_count > 0:
            doc_share.db_set('status', 'Partially Sent')
        else:
            doc_share.db_set('status', 'Failed')
        
        doc_share.db_set('sent_on', frappe.utils.now())
        
        return {
            "success": True,
            "message": f"Document sent to {success_count}/{len(doc_share.recipients)} recipients",
            "document_share": doc_share.name
        }
        
    except Exception as e:
        frappe.log_error(f"Failed to send document via WhatsApp: {str(e)}")
        return {"success": False, "error": str(e)}

def generate_pdf_for_document(doctype, name, print_format=None):
    """Generate PDF for the document"""
    try:
        from frappe.utils.pdf import get_pdf
        
        # Get the document
        doc = frappe.get_doc(doctype, name)
        
        # Use default print format if not specified
        if not print_format:
            print_format = frappe.db.get_value("Property Setter", 
                {"doc_type": doctype, "property": "default_print_format"}, "value")
            if not print_format:
                print_format = "Standard"
        
        # Generate HTML
        html = frappe.get_print(doctype, name, print_format)
        
        # Generate PDF
        pdf_content = get_pdf(html)
        
        # Save to file
        file_name = f"{doctype}_{name}_{frappe.utils.now()}.pdf".replace(" ", "_").replace(":", "-")
        file_path = frappe.utils.get_files_path(file_name)
        
        with open(file_path, 'wb') as f:
            f.write(pdf_content)
        
        # Create File document
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "file_url": f"/files/{file_name}",
            "is_private": 1
        }).insert()
        
        return file_doc.file_url
        
    except Exception as e:
        frappe.log_error(f"PDF generation failed: {str(e)}")
        raise

def send_pdf_to_recipient(pdf_file, recipient, message, doc_share_name):
    """Send PDF file to a single WhatsApp recipient"""
    try:
        account_sid, auth_token, twilio_number = get_twilio_credentials()
        client = Client(account_sid, auth_token)
        
        # Get file path
        file_path = frappe.utils.get_site_path() + pdf_file
        
        # Upload media to Twilio (for WhatsApp media messages)
        with open(file_path, 'rb') as f:
            pdf_content = f.read()
            
        # For WhatsApp, we need to upload the media first
        # Note: This requires Twilio's media upload endpoint
        media_url = upload_media_to_twilio(pdf_content, f"{recipient.recipient_name}_document.pdf")
        
        # Send message with media
        message_text = message or f"📄 Document: {recipient.recipient_name}"
        
        whatsapp_message = client.messages.create(
            body=message_text,
            media_url=[media_url],
            from_=f'whatsapp:{twilio_number}',
            to=f'whatsapp:{recipient.whatsapp_number}'
        )
        
        return {"success": True, "message_id": whatsapp_message.sid}
        
    except Exception as e:
        frappe.log_error(f"Failed to send PDF to {recipient.whatsapp_number}: {str(e)}")
        return {"success": False, "error": str(e)}

def upload_media_to_twilio(file_content, filename):
    """Upload media file to Twilio for WhatsApp"""
    try:
        # This is a simplified version - in practice, you'd need to:
        # 1. Upload to a publicly accessible URL (AWS S3, etc.)
        # 2. Return that URL for Twilio to access
        # For now, we'll use a placeholder approach
        
        # Save to public files temporarily
        import tempfile
        import shutil
        
        # Create temporary public file
        temp_filename = f"temp_whatsapp_{frappe.generate_hash()}.pdf"
        public_file_path = frappe.utils.get_site_path('public', 'files', temp_filename)
        
        with open(public_file_path, 'wb') as f:
            f.write(file_content)
        
        # Return public URL
        site_url = frappe.utils.get_url()
        return f"{site_url}/files/{temp_filename}"
        
    except Exception as e:
        frappe.log_error(f"Media upload failed: {str(e)}")
        raise

# WhatsApp Notification Channel Implementation
class WhatsAppNotificationChannel:
    """WhatsApp notification channel for ERPNext Notification system"""
    
    def send(self, recipients, subject, message, attachments=None):
        """Send notification via WhatsApp"""
        try:
            account_sid, auth_token, twilio_number = get_twilio_credentials()
            client = Client(account_sid, auth_token)
            
            results = []
            
            for recipient in recipients:
                try:
                    # Format message for WhatsApp
                    whatsapp_message = f"🔔 *{subject}*\n\n{message}"
                    
                    # Send message
                    msg = client.messages.create(
                        body=whatsapp_message,
                        from_=f'whatsapp:{twilio_number}',
                        to=f'whatsapp:{recipient}'
                    )
                    
                    results.append({
                        "recipient": recipient,
                        "success": True,
                        "message_id": msg.sid
                    })
                    
                except Exception as e:
                    results.append({
                        "recipient": recipient,
                        "success": False,
                        "error": str(e)
                    })
            
            return results
            
        except Exception as e:
            frappe.log_error(f"WhatsApp notification failed: {str(e)}")
            return []

# Custom button for documents
@frappe.whitelist()
def add_send_whatsapp_button():
    """Add 'Send via WhatsApp' button to documents"""
    return """
    frappe.ui.form.on('{{doctype}}', {
        refresh: function(frm) {
            if (frm.doc.docstatus === 1) {
                frm.add_custom_button(__('Send via WhatsApp'), function() {
                    frappe.call({
                        method: 'twilio_integration.api.whatsapp_documents.show_whatsapp_dialog',
                        args: {
                            doctype: frm.doc.doctype,
                            name: frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message) {
                                // Show dialog for recipient selection
                                show_whatsapp_recipients_dialog(frm, r.message);
                            }
                        }
                    });
                }, __('Share'));
            }
        }
    });
    
    function show_whatsapp_recipients_dialog(frm, data) {
        let dialog = new frappe.ui.Dialog({
            title: __('Send via WhatsApp'),
            fields: [
                {
                    fieldtype: 'Table',
                    fieldname: 'recipients',
                    label: 'Recipients',
                    fields: [
                        {
                            fieldtype: 'Data',
                            fieldname: 'recipient_name',
                            label: 'Name',
                            reqd: 1,
                            in_list_view: 1
                        },
                        {
                            fieldtype: 'Data',
                            fieldname: 'whatsapp_number',
                            label: 'WhatsApp Number',
                            reqd: 1,
                            in_list_view: 1
                        }
                    ]
                },
                {
                    fieldtype: 'Text',
                    fieldname: 'message',
                    label: 'Custom Message'
                },
                {
                    fieldtype: 'Link',
                    fieldname: 'print_format',
                    label: 'Print Format',
                    options: 'Print Format'
                }
            ],
            primary_action_label: __('Send'),
            primary_action: function(values) {
                if (!values.recipients || values.recipients.length === 0) {
                    frappe.msgprint(__('Please add at least one recipient'));
                    return;
                }
                
                frappe.call({
                    method: 'twilio_integration.api.whatsapp_documents.send_document_via_whatsapp',
                    args: {
                        reference_doctype: frm.doc.doctype,
                        reference_name: frm.doc.name,
                        recipients: values.recipients,
                        message: values.message,
                        print_format: values.print_format
                    },
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.msgprint(r.message.message);
                            dialog.hide();
                        } else {
                            frappe.msgprint(__('Failed to send document'));
                        }
                    }
                });
            }
        });
        
        dialog.show();
    }
    """

@frappe.whitelist()
def show_whatsapp_dialog(doctype, name):
    """Show WhatsApp sending dialog data"""
    # Get available print formats
    print_formats = frappe.get_all("Print Format", 
        filters={"doc_type": doctype}, 
        fields=["name", "print_format_type"])
    
    return {
        "print_formats": print_formats,
        "doctype": doctype,
        "name": name
    }

# Cleanup function for temporary files
@frappe.whitelist()
def cleanup_temp_whatsapp_files():
    """Clean up temporary WhatsApp media files"""
    try:
        import glob
        import os
        from frappe.utils import get_site_path
        
        # Clean files older than 24 hours
        temp_files = glob.glob(get_site_path('public', 'files', 'temp_whatsapp_*.pdf'))
        current_time = frappe.utils.now_datetime()
        
        for file_path in temp_files:
            try:
                file_time = frappe.utils.get_datetime(os.path.getmtime(file_path))
                if (current_time - file_time).total_seconds() > 86400:  # 24 hours
                    os.remove(file_path)
            except:
                pass
                
        return {"success": True, "message": "Temporary files cleaned up"}
        
    except Exception as e:
        frappe.log_error(f"Cleanup failed: {str(e)}")
        return {"success": False, "error": str(e)}

# Custom button for documents
@frappe.whitelist()
def add_whatsapp_button_to_form(doc,method):
    """Add 'Send via WhatsApp' button to documents"""
    return """
    frappe.ui.form.on('{{doctype}}', {
        refresh: function(frm) {
            if (frm.doc.docstatus === 1) {
                frm.add_custom_button(__('Send via WhatsApp'), function() {
                    frappe.call({
                        method: 'twilio_integration.api.whatsapp_documents.show_whatsapp_dialog',
                        args: {
                            doctype: frm.doc.doctype,
                            name: frm.doc.name
                        },
                        callback: function(r) {
                            if (r.message) {
                                // Show dialog for recipient selection
                                show_whatsapp_recipients_dialog(frm, r.message);
                            }
                        }
                    });
                }, __('Share'));
            }
        }
    });
    
    function show_whatsapp_recipients_dialog(frm, data) {
        let dialog = new frappe.ui.Dialog({
            title: __('Send via WhatsApp'),
            fields: [
                {
                    fieldtype: 'Table',
                    fieldname: 'recipients',
                    label: 'Recipients',
                    fields: [
                        {
                            fieldtype: 'Data',
                            fieldname: 'recipient_name',
                            label: 'Name',
                            reqd: 1,
                            in_list_view: 1
                        },
                        {
                            fieldtype: 'Data',
                            fieldname: 'whatsapp_number',
                            label: 'WhatsApp Number',
                            reqd: 1,
                            in_list_view: 1
                        }
                    ]
                },
                {
                    fieldtype: 'Text',
                    fieldname: 'message',
                    label: 'Custom Message'
                },
                {
                    fieldtype: 'Link',
                    fieldname: 'print_format',
                    label: 'Print Format',
                    options: 'Print Format'
                }
            ],
            primary_action_label: __('Send'),
            primary_action: function(values) {
                if (!values.recipients || values.recipients.length === 0) {
                    frappe.msgprint(__('Please add at least one recipient'));
                    return;
                }
                
                frappe.call({
                    method: 'twilio_integration.api.whatsapp_documents.send_document_via_whatsapp',
                    args: {
                        reference_doctype: frm.doc.doctype,
                        reference_name: frm.doc.name,
                        recipients: values.recipients,
                        message: values.message,
                        print_format: values.print_format
                    },
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.msgprint(r.message.message);
                            dialog.hide();
                        } else {
                            frappe.msgprint(__('Failed to send document'));
                        }
                    }
                });
            }
        });
        
        dialog.show();
    }
    """