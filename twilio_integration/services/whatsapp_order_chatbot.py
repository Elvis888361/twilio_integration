import frappe
from frappe import _
import requests
import json
import hashlib
import time
from twilio.rest import Client
from datetime import datetime, timedelta

# ======================== CHATBOT CODE (UNCHANGED FROM ORIGINAL) ========================
# Configuration
twilio_settings = frappe.get_doc("whatsapp integration settings")
STATIC_TWILIO_SID = twilio_settings.twilio_sid
STATIC_TWILIO_TOKEN = twilio_settings.twilio_token
STATIC_WHATSAPP_FROM = twilio_settings.twilio_number

@frappe.whitelist(allow_guest=True)
def handle_whatsapp_chatbot():
    """Main webhook handler for WhatsApp chatbot - NOW HANDLES BOTH CHATBOT AND WORKFLOW"""
    try:
        message_body = frappe.form_dict.get('Body', '').strip()
        from_number = frappe.form_dict.get('From', '').replace('whatsapp:', '').replace('+', '')
        
        frappe.log_error(f"Received: {message_body} from {from_number}", "WhatsApp Message")
        
        if not message_body or not from_number:
            return "OK"
        
        # Handle reset commands
        if message_body.lower() in ['reset', 'restart', 'cancel', '0', 'start']:
            reset_and_start(from_number)
            return "OK"
        
        # NEW: Check if this is a workflow action first
        if is_workflow_action_message(from_number, message_body):
            frappe.log_error(f"Processing as workflow action: {message_body}", "Workflow Action")
            process_workflow_action_via_chatbot(from_number, message_body)
            return "OK"
        
        # Process as normal chatbot message
        process_message(from_number, message_body)
        return "OK"
        
    except Exception as e:
        frappe.log_error(f"Chatbot error: {str(e)}", "Chatbot Error")
        return "Error"

def is_workflow_action_message(phone_number, message_body):
    """Check if incoming message is a workflow action - IMPROVED"""
    try:
        # Find user by phone number
        user = find_user_by_mobile_for_workflow(phone_number)
        if not user:
            frappe.log_error(f"No user found for {phone_number}", "User Lookup Debug")
            return False
        
        frappe.log_error(f"Found user {user} for {phone_number}", "User Found Debug")
        
        # Check if user has pending workflow documents
        pending_docs = get_pending_documents_for_user_workflow(user)
        if not pending_docs:
            frappe.log_error(f"No pending docs for user {user}", "No Pending Debug")
            return False
        
        frappe.log_error(f"User {user} has {len(pending_docs)} pending docs", "Pending Docs Debug")
        
        # Check if message looks like a workflow action
        message_lower = message_body.lower().strip()
        
        # Check for numbered actions
        if message_body.strip().isdigit():
            action_num = int(message_body.strip())
            if 1 <= action_num <= 10:
                frappe.log_error(f"Detected workflow action number: {action_num}", "Action Number Debug")
                return True
        
        # Check for workflow keywords
        workflow_keywords = ['approve', 'reject', 'status', 'pending', 'workflow']
        if any(keyword in message_lower for keyword in workflow_keywords):
            frappe.log_error(f"Detected workflow keyword in: {message_body}", "Keyword Debug")
            return True
        
        frappe.log_error(f"Message '{message_body}' not recognized as workflow action", "Not Workflow Debug")
        return False
        
    except Exception as e:
        frappe.log_error(f"Error checking workflow action: {str(e)}", "Workflow Check Error")
        return False

def process_workflow_action_via_chatbot(phone_number, message_body):
    """Process workflow actions through the chatbot webhook"""
    try:
        user = find_user_by_mobile_for_workflow(phone_number)
        if not user:
            send_message(phone_number, "User not found for workflow actions.")
            return
        
        # Handle status request
        if message_body.lower() in ['status', 'pending']:
            send_workflow_status_via_chatbot(phone_number, user)
            return
        
        # Handle numbered actions
        if message_body.isdigit():
            action_number = int(message_body)
            execute_workflow_action_via_chatbot(phone_number, user, action_number)
        else:
            send_message(phone_number, "Reply with a number for workflow actions or 'status' to see pending items.")
        
    except Exception as e:
        frappe.log_error(f"Workflow action error: {str(e)}", "Workflow Action Error")
        send_message(phone_number, "Error processing workflow action.")

def send_workflow_status_via_chatbot(phone_number, user):
    """Send workflow status through chatbot - ENHANCED"""
    try:
        pending_docs = get_pending_documents_for_user_workflow(user)
        
        if not pending_docs:
            send_message(phone_number, "✅ No pending approvals found.")
            return
        
        msg = f"📋 *PENDING APPROVALS* ({len(pending_docs)})\n\n"
        
        # Show detailed info for first 3 documents
        for i, doc_info in enumerate(pending_docs[:3], 1):
            # Get full document for more details
            try:
                doc = frappe.get_doc(doc_info['doctype'], doc_info['name'])
                
                # Get available actions
                actions = get_workflow_actions_for_chatbot(doc_info['doctype'], doc_info['state'])
                
                msg += f"*{i}. {doc_info['doctype']}: {doc_info['name']}*\n"
                msg += f"📊 State: {doc_info['state']}\n"
                
                # Add customer info if available
                if hasattr(doc, 'customer'):
                    msg += f"👤 Customer: {doc.customer}\n"
                
                # Add amount if configured
                workflow_config = get_workflow_config(doc_info['doctype'])
                if workflow_config and workflow_config.get('include_amount_field') and workflow_config.get('amount_field'):
                    amount_field = workflow_config['amount_field']
                    if hasattr(doc, amount_field):
                        amount_value = getattr(doc, amount_field)
                        currency = getattr(doc, 'currency', frappe.defaults.get_global_default('currency'))
                        msg += f"💰 Amount: {frappe.utils.fmt_money(amount_value, currency=currency)}\n"
                
                # Show available actions
                if actions:
                    msg += f"Actions: "
                    for j, action in enumerate(actions, 1):
                        msg += f"{j}-{action['action']} "
                    msg += "\n"
                
                msg += "\n"
                
            except Exception as e:
                msg += f"{i}. {doc_info['doctype']}: {doc_info['name']} (Error loading details)\n\n"
        
        if len(pending_docs) > 3:
            msg += f"... and {len(pending_docs) - 3} more documents\n\n"
        
        msg += "💬 *Reply with:*\n"
        msg += "• Document number to see actions\n"
        msg += "• 'status' to refresh this list\n"
        msg += "\n_ERPNext Workflow_"
        
        send_message(phone_number, msg)
        
    except Exception as e:
        frappe.log_error(f"Error sending workflow status: {str(e)}", "Workflow Status Error")
        send_message(phone_number, "Error loading workflow status. Please try again.")


