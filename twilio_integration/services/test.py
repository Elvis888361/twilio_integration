import frappe
from twilio.rest import Client
import json
import re
from datetime import datetime, timedelta
import pytz

# Configuration - Move to Site Config or DocType for production
STATIC_TWILIO_SID = "AC7b3d98150c02344e32fa5550a488aeda"
STATIC_TWILIO_TOKEN = "aa40c5f5460634a165829d823fa477a8"
STATIC_WHATSAPP_FROM = "+256770787451"

# Order states for conversation flow
ORDER_STATES = {
    'START': 'start',
    'CUSTOMER_NAME': 'customer_name',
    'CUSTOMER_PHONE': 'customer_phone',
    'ADDING_ITEMS': 'adding_items',
    'ITEM_NAME': 'item_name',
    'ITEM_QUANTITY': 'item_quantity',
    'ITEM_RATE': 'item_rate',
    'CONFIRM_ITEM': 'confirm_item',
    'MORE_ITEMS': 'more_items',
    'DELIVERY_DATE': 'delivery_date',
    'DELIVERY_ADDRESS': 'delivery_address',
    'CONFIRM_ORDER': 'confirm_order',
    'COMPLETED': 'completed'
}

@frappe.whitelist(allow_guest=True)
def handle_whatsapp_chatbot():
    """Main webhook handler for WhatsApp chatbot"""
    try:
        # Get the message content
        message_body = frappe.form_dict.get('Body', '').strip()
        from_number = frappe.form_dict.get('From', '').replace('whatsapp:', '').replace('+', '')
        
        # Short logging to avoid character limit
        frappe.log_error(f"MSG: '{message_body}' FROM: +{from_number}", "Chatbot")
        
        if not message_body or not from_number:
            return "OK"
        
        # Handle special commands
        if message_body.lower() in ['reset', 'restart', 'cancel', 'stop']:
            reset_user_session(from_number)
            send_message(from_number, "🔄 Session reset. Type 'HELLO' to start a new order.")
            return "OK"
            
        if message_body.lower() in ['help', 'menu']:
            send_help_message(from_number)
            return "OK"
        
        # Get or create user session
        session = get_user_session(from_number)
        
        # Process the message based on current state
        process_chatbot_message(from_number, message_body, session)
        
        return "OK"
        
    except Exception as e:
        frappe.log_error(f"Error: {str(e)[:100]}", "Chatbot Error")
        # Send error message to user
        try:
            send_message(from_number, "❌ Something went wrong. Type 'HELLO' to restart.")
        except:
            pass
        return "Error"

def send_help_message(phone_number):
    """Send help information"""
    help_msg = """🤖 WhatsApp Order Assistant Help

📋 Available Commands:
• HELLO - Start new order
• HELP - Show this menu
• RESET - Reset current session
• CANCEL - Cancel current order
• STOP - End conversation

📞 For support, contact us directly.

Type 'HELLO' to start ordering! 🛒"""
    
    send_message(phone_number, help_msg)

def get_user_session(phone_number):
    """Get or create user session for conversation state"""
    try:
        # Check if session exists in database
        existing_sessions = frappe.get_all(
            "WhatsApp Order Session",
            filters={"phone_number": phone_number, "status": "Active"},
            fields=["name", "current_state", "order_data"],
            order_by="creation desc",
            limit=1
        )
        
        if existing_sessions:
            session = frappe.get_doc("WhatsApp Order Session", existing_sessions[0].name)
            return session
        else:
            # Create new session
            session = frappe.new_doc("WhatsApp Order Session")
            session.phone_number = phone_number
            session.current_state = ORDER_STATES['START']
            session.order_data = "{}"
            session.status = "Active"
            session.session_started = datetime.now()
            session.insert(ignore_permissions=True)
            frappe.db.commit()
            return session
            
    except Exception as e:
        frappe.log_error(f"Session error: {str(e)[:100]}", "Session Error")
        # Return a basic session object if database operations fail
        return type('Session', (), {
            'phone_number': phone_number,
            'current_state': ORDER_STATES['START'],
            'order_data': "{}",
            'save': lambda: None
        })()

