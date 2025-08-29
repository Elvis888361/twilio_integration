import frappe
from twilio.rest import Client
import json
from datetime import datetime, timedelta

# Configuration
twilio_settings = frappe.get_doc("whatsapp integration settings")
STATIC_TWILIO_SID = twilio_settings.twilio_sid
STATIC_TWILIO_TOKEN = twilio_settings.twilio_token
STATIC_WHATSAPP_FROM = twilio_settings.twilio_number

@frappe.whitelist(allow_guest=True)
def handle_whatsapp_chatbot():
    """Main webhook handler for WhatsApp chatbot"""
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
        
        # Process message
        process_message(from_number, message_body)
        return "OK"
        
    except Exception as e:
        frappe.log_error(f"Chatbot error: {str(e)}", "Chatbot Error")
        return "Error"

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
        send_message(phone_number, "❌ Error occurred. Restarting...")
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
            msg = """📞 *CONTACT SUPPORT*

Phone: +256-XXX-XXXXXX
Email: support@store.com
Hours: 8AM - 6PM

Type *0* to return to main menu."""
            send_message(phone_number, msg)
        elif choice == 3:
            # About us
            msg = """ℹ️ *ABOUT US*

Your trusted online store!
✅ Quality products
✅ Fast delivery
✅ 24/7 WhatsApp ordering

Type *0* to return to main menu."""
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

Type 1 or 2:"""
    
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

Type *0* to go back to main menu."""
            
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
            msg += f"*{i}* - {item['item_name']}\n     💰 {price_text} per {uom}\n\n"
        
        msg += "Type item number (1-5):"
        
        # Save items for reference
        save_temp_data(phone_number, "current_items", items[:5])
        set_user_state(phone_number, "ITEMS_BROWSE")
        
        frappe.log_error(f"Sending items menu to {phone_number}", "Items Menu Sent")
        send_message(phone_number, msg)
        
    except Exception as e:
        frappe.log_error(f"Items menu error: {str(e)}", "Items Menu Error")
        send_message(phone_number, "❌ Error loading items. Type *0* to go back to main menu.")
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
        send_message(phone_number, "🛒 Your cart is empty!")
        show_items_menu(phone_number)
        return
    
    total = 0
    msg = "🛒 *YOUR CART*\n\n"
    
    for i, item in enumerate(cart, 1):
        total += item['total']
        msg += f"{i}. {item['item_name']}\n"
        msg += f"   {item['qty']} × {item['rate']:,.0f} = {item['total']:,.0f} UGX\n\n"
    
    msg += f"💰 *TOTAL: {total:,.0f} UGX*\n\n"
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

Type *0* to start a new order."""
                
                # Clear cart and reset
                clear_user_data(phone_number)
                send_message(phone_number, msg)
            else:
                send_message(phone_number, "❌ Error placing order. Please try again.")
                
        elif choice == 2:
            # Continue shopping
            show_items_menu(phone_number)
        else:
            send_message(phone_number, "❌ Please choose 1 or 2")
            
    except ValueError:
        send_message(phone_number, "❌ Please enter 1 or 2")

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

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
            {"name": "TEST005", "item_name": "Test Milk 1L", "standard_rate": 4000, "stock_uom": "Litre"}
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

# =============================================================================
# DIAGNOSTIC FUNCTIONS
# =============================================================================

@frappe.whitelist()
def check_items_debug():
    """Check what items are available in the system"""
    try:
        # Count all items
        total_items = frappe.db.count("Item")
        
        # Count sales items
        sales_items = frappe.db.count("Item", filters={"is_sales_item": 1, "disabled": 0})
        
        # Count items with prices
        items_with_price = frappe.db.count("Item", filters={
            "is_sales_item": 1, 
            "disabled": 0,
            "standard_rate": [">", 0]
        })
        
        # Get sample items
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
            # Check if item already exists
            if frappe.db.exists("Item", {"item_name": item_data["item_name"]}):
                continue
                
            # Create new item
            item = frappe.new_doc("Item")
            item.item_name = item_data["item_name"]
            item.item_code = item_data["item_name"].replace(" ", "_").upper()
            item.item_group = "Products"  # Default group
            item.stock_uom = item_data["stock_uom"]
            item.is_sales_item = 1
            item.is_stock_item = 1
            item.standard_rate = item_data["standard_rate"]
            item.disabled = 0
            
            try:
                item.flags.ignore_permissions = True
                item.insert(ignore_permissions=True)
                created_items.append(item.name)
                frappe.log_error(f"Created test item: {item.name}", "Test Item Created")
            except Exception as e:
                frappe.log_error(f"Failed to create {item.item_name}: {str(e)}", "Item Creation Error")
        
        frappe.db.commit()
        
        return {
            "status": "success",
            "created_items": created_items,
            "message": f"Created {len(created_items)} test items"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def test_chatbot(phone_number):
    """Test the simplified chatbot"""
    try:
        phone_number = str(phone_number).replace('+', '')
        
        # Reset and start
        reset_and_start(phone_number)
        
        return {
            "status": "success",
            "message": f"Test message sent to +{phone_number}. Check WhatsApp and reply with a number!"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def debug_user_state(phone_number):
    """Debug user state"""
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