def execute_workflow_action_via_chatbot(phone_number, user, action_number):
    """Execute workflow action through chatbot"""
    try:
        pending_docs = get_pending_documents_for_user_workflow(user)
        
        if not pending_docs:
            send_message(phone_number, "No pending documents found.")
            return
        
        # Get the most recent document
        latest_doc = pending_docs[0]
        
        # Get available actions
        actions = get_workflow_actions_for_chatbot(latest_doc['doctype'], latest_doc['state'])
        
        if action_number > len(actions) or action_number < 1:
            # FIX: Show available actions in error message
            actions_text = "\n".join([f"{i+1} - {action['action']}" for i, action in enumerate(actions)])
            msg = f"Invalid action. Available actions:\n{actions_text}"
            send_message(phone_number, msg)
            return
        
        selected_action = actions[action_number - 1]
        
        # Check permissions
        user_roles = frappe.get_roles(user)
        if selected_action['allowed_role'] not in user_roles:
            send_message(phone_number, f"Permission denied for action: {selected_action['action']}")
            return
        
        # Execute the action
        doc = frappe.get_doc(latest_doc['doctype'], latest_doc['name'])
        
        # FIX: Set user context properly
        frappe.set_user(user)
        
        # Add comment
        doc.add_comment("Workflow", f"Action '{selected_action['action']}' via WhatsApp by {user}")
        
        # FIX: Update state and save with proper flags
        doc.workflow_state = selected_action['next_state']
        doc.flags.ignore_permissions = True
        doc.save(ignore_permissions=True)
        
        # FIX: Critical - commit the transaction
        frappe.db.commit()
        
        # Send confirmation
        msg = f"""✅ ACTION COMPLETED!

{doc.doctype}: {doc.name}
Action: {selected_action['action']}
New State: {doc.workflow_state}

ERPNext"""
        send_message(phone_number, msg)
        
        # FIX: Send updated status after action
        frappe.enqueue(
            'your_app.whatsapp_integration.send_workflow_status_via_chatbot',
            phone_number=phone_number,
            user=user,
            queue='short'
        )
        
    except frappe.ValidationError as e:
        frappe.log_error(f"Validation error in workflow action: {str(e)}", "Workflow Validation Error")
        send_message(phone_number, f"Validation error: {str(e)}")
    except frappe.PermissionError as e:
        frappe.log_error(f"Permission error in workflow action: {str(e)}", "Workflow Permission Error")
        send_message(phone_number, "Permission denied for this action.")
    except Exception as e:
        frappe.log_error(f"Execute workflow action error: {str(e)}", "Execute Action Error")
        send_message(phone_number, "Error executing action. Please try again.")

# ======================== ORIGINAL CHATBOT FUNCTIONS (UNCHANGED) ========================
def process_message(phone_number, message):
    """Process incoming message based on simple state"""
    try:
        # Get current state from cache or database
        state = get_user_state(phone_number)
        
        frappe.log_error(f"Current state for {phone_number}: {state}", "State Check")
        
        if state == "START" or not state:
            handle_main_menu(phone_number, message)
        elif state == "MAIN_MENU":
            handle_main_menu_choice(phone_number, message)
        elif state == "CUSTOMER_SELECT":
            handle_customer_choice(phone_number, message)
        elif state == "NEW_CUSTOMER_NAME":
            handle_new_customer_name(phone_number, message)
        elif state == "ITEMS_BROWSE":
            handle_items_browse(phone_number, message)
        elif state == "ITEM_SELECTED":
            handle_item_selection(phone_number, message)
        elif state == "QUANTITY":
            handle_quantity_input(phone_number, message)
        elif state == "CART_MENU":
            handle_cart_menu(phone_number, message)
        elif state == "CHECKOUT":
            handle_checkout(phone_number, message)
        else:
            # Reset if unknown state
            reset_and_start(phone_number)
            
    except Exception as e:
        frappe.log_error(f"Process message error: {str(e)}", "Process Error")
        send_message(phone_number, "Error occurred. Restarting...")
        reset_and_start(phone_number)

def handle_main_menu(phone_number, message):
    """Show main menu"""
    msg = """🛒 *WELCOME TO OUR STORE*

Select an option:
*1* - 🛍️ Browse & Order Items
*2* - 📞 Contact Support
*3* - ℹ️ About Us

Type a number (1-3):"""
    
    set_user_state(phone_number, "MAIN_MENU")
    send_message(phone_number, msg)

def handle_main_menu_choice(phone_number, message):
    """Handle main menu selection"""
    try:
        choice = int(message.strip())
        
        if choice == 1:
            # Start ordering process
            show_customer_options(phone_number)
        elif choice == 2:
            # Contact support
            msg = """CONTACT SUPPORT

Phone: +256-XXX-XXXXXX
Email: support@store.com
Hours: 8AM - 6PM

Type 0 to return to main menu."""
            send_message(phone_number, msg)
        elif choice == 3:
            # About us
            msg = """ℹ️ *ABOUT US*

Your trusted online store!
✅ Quality products
✅ Fast delivery
✅ 24/7 WhatsApp ordering

Type 0 to return to main menu."""
            send_message(phone_number, msg)
        else:
            send_message(phone_number, "❌ Please choose 1, 2, or 3")
            
    except ValueError:
        send_message(phone_number, "❌ Please enter a valid number (1-3)")