def reset_user_session(phone_number):
    """Reset user session"""
    try:
        # Mark existing sessions as cancelled
        frappe.db.sql("""
            UPDATE `tabWhatsApp Order Session` 
            SET status = 'Cancelled', session_ended = %s
            WHERE phone_number = %s AND status = 'Active'
        """, (datetime.now(), phone_number))
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Reset error: {str(e)[:100]}", "Reset Error")

def process_chatbot_message(phone_number, message, session):
    """Process message based on current conversation state"""
    try:
        current_state = session.current_state
        order_data = json.loads(session.order_data or "{}")
        
        # Handle different conversation states
        if current_state == ORDER_STATES['START']:
            handle_start_conversation(phone_number, message, session, order_data)
            
        elif current_state == ORDER_STATES['CUSTOMER_NAME']:
            handle_customer_name(phone_number, message, session, order_data)
            
        elif current_state == ORDER_STATES['CUSTOMER_PHONE']:
            handle_customer_phone(phone_number, message, session, order_data)
            
        elif current_state == ORDER_STATES['ADDING_ITEMS']:
            handle_adding_items(phone_number, message, session, order_data)
            
        elif current_state == ORDER_STATES['ITEM_NAME']:
            handle_item_name(phone_number, message, session, order_data)
            
        elif current_state == ORDER_STATES['ITEM_QUANTITY']:
            handle_item_quantity(phone_number, message, session, order_data)
            
        elif current_state == ORDER_STATES['ITEM_RATE']:
            handle_item_rate(phone_number, message, session, order_data)
            
        elif current_state == ORDER_STATES['CONFIRM_ITEM']:
            handle_confirm_item(phone_number, message, session, order_data)
            
        elif current_state == ORDER_STATES['MORE_ITEMS']:
            handle_more_items(phone_number, message, session, order_data)
            
        elif current_state == ORDER_STATES['DELIVERY_DATE']:
            handle_delivery_date(phone_number, message, session, order_data)
            
        elif current_state == ORDER_STATES['DELIVERY_ADDRESS']:
            handle_delivery_address(phone_number, message, session, order_data)
            
        elif current_state == ORDER_STATES['CONFIRM_ORDER']:
            handle_confirm_order(phone_number, message, session, order_data)
            
        else:
            # Reset conversation if unknown state
            reset_conversation(phone_number, session)
            
    except Exception as e:
        frappe.log_error(f"Process error: {str(e)[:100]}", "Process Error")
        send_message(phone_number, "❌ Sorry, something went wrong. Let's start over. Type 'HELLO' to begin.")
        reset_conversation(phone_number, session)

# =============================================================================
# HANDLER FUNCTIONS - These were missing in your original code
# =============================================================================

def handle_start_conversation(phone_number, message, session, order_data):
    """Handle start of conversation"""
    if message.lower() in ['hello', 'hi', 'start', 'order']:
        msg = """🛒 Welcome to our WhatsApp ordering service!

Let's start your order. What's your name?"""
        
        session.current_state = ORDER_STATES['CUSTOMER_NAME']
        update_session(session, order_data)
        send_message(phone_number, msg)
    else:
        msg = """👋 Hello! Welcome to our ordering service.

Type 'HELLO' to start placing an order
Type 'HELP' for assistance"""
        send_message(phone_number, msg)

def handle_customer_name(phone_number, message, session, order_data):
    """Handle customer name input"""
    order_data['customer_name'] = message.strip()
    
    msg = f"""Thanks {message}! 👤

Now, please provide your phone number for delivery confirmation."""
    
    session.current_state = ORDER_STATES['CUSTOMER_PHONE']
    update_session(session, order_data)
    send_message(phone_number, msg)

