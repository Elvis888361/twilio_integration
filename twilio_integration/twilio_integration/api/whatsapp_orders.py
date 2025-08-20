import frappe
from frappe import _
import json
import re
from twilio.rest import Client
from twilio_integration.twilio_integration.doctype.twilio_settings.twilio_settings import get_twilio_credentials

@frappe.whitelist(allow_guest=True)
def handle_order_webhook():
    """Handle incoming WhatsApp messages for order processing"""
    try:
        data = json.loads(frappe.request.data)
        
        message_body = data.get('Body', '').strip().lower()
        from_number = data.get('From', '').replace('whatsapp:', '')
        
        # Get or create order session
        session = get_or_create_order_session(from_number)
        
        # Process message based on current step
        response = process_order_message(session, message_body, from_number)
        
        # Send response
        if response:
            send_whatsapp_message(from_number, response)
        
        return "OK"
        
    except Exception as e:
        frappe.log_error(f"Order webhook error: {str(e)}")
        return "ERROR"

def get_or_create_order_session(customer_number):
    """Get existing active session or create new one"""
    # Check for existing active session
    existing_session = frappe.db.get_value('WhatsApp Order Session', 
        {'customer_number': customer_number, 'status': 'Active'}, 'name')
    
    if existing_session:
        return frappe.get_doc('WhatsApp Order Session', existing_session)
    
    # Create new session
    session = frappe.get_doc({
        'doctype': 'WhatsApp Order Session',
        'customer_number': customer_number
    }).insert()
    
    return session

def process_order_message(session, message, customer_number):
    """Process customer message based on current step"""
    current_step = session.current_step
    
    if message in ['hi', 'hello', 'start', 'order'] or current_step == 'start':
        return handle_start_step(session)
    elif current_step == 'browse_items':
        return handle_browse_items(session, message)
    elif current_step == 'add_item':
        return handle_add_item(session, message)
    elif current_step == 'confirm_order':
        return handle_confirm_order(session, message)
    elif current_step == 'customer_info':
        return handle_customer_info(session, message)
    else:
        return handle_default_response(session)

def handle_start_step(session):
    """Handle order start"""
    session.db_set('current_step', 'browse_items')
    
    # Get available items
    items = frappe.get_all('Item', 
        filters={'disabled': 0, 'has_variants': 0}, 
        fields=['item_code', 'item_name', 'standard_rate'], 
        limit=10)
    
    message = "🛒 *Welcome to our WhatsApp Store!*\n\n"
    message += "Available items:\n"
    
    for i, item in enumerate(items, 1):
        rate = item.standard_rate or 0
        message += f"{i}. {item.item_name} - ${rate:.2f}\n"
    
    message += "\n💡 *How to order:*\n"
    message += "Type item number and quantity (e.g., '1 x 2' for 2 units of item 1)\n"
    message += "Type 'cart' to view your cart\n"
    message += "Type 'checkout' when ready to place order"
    
    return message

def handle_browse_items(session, message):
    """Handle item browsing and adding to cart"""
    if message == 'cart':
        return show_cart(session)
    elif message == 'checkout':
        return handle_checkout(session)
    
    # Parse item selection (e.g., "1 x 2" or "1" or "item1 2")
    pattern = r'(\d+)(?:\s*x?\s*(\d+))?'
    match = re.search(pattern, message)
    
    if match:
        item_index = int(match.group(1)) - 1
        quantity = int(match.group(2)) if match.group(2) else 1
        
        # Get available items
        items = frappe.get_all('Item', 
            filters={'disabled': 0, 'has_variants': 0}, 
            fields=['item_code', 'item_name', 'standard_rate'], 
            limit=10)
        
        if 0 <= item_index < len(items):
            item = items[item_index]
            session.add_item_to_cart(item.item_code, quantity, item.standard_rate)
            
            return f"✅ Added {quantity} x {item.item_name} to your cart!\n\n" + \
                   "Add more items or type 'checkout' to proceed."
    
    return "❌ Invalid format. Use format like '1 x 2' (item 1, quantity 2) or just '1' for 1 unit."

def show_cart(session):
    """Show current cart contents"""
    data = session.get_session_data()
    items = data.get('items', [])
    
    if not items:
        return "🛒 Your cart is empty. Browse items to add to cart!"
    
    message = "🛒 *Your Cart:*\n\n"
    total = 0
    
    for item in items:
        amount = item['quantity'] * item['rate']
        total += amount
        message += f"• {item['item_name']}\n"
        message += f"  Qty: {item['quantity']} x ${item['rate']:.2f} = ${amount:.2f}\n\n"
    
    message += f"💰 *Total: ${total:.2f}*\n\n"
    message += "Type 'checkout' to place order or continue adding items."
    
    return message

def handle_checkout(session):
    """Handle checkout process"""
    data = session.get_session_data()
    
    if not data.get('items'):
        return "❌ Your cart is empty. Add items first!"
    
    session.db_set('current_step', 'customer_info')
    
    return "📝 *Almost done!*\n\n" + \
           "Please provide your name for the order:\n" + \
           "(e.g., 'John Doe')"

def handle_customer_info(session, message):
    """Handle customer information collection"""
    data = session.get_session_data()
    data['customer_info'] = {'name': message}
    session.update_session_data(data)
    
    # Create sales order
    sales_order = session.create_sales_order()
    
    if sales_order:
        session.db_set('current_step', 'completed')
        return f"🎉 *Order Placed Successfully!*\n\n" + \
               f"Order Number: {sales_order}\n" + \
               f"Customer: {message}\n\n" + \
               "Thank you for your order! We'll process it shortly.\n\n" + \
               "Type 'start' to place another order."
    else:
        return "❌ Sorry, there was an error placing your order. Please try again."

def handle_confirm_order(session, message):
    """Handle order confirmation"""
    if message.lower() in ['yes', 'confirm', 'y']:
        sales_order = session.create_sales_order()
        if sales_order:
            return f"✅ Order confirmed! Sales Order: {sales_order}"
        else:
            return "❌ Failed to create order. Please try again."
    else:
        session.db_set('current_step', 'browse_items')
        return "Order cancelled. You can continue shopping or type 'start' to begin again."

def handle_default_response(session):
    """Handle unrecognized messages"""
    return "❓ I didn't understand that. Type 'start' to begin ordering or 'cart' to view your cart."

def send_whatsapp_message(to_number, message):
    """Send WhatsApp message to customer"""
    try:
        account_sid, auth_token, twilio_number = get_twilio_credentials()
        client = Client(account_sid, auth_token)
        
        client.messages.create(
            body=message,
            from_=f'whatsapp:{twilio_number}',
            to=f'whatsapp:{to_number}'
        )
        
    except Exception as e:
        frappe.log_error(f"Failed to send WhatsApp message: {str(e)}")