def show_customer_options(phone_number):
    """Show customer selection options"""
    msg = """👤 *CUSTOMER INFO*

*1* - 🆕 New Customer
*2* - 🔍 Existing Customer

Type 1 or 2"""
    
    set_user_state(phone_number, "CUSTOMER_SELECT")
    send_message(phone_number, msg)

def handle_customer_choice(phone_number, message):
    """Handle customer selection"""
    try:
        choice = int(message.strip())
        
        if choice == 1:
            # New customer
            msg = "👤 Please enter your name:"
            set_user_state(phone_number, "NEW_CUSTOMER_NAME")
            send_message(phone_number, msg)
        elif choice == 2:
            # Skip customer creation for now
            show_items_menu(phone_number)
        else:
            send_message(phone_number, "❌ Please choose 1 or 2")
            
    except ValueError:
        send_message(phone_number, "❌ Please enter 1 or 2")

def handle_new_customer_name(phone_number, message):
    """Handle new customer name input"""
    name = message.strip()
    
    if len(name) < 2:
        send_message(phone_number, "❌ Please enter a valid name (at least 2 characters)")
        return
    
    # Save customer name temporarily
    save_temp_data(phone_number, "customer_name", name)
    
    # Move to items
    show_items_menu(phone_number)

def show_items_menu(phone_number):
    """Show available items"""
    try:
        frappe.log_error(f"Showing items menu for {phone_number}", "Items Menu Debug")
        
        # Get some items from database
        items = get_available_items()
        
        frappe.log_error(f"Retrieved {len(items)} items for {phone_number}", "Items Retrieved")
        
        if not items:
            # Send more helpful message and try to diagnose
            msg = """❌ *NO ITEMS FOUND*

This might be because:
• No items are marked as 'Sales Item'
• No items have prices set
• Items might be disabled

Please contact admin or try again later.

Type 0 to go back to main menu."""
            
            frappe.log_error(f"No items available for {phone_number}", "No Items Error")
            send_message(phone_number, msg)
            set_user_state(phone_number, "MAIN_MENU")
            return
        
        msg = "📦 *AVAILABLE ITEMS*\n\n"
        
        # Show first 5 items
        for i, item in enumerate(items[:5], 1):
            price = item.get('standard_rate', 0)
            price_text = f"{price:,.0f} UGX" if price > 0 else "Price on request"
            uom = item.get('stock_uom', 'unit')
            msg += f"{i} - {item['item_name']}\n    💰 {price_text} per {uom}\n\n"
        
        msg += "Type item number (1-5):"
        
        # Save items for reference
        save_temp_data(phone_number, "current_items", items[:5])
        set_user_state(phone_number, "ITEMS_BROWSE")
        
        frappe.log_error(f"Sending items menu to {phone_number}", "Items Menu Sent")
        send_message(phone_number, msg)
        
    except Exception as e:
        frappe.log_error(f"Items menu error: {str(e)}", "Items Menu Error")
        send_message(phone_number, "Error loading items. Type 0 to go back to main menu.")
        set_user_state(phone_number, "MAIN_MENU")

def handle_items_browse(phone_number, message):
    """Handle item selection"""
    try:
        choice = int(message.strip())
        items = get_temp_data(phone_number, "current_items") or []
        
        if 1 <= choice <= len(items):
            selected_item = items[choice - 1]
            
            # Show item details
            price = selected_item.get('standard_rate', 0)
            if price <= 0:
                send_message(phone_number, "❌ This item is not available for purchase.")
                return
            
            msg = f"""📦 *{selected_item['item_name']}*

💰 Price: {price:,.0f} UGX per {selected_item.get('stock_uom', 'unit')}

*1* - ➕ Add to Cart
*2* - 🔙 Back to Items

Choose 1 or 2:"""
            
            save_temp_data(phone_number, "selected_item", selected_item)
            set_user_state(phone_number, "ITEM_SELECTED")
            send_message(phone_number, msg)
        else:
            send_message(phone_number, f"❌ Please choose 1-{len(items)}")
            
    except ValueError:
        send_message(phone_number, "❌ Please enter a valid number")

def handle_item_selection(phone_number, message):
    """Handle add to cart or back"""
    try:
        choice = int(message.strip())
        
        if choice == 1:
            # Add to cart - ask for quantity
            msg = "📊 Enter quantity (e.g., 1, 2, 5):"
            set_user_state(phone_number, "QUANTITY")
            send_message(phone_number, msg)
        elif choice == 2:
            # Back to items
            show_items_menu(phone_number)
        else:
            send_message(phone_number, "❌ Please choose 1 or 2")
            
    except ValueError:
        send_message(phone_number, "❌ Please enter 1 or 2")

def handle_quantity_input(phone_number, message):
    """Handle quantity input"""
    try:
        qty = float(message.strip())
        
        if qty <= 0:
            send_message(phone_number, "❌ Please enter a quantity greater than 0")
            return
        
        selected_item = get_temp_data(phone_number, "selected_item")
        if not selected_item:
            send_message(phone_number, "❌ Error: No item selected")
            return
        
        # Calculate total
        price = selected_item.get('standard_rate', 0)
        total = qty * price
        
        # Add to cart
        cart_item = {
            'item_name': selected_item['item_name'],
            'item_code': selected_item.get('name', ''),
            'qty': qty,
            'rate': price,
            'total': total,
            'uom': selected_item.get('stock_uom', 'unit')
        }
        
        add_to_cart(phone_number, cart_item)
        
        msg = f"""✅ Added to cart!

📦 {selected_item['item_name']}
📊 Quantity: {qty}
💰 Total: {total:,.0f} UGX

*1* - 🛍️ Continue Shopping
*2* - 🛒 View Cart & Checkout

Choose 1 or 2:"""
        
        set_user_state(phone_number, "CART_MENU")
        send_message(phone_number, msg)
        
    except ValueError:
        send_message(phone_number, "❌ Please enter a valid number for quantity")