def handle_customer_phone(phone_number, message, session, order_data):
    """Handle customer phone input"""
    # Basic phone validation
    clean_phone = re.sub(r'[^\d+]', '', message)
    if len(clean_phone) < 10:
        send_message(phone_number, "❌ Please enter a valid phone number (at least 10 digits)")
        return
    
    order_data['customer_phone'] = clean_phone
    order_data['items'] = []
    
    msg = """📞 Phone number saved!

Now let's add items to your order. What's the first item you'd like to order?"""
    
    session.current_state = ORDER_STATES['ITEM_NAME']
    update_session(session, order_data)
    send_message(phone_number, msg)

def handle_adding_items(phone_number, message, session, order_data):
    """Handle adding items state"""
    # This state is used when transitioning to item addition
    handle_item_name(phone_number, message, session, order_data)

def handle_item_name(phone_number, message, session, order_data):
    """Handle item name input"""
    if not order_data.get('items'):
        order_data['items'] = []
    
    # Store current item being added
    order_data['current_item'] = {'item_name': message.strip()}
    
    msg = f"""📦 Item: {message}

How many units of "{message}" do you want? (Enter quantity)"""
    
    session.current_state = ORDER_STATES['ITEM_QUANTITY']
    update_session(session, order_data)
    send_message(phone_number, msg)

def handle_item_quantity(phone_number, message, session, order_data):
    """Handle item quantity input"""
    try:
        quantity = float(message.strip())
        if quantity <= 0:
            send_message(phone_number, "❌ Please enter a valid quantity (greater than 0)")
            return
        
        order_data['current_item']['quantity'] = quantity
        
        msg = f"""📊 Quantity: {quantity}

What's the price per unit for "{order_data['current_item']['item_name']}"? (Enter price)"""
        
        session.current_state = ORDER_STATES['ITEM_RATE']
        update_session(session, order_data)
        send_message(phone_number, msg)
        
    except ValueError:
        send_message(phone_number, "❌ Please enter a valid number for quantity")

def handle_item_rate(phone_number, message, session, order_data):
    """Handle item rate input"""
    try:
        rate = float(message.strip())
        if rate <= 0:
            send_message(phone_number, "❌ Please enter a valid price (greater than 0)")
            return
        
        order_data['current_item']['rate'] = rate
        total = order_data['current_item']['quantity'] * rate
        
        msg = f"""💰 Item Summary:
📦 Item: {order_data['current_item']['item_name']}
📊 Quantity: {order_data['current_item']['quantity']}
💵 Price: {rate:,.0f} each
💰 Total: {total:,.0f}

Is this correct? Reply 'YES' to confirm or 'NO' to change"""
        
        session.current_state = ORDER_STATES['CONFIRM_ITEM']
        update_session(session, order_data)
        send_message(phone_number, msg)
        
    except ValueError:
        send_message(phone_number, "❌ Please enter a valid number for price")

def handle_confirm_item(phone_number, message, session, order_data):
    """Handle item confirmation"""
    if message.lower() in ['yes', 'y', 'confirm', 'ok']:
        # Add item to order
        order_data['items'].append(order_data['current_item'])
        del order_data['current_item']
        
        msg = f"""✅ Item added successfully!

Would you like to add another item?
• Reply 'YES' to add more items
• Reply 'NO' to proceed to delivery details"""
        
        session.current_state = ORDER_STATES['MORE_ITEMS']
        update_session(session, order_data)
        send_message(phone_number, msg)
        
    elif message.lower() in ['no', 'n', 'change']:
        msg = """Let's start over with this item.

What item would you like to order?"""
        
        session.current_state = ORDER_STATES['ITEM_NAME']
        update_session(session, order_data)
        send_message(phone_number, msg)
    else:
        send_message(phone_number, "Please reply 'YES' to confirm or 'NO' to change the item details")