def handle_cart_menu(phone_number, message):
    """Handle cart menu options"""
    try:
        choice = int(message.strip())
        
        if choice == 1:
            # Continue shopping
            show_items_menu(phone_number)
        elif choice == 2:
            # View cart and checkout
            show_cart_summary(phone_number)
        else:
            send_message(phone_number, "❌ Please choose 1 or 2")
            
    except ValueError:
        send_message(phone_number, "❌ Please enter 1 or 2")

def show_cart_summary(phone_number):
    """Show cart summary and checkout"""
    cart = get_temp_data(phone_number, "cart") or []
    
    if not cart:
        send_message(phone_number, "Your cart is empty!")
        show_items_menu(phone_number)
        return
    
    total = 0
    msg = "YOUR CART\n\n"
    
    for i, item in enumerate(cart, 1):
        total += item['total']
        msg += f"{i}. {item['item_name']}\n"
        msg += f"   {item['qty']} × {item['rate']:,.0f} = {item['total']:,.0f} UGX\n\n"
    
    msg += f"TOTAL: {total:,.0f} UGX\n\n"
    msg += "*1* - ✅ Place Order\n*2* - 🛍️ Continue Shopping\n\nChoose 1 or 2:"
    
    set_user_state(phone_number, "CHECKOUT")
    send_message(phone_number, msg)

def handle_checkout(phone_number, message):
    """Handle checkout process"""
    try:
        choice = int(message.strip())
        
        if choice == 1:
            # Place order
            success = create_order(phone_number)
            if success:
                msg = """🎉 *ORDER PLACED SUCCESSFULLY!*

Thank you for your order!
We'll contact you soon for delivery details.

Type 0 to start a new order."""
                
                # Clear cart and reset
                clear_user_data(phone_number)
                send_message(phone_number, msg)
            else:
                send_message(phone_number, "❌ Error placing order. Please try again.")
                
        elif choice == 2:
            # Continue shopping
            show_items_menu(phone_number)
        else:
            send_message(phone_number, "Please choose 1 or 2")
            
    except ValueError:
        send_message(phone_number, "Please enter 1 or 2")

# ======================== ORIGINAL CHATBOT UTILITY FUNCTIONS ========================
def send_message(phone_number, message):
    """Send WhatsApp message"""
    try:
        if not phone_number.startswith('+'):
            phone_number = '+' + str(phone_number)
        
        client = Client(STATIC_TWILIO_SID, STATIC_TWILIO_TOKEN)
        
        response = client.messages.create(
            body=message,
            from_=f"whatsapp:{STATIC_WHATSAPP_FROM}",
            to=f"whatsapp:{phone_number}"
        )
        
        frappe.log_error(f"Message sent to {phone_number}", "Message Success")
        return True
        
    except Exception as e:
        frappe.log_error(f"Send message failed: {str(e)}", "Message Error")
        return False

def get_user_state(phone_number):
    """Get user's current state"""
    try:
        # Try to get from cache first
        cache_key = f"whatsapp_state_{phone_number}"
        state = frappe.cache().get_value(cache_key)
        
        if state:
            return state
        
        # Fallback to database
        sessions = frappe.get_all(
            "WhatsApp Order Session",
            filters={"phone_number": phone_number, "status": "Active"},
            fields=["current_state"],
            order_by="modified desc",
            limit=1
        )
        
        if sessions:
            state = sessions[0].current_state
            frappe.cache().set_value(cache_key, state, expires_in_sec=3600)
            return state
        
        return "START"
        
    except Exception as e:
        frappe.log_error(f"Get state error: {str(e)}", "State Error")
        return "START"

def set_user_state(phone_number, state):
    """Set user's current state"""
    try:
        # Save to cache
        cache_key = f"whatsapp_state_{phone_number}"
        frappe.cache().set_value(cache_key, state, expires_in_sec=3600)
        
        # Also try to save to database
        try:
            session = get_or_create_session(phone_number)
            if session:
                session.current_state = state
                session.save(ignore_permissions=True)
                frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"DB state save error: {str(e)}", "State DB Error")
        
        frappe.log_error(f"State set for {phone_number}: {state}", "State Set")
        
    except Exception as e:
        frappe.log_error(f"Set state error: {str(e)}", "State Error")

def save_temp_data(phone_number, key, data):
    """Save temporary data"""
    try:
        cache_key = f"whatsapp_data_{phone_number}_{key}"
        frappe.cache().set_value(cache_key, data, expires_in_sec=3600)
    except Exception as e:
        frappe.log_error(f"Save temp data error: {str(e)}", "Temp Data Error")

def get_temp_data(phone_number, key):
    """Get temporary data"""
    try:
        cache_key = f"whatsapp_data_{phone_number}_{key}"
        return frappe.cache().get_value(cache_key)
    except Exception as e:
        frappe.log_error(f"Get temp data error: {str(e)}", "Temp Data Error")
        return None

def add_to_cart(phone_number, item):
    """Add item to cart"""
    try:
        cart = get_temp_data(phone_number, "cart") or []
        cart.append(item)
        save_temp_data(phone_number, "cart", cart)
        frappe.log_error(f"Added to cart for {phone_number}: {item['item_name']}", "Cart Add")
    except Exception as e:
        frappe.log_error(f"Add to cart error: {str(e)}", "Cart Error")

def clear_user_data(phone_number):
    """Clear all user data"""
    try:
        # Clear cache
        keys_to_clear = ["cart", "customer_name", "selected_item", "current_items"]
        for key in keys_to_clear:
            cache_key = f"whatsapp_data_{phone_number}_{key}"
            frappe.cache().delete_value(cache_key)
        
        # Reset state
        set_user_state(phone_number, "START")
        
    except Exception as e:
        frappe.log_error(f"Clear data error: {str(e)}", "Clear Error")