def handle_more_items(phone_number, message, session, order_data):
    """Handle more items question"""
    if message.lower() in ['yes', 'y', 'add', 'more']:
        msg = """What's the next item you'd like to add to your order?"""
        
        session.current_state = ORDER_STATES['ITEM_NAME']
        update_session(session, order_data)
        send_message(phone_number, msg)
        
    elif message.lower() in ['no', 'n', 'done', 'finish']:
        # Show order summary and ask for delivery date
        summary = "📋 ORDER SUMMARY:\n\n"
        total = 0
        for i, item in enumerate(order_data['items'], 1):
            item_total = item['quantity'] * item['rate']
            total += item_total
            summary += f"{i}. {item['item_name']}\n   Qty: {item['quantity']} × {item['rate']:,.0f} = {item_total:,.0f}\n\n"
        
        summary += f"💰 TOTAL: {total:,.0f}\n\n"
        summary += "When do you need this delivered?\n(e.g., 'Today', 'Tomorrow', '2024-01-15')"
        
        session.current_state = ORDER_STATES['DELIVERY_DATE']
        update_session(session, order_data)
        send_message(phone_number, summary)
    else:
        send_message(phone_number, "Please reply 'YES' to add more items or 'NO' to proceed")

def handle_delivery_date(phone_number, message, session, order_data):
    """Handle delivery date input"""
    order_data['delivery_date'] = message.strip()
    
    msg = f"""📅 Delivery date: {message}

Please provide your delivery address:"""
    
    session.current_state = ORDER_STATES['DELIVERY_ADDRESS']
    update_session(session, order_data)
    send_message(phone_number, msg)

def handle_delivery_address(phone_number, message, session, order_data):
    """Handle delivery address input"""
    order_data['delivery_address'] = message.strip()
    
    # Final order summary
    summary = "🔍 FINAL ORDER REVIEW:\n\n"
    summary += f"👤 Customer: {order_data['customer_name']}\n"
    summary += f"📞 Phone: {order_data['customer_phone']}\n"
    summary += f"📅 Delivery: {order_data['delivery_date']}\n"
    summary += f"📍 Address: {order_data['delivery_address']}\n\n"
    
    summary += "📦 ITEMS:\n"
    total = 0
    for i, item in enumerate(order_data['items'], 1):
        item_total = item['quantity'] * item['rate']
        total += item_total
        summary += f"{i}. {item['item_name']}\n   {item['quantity']} × {item['rate']:,.0f} = {item_total:,.0f}\n"
    
    summary += f"\n💰 GRAND TOTAL: {total:,.0f}\n\n"
    summary += "Confirm your order? Reply 'CONFIRM' to place order or 'CANCEL' to cancel"
    
    session.current_state = ORDER_STATES['CONFIRM_ORDER']
    update_session(session, order_data)
    send_message(phone_number, summary)

def handle_confirm_order(phone_number, message, session, order_data):
    """Handle final order confirmation"""
    if message.lower() in ['confirm', 'yes', 'place', 'order']:
        try:
            # Create Sales Order
            sales_order = create_sales_order(order_data)
            
            if sales_order:
                msg = f"""✅ ORDER PLACED SUCCESSFULLY!

📋 Order Number: {sales_order.name}
💰 Total Amount: {sales_order.grand_total:,.0f}

Thank you for your order! We'll contact you soon for confirmation.

Type 'HELLO' to place another order."""
                
                # Mark session as completed
                session.status = "Completed"
                session.session_ended = datetime.now()
                session.created_sales_order = sales_order.name
                session.current_state = ORDER_STATES['COMPLETED']
                update_session(session, order_data)
                
            else:
                msg = """❌ Sorry, there was an error creating your order. 

Please try again or contact support."""
            
            send_message(phone_number, msg)
            
        except Exception as e:
            frappe.log_error(f"Order creation error: {str(e)[:100]}", "Order Error")
            send_message(phone_number, "❌ Sorry, there was an error. Please try again or contact support.")
            
    elif message.lower() in ['cancel', 'no', 'stop']:
        send_message(phone_number, "❌ Order cancelled. Type 'HELLO' to start a new order.")
        reset_user_session(phone_number)
    else:
        send_message(phone_number, "Please reply 'CONFIRM' to place your order or 'CANCEL' to cancel")

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def create_sales_order(order_data):
    """Create Sales Order in ERPNext from order data"""
    try:
        # Create or get customer
        customer = get_or_create_customer(order_data['customer_name'], order_data['customer_phone'])
        
        # Parse delivery date
        delivery_date = parse_delivery_date(order_data.get('delivery_date', 'Today'))
        
        # Create Sales Order
        so = frappe.new_doc("Sales Order")
        so.customer = customer.name
        so.transaction_date = datetime.now().date()
        so.delivery_date = delivery_date
        so.custom_phone = order_data['customer_phone']
        so.custom_delivery_address = order_data.get('delivery_address', '')
        so.custom_whatsapp_order = 1  # Custom field to mark WhatsApp orders
        
        # Add items
        for item_data in order_data['items']:
            # Get or create item
            item = get_or_create_item(item_data['item_name'])
            
            so.append("items", {
                "item_code": item.name,
                "item_name": item_data['item_name'],
                "qty": item_data['quantity'],
                "rate": item_data['rate'],
                "amount": item_data['quantity'] * item_data['rate']
            })
        
        so.flags.ignore_permissions = True
        so.insert()
        so.submit()
        
        frappe.db.commit()
        return so
        
    except Exception as e:
        frappe.log_error(f"SO creation error: {str(e)[:100]}", "SO Error")
        return None