def reset_and_start(phone_number):
    """Reset user session and start over"""
    try:
        clear_user_data(phone_number)
        handle_main_menu(phone_number, "")
        frappe.log_error(f"Reset and started for {phone_number}", "Reset")
    except Exception as e:
        frappe.log_error(f"Reset error: {str(e)}", "Reset Error")

def get_available_items():
    """Get available items from database"""
    try:
        frappe.log_error("Fetching items from database", "Items Debug")
        
        # First, try to get ANY items
        all_items = frappe.get_all(
            "Item",
            filters={"disabled": 0, "is_sales_item": 1},
            fields=["name", "item_name", "standard_rate", "stock_uom"],
            limit=20,
            order_by="item_name asc"
        )
        
        frappe.log_error(f"Found {len(all_items)} total sales items", "Items Debug")
        
        # If no items with standard_rate, create some dummy items for testing
        items_with_price = [item for item in all_items if item.get('standard_rate', 0) > 0]
        
        if not items_with_price and all_items:
            frappe.log_error("No items with standard_rate > 0, adding default prices", "Items Debug")
            # Add default prices for testing
            for item in all_items[:5]:
                item['standard_rate'] = 10000  # Default 10,000 UGX
            return all_items[:5]
        
        if items_with_price:
            frappe.log_error(f"Found {len(items_with_price)} items with prices", "Items Debug")
            return items_with_price
            
        # If still no items, create test items
        frappe.log_error("No items found, creating test items", "Items Debug")
        return [
            {"name": "TEST001", "item_name": "Test Rice 1kg", "standard_rate": 5000, "stock_uom": "Kg"},
            {"name": "TEST002", "item_name": "Test Sugar 1kg", "standard_rate": 3000, "stock_uom": "Kg"},
            {"name": "TEST003", "item_name": "Test Cooking Oil 1L", "standard_rate": 8000, "stock_uom": "Litre"},
            {"name": "TEST004", "item_name": "Test Bread", "standard_rate": 2000, "stock_uom": "Nos"},
            {"name": "TEST005", "item_name": "Test Fresh Milk 1L", "standard_rate": 4000, "stock_uom": "Litre"}
        ]
        
    except Exception as e:
        frappe.log_error(f"Get items error: {str(e)}", "Items Error")
        # Return test items if database fails
        return [
            {"name": "TEST001", "item_name": "Test Rice 1kg", "standard_rate": 5000, "stock_uom": "Kg"},
            {"name": "TEST002", "item_name": "Test Sugar 1kg", "standard_rate": 3000, "stock_uom": "Kg"},
            {"name": "TEST003", "item_name": "Test Cooking Oil 1L", "standard_rate": 8000, "stock_uom": "Litre"}
        ]

def get_or_create_session(phone_number):
    """Get or create session record"""
    try:
        # Check if session exists
        existing = frappe.get_all(
            "WhatsApp Order Session",
            filters={"phone_number": phone_number, "status": "Active"},
            limit=1
        )
        
        if existing:
            return frappe.get_doc("WhatsApp Order Session", existing[0].name)
        
        # Create new session
        session = frappe.new_doc("WhatsApp Order Session")
        session.phone_number = phone_number
        session.current_state = "START"
        session.status = "Active"
        session.order_data = "{}"
        session.flags.ignore_permissions = True
        session.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return session
        
    except Exception as e:
        frappe.log_error(f"Session creation error: {str(e)}", "Session Error")
        return None

def create_order(phone_number):
    """Create sales order from cart"""
    try:
        cart = get_temp_data(phone_number, "cart") or []
        customer_name = get_temp_data(phone_number, "customer_name") or f"WhatsApp Customer {phone_number}"
        
        if not cart:
            return False
        
        # Create or get customer
        customer = get_or_create_customer(customer_name, phone_number)
        if not customer:
            return False
        
        # Create sales order
        so = frappe.new_doc("Sales Order")
        so.customer = customer.name
        so.transaction_date = datetime.now().date()
        so.delivery_date = datetime.now().date() + timedelta(days=1)
        
        # Add items
        for item in cart:
            so.append("items", {
                "item_code": item['item_code'],
                "item_name": item['item_name'],
                "qty": item['qty'],
                "rate": item['rate'],
                "amount": item['total']
            })
        
        so.flags.ignore_permissions = True
        so.insert(ignore_permissions=True)
        frappe.db.commit()
        
        frappe.log_error(f"Order created: {so.name} for {phone_number}", "Order Success")
        return True
        
    except Exception as e:
        frappe.log_error(f"Create order error: {str(e)}", "Order Error")
        return False

def get_or_create_customer(customer_name, phone_number):
    """Get or create customer"""
    try:
        # Check existing
        existing = frappe.get_all(
            "Customer",
            filters={"mobile_no": phone_number},
            limit=1
        )
        
        if existing:
            return frappe.get_doc("Customer", existing[0].name)
        
        # Create new
        customer = frappe.new_doc("Customer")
        customer.customer_name = customer_name
        customer.customer_type = "Individual"
        customer.customer_group = "Individual"
        customer.territory = "All Territories"
        customer.mobile_no = phone_number
        
        customer.flags.ignore_permissions = True
        customer.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return customer
        
    except Exception as e:
        frappe.log_error(f"Customer creation error: {str(e)}", "Customer Error")
        return None

# ======================== WORKFLOW FUNCTIONS (MODIFIED TO USE CHATBOT WEBHOOK) ========================
def send_whatsapp_workflow_notifications(doc, method):
    """
    Send WhatsApp notifications for any doctype with enabled workflow notifications
    Now uses the chatbot's messaging system
    """
    try:
        frappe.logger().info(f"Starting WhatsApp workflow notification for {doc.doctype} {doc.name}")
        
        # Check if WhatsApp workflow is enabled for this doctype
        workflow_config = get_workflow_config(doc.doctype)
        if not workflow_config:
            frappe.logger().info(f"No workflow config found for {doc.doctype} - skipping WhatsApp notification")
            return
        
        # Check if current state requires notification
        if not should_send_notification(doc, workflow_config):
            frappe.logger().info(f"No notification needed for {doc.doctype} {doc.name}")
            return
        
        # Get approvers for current workflow state
        approvers = get_workflow_approvers(doc.doctype, doc.workflow_state)
        
        if not approvers:
            frappe.logger().error(f"No approvers found for {doc.doctype} workflow state: {doc.workflow_state}")
            return
        
        # Get available actions for current state
        available_actions = get_workflow_actions_for_chatbot(doc.doctype, doc.workflow_state)
        
        # Prepare dynamic message with action options
        message = prepare_workflow_message_for_chatbot(doc, available_actions, workflow_config)
        
        # Send to all approvers using the chatbot's send_message function
        sent_count = 0
        failed_count = 0
        for approver in approvers:
            if send_message(approver['mobile'], message):
                sent_count += 1
            else:
                failed_count += 1
        
        frappe.logger().info(f"WhatsApp notification complete: {sent_count} sent, {failed_count} failed")
        
    except Exception as e:
        frappe.logger().error(f"WhatsApp workflow notification failed: {str(e)}")
        frappe.log_error(f"WhatsApp Workflow Error: {str(e)}", "WhatsApp Workflow")

def send_workflow_confirmation(doc, method):
    """Send confirmation when workflow state changes to completion states"""
    try:
        workflow_config = get_workflow_config(doc.doctype)
        if not workflow_config:
            return
        
        # Check if current state is a confirmation state
        if doc.workflow_state not in workflow_config['confirmation_states']:
            return
        
        # Check if state actually changed
        if hasattr(doc, '_doc_before_save') and doc._doc_before_save:
            if doc._doc_before_save.workflow_state == doc.workflow_state:
                return
        
        # Get approvers to notify
        approvers = get_workflow_approvers(doc.doctype, doc.workflow_state)
        
        # Get who made the change
        user_name = frappe.get_value("User", frappe.session.user, "full_name") or frappe.session.user
        
        # Prepare confirmation message
        message = prepare_confirmation_message_for_chatbot(doc, workflow_config, user_name)
        
        # Send confirmation using chatbot's messaging system
        for approver in approvers:
            send_message(approver['mobile'], message)
        
    except Exception as e:
        frappe.logger().error(f"Workflow confirmation failed: {str(e)}")

# ======================== WORKFLOW HELPER FUNCTIONS ========================
def get_workflow_config(doctype):
    """Check if WhatsApp workflow is enabled for this doctype - CORRECTED"""
    try:
        config = frappe.get_value(
            "WhatsApp Workflow Configuration",
            {"document_type": doctype, "enabled": 1},  # Fixed: use 'document_type' instead of 'doctype'
            ["name", "notification_states", "confirmation_states", "message_template", "include_amount_field", "amount_field"]
        )
        
        if config:
            result = {
                "name": config[0],
                "notification_states": (config[1] or "").split('\n'),
                "confirmation_states": (config[2] or "").split('\n'),
                "message_template": config[3],
                "include_amount_field": config[4],
                "amount_field": config[5]
            }
            return result
        return None
        
    except Exception as e:
        frappe.logger().error(f"Error getting workflow config: {str(e)}")
        return None

def should_send_notification(doc, workflow_config):
    """Check if notification should be sent based on state change"""
    try:
        if not hasattr(doc, 'workflow_state') or not doc.workflow_state:
            return False
        
        # Check if current state requires notification
        if doc.workflow_state not in workflow_config['notification_states']:
            return False
        
        # Check if state actually changed to avoid duplicate notifications
        if hasattr(doc, '_doc_before_save') and doc._doc_before_save:
            previous_state = doc._doc_before_save.workflow_state
            if previous_state == doc.workflow_state:
                return False
        
        return True
        
    except Exception as e:
        frappe.logger().error(f"Error checking notification: {str(e)}")
        return False

def get_workflow_actions_for_chatbot(doctype, current_state):
    """Get workflow actions for chatbot integration"""
    try:
        workflow = frappe.get_value("Workflow", {"document_type": doctype}, "name")
        if not workflow:
            return []
        
        transitions = frappe.get_all(
            "Workflow Transition",
            filters={
                "parent": workflow,
                "state": current_state
            },
            fields=["action", "next_state", "allowed"],
            order_by="idx"
        )
        
        actions = []
        for i, transition in enumerate(transitions, 1):
            actions.append({
                "number": i,
                "action": transition.action,
                "next_state": transition.next_state,
                "allowed_role": transition.allowed
            })
        
        return actions
        
    except Exception as e:
        frappe.logger().error(f"Error getting workflow actions: {str(e)}")
        return []