def parse_delivery_date(date_str):
    """Parse delivery date from various formats"""
    try:
        date_str = date_str.lower().strip()
        today = datetime.now().date()
        
        if date_str in ['today', 'now']:
            return today
        elif date_str in ['tomorrow']:
            return today + timedelta(days=1)
        elif 'next monday' in date_str:
            days_ahead = 0 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return today + timedelta(days_ahead)
        elif 'next week' in date_str:
            return today + timedelta(days=7)
        else:
            # Try to parse date formats
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y']:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue
            
            # Default to today if parsing fails
            return today
            
    except Exception:
        return datetime.now().date()

def get_or_create_customer(customer_name, phone):
    """Get existing customer or create new one"""
    try:
        # Check if customer exists by phone
        existing = frappe.get_all("Customer", filters={"mobile_no": phone}, limit=1)
        
        if existing:
            return frappe.get_doc("Customer", existing[0].name)
        
        # Create new customer
        customer = frappe.new_doc("Customer")
        customer.customer_name = customer_name
        customer.customer_type = "Individual"
        customer.customer_group = "Individual"
        customer.territory = "Uganda"  # Adjust as needed
        customer.mobile_no = phone
        customer.flags.ignore_permissions = True
        customer.insert()
        
        return customer
        
    except Exception as e:
        frappe.log_error(f"Customer error: {str(e)[:100]}", "Customer Error")
        raise e

def get_or_create_item(item_name):
    """Get existing item or create new one"""
    try:
        # Check if item exists
        existing = frappe.get_all("Item", filters={"item_name": item_name}, limit=1)
        
        if existing:
            return frappe.get_doc("Item", existing[0].name)
        
        # Create new item
        item_code = re.sub(r'[^a-zA-Z0-9]', '_', item_name.upper())[:140]
        
        item = frappe.new_doc("Item")
        item.item_code = item_code
        item.item_name = item_name
        item.item_group = "Products"  # Adjust as needed
        item.stock_uom = "Nos"
        item.is_stock_item = 1
        item.is_sales_item = 1
        item.flags.ignore_permissions = True
        item.insert()
        
        return item
        
    except Exception as e:
        frappe.log_error(f"Item error: {str(e)[:100]}", "Item Error")
        raise e

def send_message(phone_number, message):
    """Send WhatsApp message"""
    try:
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
            
        client = Client(STATIC_TWILIO_SID, STATIC_TWILIO_TOKEN)
        
        response = client.messages.create(
            body=message,
            from_=f"whatsapp:{STATIC_WHATSAPP_FROM}",
            to=f"whatsapp:{phone_number}"
        )
        
        frappe.log_error(f"Message sent - SID: {response.sid}", "Message Sent")
        
    except Exception as e:
        frappe.log_error(f"Send failed: {str(e)[:100]}", "Send Failed")