def prepare_workflow_message_for_chatbot(doc, actions, workflow_config):
    """Prepare workflow message for chatbot system"""
    try:
        site_url = frappe.utils.get_site_url(frappe.local.site)
        doc_url = f"{site_url}/app/{doc.doctype.lower().replace(' ', '-')}/{doc.name}"
        
        # Get amount if configured
        amount_text = ""
        if workflow_config.get('include_amount_field') and workflow_config.get('amount_field'):
            amount_field = workflow_config['amount_field']
            if hasattr(doc, amount_field):
                amount_value = getattr(doc, amount_field)
                currency = getattr(doc, 'currency', frappe.defaults.get_global_default('currency'))
                amount_text = f"Amount: {frappe.utils.fmt_money(amount_value, currency=currency)}\n"
        
        # Use custom template or default
        if workflow_config.get('message_template') and workflow_config['message_template'].strip():
            message_base = workflow_config['message_template']
            message_base = message_base.replace('{doc_name}', doc.name)
            message_base = message_base.replace('{doc_type}', doc.doctype)
            message_base = message_base.replace('{current_state}', doc.workflow_state)
            message_base = message_base.replace('{url}', doc_url)
            
            if hasattr(doc, 'customer'):
                message_base = message_base.replace('{customer}', doc.customer)
            
            if amount_text:
                message_base = message_base.replace('{amount}', amount_text.strip())
        else:
            # Default template
            customer_text = f"Customer: {doc.customer}\n" if hasattr(doc, 'customer') else ""
            date_field = getattr(doc, 'transaction_date', None) or getattr(doc, 'posting_date', None)
            date_text = f"Date: {frappe.utils.formatdate(date_field)}\n" if date_field else ""
            
            message_base = f"""{doc.doctype} APPROVAL REQUIRED

Document: {doc.name}
{customer_text}{amount_text}{date_text}
Link: {doc_url}"""
        
        # Add action options
        if actions:
            message_base += f"\n\nReply with:\n"
            for action in actions:
                message_base += f"{action['number']} - {action['action']}\n"
        
        message_base += "\nERPNext"
        
        return message_base
        
    except Exception as e:
        frappe.logger().error(f"Error preparing workflow message: {str(e)}")
        return f"{doc.doctype} {doc.name} requires attention. Check ERPNext."

def prepare_confirmation_message_for_chatbot(doc, workflow_config, user_name):
    """Prepare confirmation message for chatbot system"""
    try:
        site_url = frappe.utils.get_site_url(frappe.local.site)
        doc_url = f"{site_url}/app/{doc.doctype.lower().replace(' ', '-')}/{doc.name}"
        
        # Get amount if configured
        amount_text = ""
        if workflow_config.get('include_amount_field') and workflow_config.get('amount_field'):
            amount_field = workflow_config['amount_field']
            if hasattr(doc, amount_field):
                amount_value = getattr(doc, amount_field)
                currency = getattr(doc, 'currency', frappe.defaults.get_global_default('currency'))
                amount_text = f"Amount: {frappe.utils.fmt_money(amount_value, currency=currency)}\n"
        
        customer_text = f"Customer: {doc.customer}\n" if hasattr(doc, 'customer') else ""
        
        message = f"""{doc.doctype} {doc.workflow_state}

Document: {doc.name}
{customer_text}{amount_text}Action by: {user_name}

Link: {doc_url}
ERPNext"""
        
        return message
        
    except Exception as e:
        frappe.logger().error(f"Error preparing confirmation message: {str(e)}")
        return f"{doc.doctype} {doc.name} status updated to {doc.workflow_state}"

def get_workflow_approvers(doctype, workflow_state):
    """Get all users who can perform actions from current workflow state"""
    try:
        workflow = frappe.get_value("Workflow", {"document_type": doctype}, "name")
        if not workflow:
            return []
        
        # Get all transitions from current state
        transitions = frappe.get_all(
            "Workflow Transition",
            filters={
                "parent": workflow,
                "state": workflow_state
            },
            fields=["allowed"]
        )
        
        # Extract unique allowed roles
        allowed_roles = list(set([t.allowed for t in transitions if t.allowed]))
        
        if not allowed_roles:
            return []
        
        # Get users with mobile numbers
        approvers = []
        processed_users = set()
        
        for role in allowed_roles:
            role_users = frappe.get_all(
                "Has Role",
                filters={"role": role},
                fields=["parent as user"]
            )
            
            for role_user in role_users:
                if role_user.user in processed_users:
                    continue
                
                processed_users.add(role_user.user)
                
                # Try Employee first, then User mobile
                mobile = None
                name = None
                
                employee_data = frappe.get_value(
                    "Employee",
                    {"user_id": role_user.user},
                    ["cell_number", "employee_name"]
                )
                
                if employee_data and employee_data[0]:
                    mobile = employee_data[0]
                    name = employee_data[1]
                else:
                    user_data = frappe.get_value(
                        "User",
                        role_user.user,
                        ["mobile_no", "full_name"]
                    )
                    if user_data and user_data[0]:
                        mobile = user_data[0]
                        name = user_data[1]
                
                if mobile:
                    approvers.append({
                        "user": role_user.user,
                        "name": name or role_user.user,
                        "mobile": mobile,
                        "role": role
                    })
        
        return approvers
        
    except Exception as e:
        frappe.logger().error(f"Error getting approvers: {str(e)}")
        return []

def find_user_by_mobile_for_workflow(mobile_number):
    """Find user by mobile number for workflow actions - IMPROVED"""
    try:
        # Clean mobile number - remove all non-digits except +
        mobile = str(mobile_number).replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Try different variations
        mobile_variations = [
            mobile,
            mobile.replace('+', ''),
            mobile[-10:] if len(mobile) >= 10 else mobile,  # Last 10 digits
            mobile[-9:] if len(mobile) >= 9 else mobile,    # Last 9 digits
        ]
        
        frappe.log_error(f"Searching for mobile variations: {mobile_variations}", "Mobile Search Debug")
        
        # Try Employee first
        for mobile_var in mobile_variations:
            employee = frappe.get_value(
                "Employee",
                {"cell_number": ["like", f"%{mobile_var}%"]},
                "user_id"
            )
            
            if employee:
                frappe.log_error(f"Found user via Employee: {employee}", "User Found Employee")
                return employee
        
        # Try User table
        for mobile_var in mobile_variations:
            user = frappe.get_value(
                "User",
                {"mobile_no": ["like", f"%{mobile_var}%"]},
                "name"
            )
            
            if user:
                frappe.log_error(f"Found user via User table: {user}", "User Found User Table")
                return user
        
        frappe.log_error(f"No user found for mobile {mobile_number}", "User Not Found")
        return None
        
    except Exception as e:
        frappe.log_error(f"Error finding user by mobile: {str(e)}", "User Lookup Error")
        return None