def update_session(session, order_data):
    """Update session with current state and data"""
    try:
        session.order_data = json.dumps(order_data)
        session.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Session update: {str(e)[:100]}", "Session Update")

def reset_conversation(phone_number, session):
    """Reset conversation to start state"""
    try:
        session.current_state = ORDER_STATES['START']
        session.order_data = "{}"
        session.status = "Reset"
        session.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Reset error: {str(e)[:100]}", "Reset Error")

# =============================================================================
# ADDITIONAL UTILITY FUNCTIONS
# =============================================================================

def validate_session(doc, method):
    """Validate session document"""
    if not doc.phone_number:
        frappe.throw("Phone number is required")
    
    # Normalize phone number
    doc.phone_number = doc.phone_number.replace('+', '').replace(' ', '').replace('-', '')

def on_session_update(doc, method):
    """Handle session updates"""
    if doc.status == "Completed" and not doc.session_ended:
        doc.session_ended = datetime.now()

def on_sales_order_submit(doc, method):
    """Handle sales order submission - send confirmation"""
    if hasattr(doc, 'custom_whatsapp_order') and doc.custom_whatsapp_order:
        send_order_confirmation(doc)

def send_order_confirmation(sales_order):
    """Send order confirmation via WhatsApp"""
    try:
        phone = sales_order.custom_phone
        if phone:
            msg = f"""✅ ORDER CONFIRMED!

📋 Order: {sales_order.name}
👤 Customer: {sales_order.customer}
💵 Total: {sales_order.grand_total:,.0f}
📅 Delivery: {sales_order.delivery_date}

Thank you for your order! 🙏"""
            
            send_message(phone.replace('+', ''), msg)
            
    except Exception as e:
        frappe.log_error(f"Confirmation error: {str(e)[:100]}", "Confirmation")

def cleanup_old_sessions():
    """Clean up old completed sessions"""
    try:
        # Delete sessions older than 30 days
        cutoff_date = datetime.now() - timedelta(days=30)
        frappe.db.sql("""
            DELETE FROM `tabWhatsApp Order Session`
            WHERE status IN ('Completed', 'Cancelled') 
            AND creation < %s
        """, cutoff_date)
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Cleanup error: {str(e)[:100]}", "Cleanup")

def cleanup_inactive_sessions():
    """Clean up inactive sessions (older than 2 hours)"""
    try:
        cutoff_time = datetime.now() - timedelta(hours=2)
        frappe.db.sql("""
            UPDATE `tabWhatsApp Order Session`
            SET status = 'Cancelled', session_ended = %s
            WHERE status = 'Active' 
            AND modified < %s
        """, (datetime.now(), cutoff_time))
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Inactive cleanup: {str(e)[:100]}", "Cleanup")

@frappe.whitelist()
def test_chatbot(phone_number):
    """Test the chatbot system"""
    try:
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        
        # Send welcome message
        welcome_msg = """🤖 CHATBOT TEST

Hi! This is a test of our WhatsApp ordering system.

Type 'HELLO' to start placing an order!"""
        
        send_message(phone_number.replace('+', ''), welcome_msg)
        
        return {
            "status": "success",
            "message": f"Test message sent to {phone_number}",
            "instructions": "Reply 'HELLO' to start the ordering process"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Test failed: {str(e)}"
        }

@frappe.whitelist()
def get_session_info(phone_number):
    """Get current session information for debugging"""
    try:
        session = get_user_session(phone_number.replace('+', ''))
        order_data = json.loads(session.order_data or "{}")
        
        return {
            "phone_number": session.phone_number,
            "current_state": session.current_state,
            "order_data": order_data,
            "status": getattr(session, 'status', 'Unknown')
        }
        
    except Exception as e:
        return {
            "error": str(e)
        }

@frappe.whitelist()
def get_order_status(order_name):
    """Get order status for Jinja templates"""
    try:
        order = frappe.get_doc("Sales Order", order_name)
        return order.status
    except:
        return "Unknown"