def get_pending_documents_for_user_workflow(user):
    """Get pending workflow documents for user - CORRECTED VERSION"""
    try:
        # Get all enabled workflow configurations
        configs = frappe.get_all(
            "WhatsApp Workflow Configuration",
            filters={"enabled": 1},
            fields=["name", "document_type", "notification_states"]  # Fixed: use 'document_type' instead of 'doctype'
        )
        
        if not configs:
            frappe.log_error(f"No workflow configurations found", "Workflow Config Debug")
            return []
        
        pending_docs = []
        user_roles = frappe.get_roles(user)
        
        frappe.log_error(f"User {user} has roles: {user_roles}", "User Roles Debug")
        
        for config in configs:
            doctype = config.document_type  # Fixed: use document_type
            notification_states = [s.strip() for s in (config.notification_states or "").split('\n') if s.strip()]
            
            frappe.log_error(f"Checking {doctype} with states: {notification_states}", "Workflow States Debug")
            
            # Get workflow for this doctype
            workflow = frappe.get_value("Workflow", {"document_type": doctype}, "name")
            if not workflow:
                frappe.log_error(f"No workflow found for {doctype}", "Workflow Missing")
                continue
            
            for state in notification_states:
                # Get allowed roles for this state
                allowed_roles = frappe.get_all(
                    "Workflow Transition",
                    filters={
                        "parent": workflow,
                        "state": state
                    },
                    fields=["allowed"],
                    pluck="allowed"
                )
                
                frappe.log_error(f"State {state} allows roles: {allowed_roles}", "Allowed Roles Debug")
                
                # Check if user has any allowed role
                has_permission = any(role in user_roles for role in allowed_roles if role)
                
                if has_permission:
                    # Get documents in this state
                    docs = frappe.get_all(
                        doctype,
                        filters={"workflow_state": state},
                        fields=["name", "modified", "workflow_state"],
                        order_by="modified desc",
                        limit=20  # Limit to avoid too many results
                    )
                    
                    frappe.log_error(f"Found {len(docs)} documents in state {state}", "Documents Found")
                    
                    for doc_data in docs:
                        pending_docs.append({
                            "doctype": doctype,
                            "name": doc_data.name,
                            "modified": doc_data.modified,
                            "state": doc_data.workflow_state
                        })
        
        # Sort by modified date (most recent first)
        pending_docs.sort(key=lambda x: x['modified'], reverse=True)
        
        frappe.log_error(f"Total pending docs for user {user}: {len(pending_docs)}", "Total Pending")
        return pending_docs
        
    except Exception as e:
        frappe.log_error(f"Error getting pending documents: {str(e)}", "Pending Docs Error")
        return []


# ======================== DIAGNOSTIC FUNCTIONS ========================
@frappe.whitelist()
def check_items_debug():
    """Check what items are available in the system"""
    try:
        total_items = frappe.db.count("Item")
        sales_items = frappe.db.count("Item", filters={"is_sales_item": 1, "disabled": 0})
        items_with_price = frappe.db.count("Item", filters={
            "is_sales_item": 1, 
            "disabled": 0,
            "standard_rate": [">", 0]
        })
        
        sample_items = frappe.get_all(
            "Item",
            filters={"disabled": 0, "is_sales_item": 1},
            fields=["name", "item_name", "standard_rate", "stock_uom", "disabled", "is_sales_item"],
            limit=10
        )
        
        return {
            "total_items": total_items,
            "sales_items": sales_items,
            "items_with_price": items_with_price,
            "sample_items": sample_items
        }
        
    except Exception as e:
        return {"error": str(e)}

@frappe.whitelist()
def create_test_items():
    """Create test items for the chatbot"""
    try:
        test_items = [
            {"item_name": "Test Rice 5kg", "standard_rate": 15000, "stock_uom": "Kg"},
            {"item_name": "Test Sugar 2kg", "standard_rate": 8000, "stock_uom": "Kg"},
            {"item_name": "Test Cooking Oil 2L", "standard_rate": 12000, "stock_uom": "Litre"},
            {"item_name": "Test Bread Loaf", "standard_rate": 3000, "stock_uom": "Nos"},
            {"item_name": "Test Fresh Milk 1L", "standard_rate": 5000, "stock_uom": "Litre"}
        ]
        
        created_items = []
        
        for item_data in test_items:
            if frappe.db.exists("Item", {"item_name": item_data["item_name"]}):
                continue
                
            item = frappe.new_doc("Item")
            item.item_name = item_data["item_name"]
            item.item_code = item_data["item_name"].replace(" ", "_").upper()
            item.item_group = "Products"
            item.stock_uom = item_data["stock_uom"]
            item.is_sales_item = 1
            item.is_stock_item = 1
            item.standard_rate = item_data["standard_rate"]
            item.disabled = 0
            
            try:
                item.flags.ignore_permissions = True
                item.insert(ignore_permissions=True)
                created_items.append(item.name)
            except Exception as e:
                frappe.log_error(f"Failed to create {item.item_name}: {str(e)}", "Item Creation Error")
        
        frappe.db.commit()
        
        return {
            "status": "success",
            "created_items": created_items,
            "message": f"Created {len(created_items)} test items"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def test_chatbot(phone_number):
    """Test the chatbot - UNCHANGED"""
    try:
        phone_number = str(phone_number).replace('+', '')
        
        # Reset and start
        reset_and_start(phone_number)
        
        return {
            "status": "success",
            "message": f"Test message sent to +{phone_number}. Check WhatsApp and reply with a number!"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def debug_user_state(phone_number):
    """Debug user state - UNCHANGED"""
    try:
        phone_number = str(phone_number).replace('+', '')
        
        state = get_user_state(phone_number)
        cart = get_temp_data(phone_number, "cart") or []
        customer_name = get_temp_data(phone_number, "customer_name")
        
        return {
            "phone_number": phone_number,
            "current_state": state,
            "cart_items": len(cart),
            "customer_name": customer_name,
            "cart_details": cart
        }
        
    except Exception as e:
        return {"error": str(e)}
