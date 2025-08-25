import bcrypt
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
import os
import re
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Get Supabase credentials from environment
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    full_name = data.get('fullName')
    business_name = data.get('businessName')
    email = data.get('email')
    phone = data.get('phone')
    raw_password = data.get('password')
    hashed_password = bcrypt.hashpw(raw_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    try:
        response = supabase.table('users').insert({
            "full_name": full_name,
            "business_name": business_name,
            "email": email,
            "phone": phone,
            "password": hashed_password
        }).execute()
        return jsonify({"message": "Account created successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/login', methods=['POST'])
def login(): 
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    try:
        response = supabase.table('users').select('*').eq('email', email).execute()
        users = response.data

        if not users:
            return jsonify({"error": "Invalid email or password."}), 401

        user = users[0]
        stored_hash = user['password']

        if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            return jsonify({
                "message": f"Welcome, {user['full_name']}!",
                "user_id": user['id'],
                "full_name": user['full_name']
            }), 200
        else:
            return jsonify({"error": "Invalid email or password."}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ===================== ADD PRODUCT ROUTE =====================
@app.route('/add-product', methods=['POST'])
def add_product():
    try:
        data = request.json
        user_id = data.get("user_id")
        product_name = data.get("product_name")
        amount = data.get("amount")

        if not user_id or not product_name or not amount:
            return jsonify({"error": "Missing required fields"}), 400

        # Insert into Supabase
        insert_response = supabase.table("products").insert({
            "user_id": user_id,
            "product_name": product_name,
            "amount": amount,
            "status": "pending"
        }).execute()

        if insert_response.data:
            return jsonify({
                "message": "Product added successfully"
            }), 201
        else:
            return jsonify({"error": "Failed to insert product"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/products', methods=['GET'])
def get_products():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400

        # Fetch only the necsary columns
        response = (
            supabase.table('payments')
            .select('product_name, amount, user_id')
            .eq('user_id', user_id)
            .execute()
        )

        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/create-payment', methods=['POST'])
def create_payment():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        product_name = data.get("product_name")
        amount = data.get("amount")
        buyer_name = data.get("buyer_name")
        buyer_email = data.get("buyer_email")
        mpesa_number = data.get("mpesa_number")
        status = data.get("status", "held")

        # Validate required fields
        if not user_id or not product_name or not amount or not buyer_name or not buyer_email or not mpesa_number:
            return jsonify({"error": "Missing required fields"}), 400

        # Normalize phone number
        def normalize_number(number):
            number = number.strip().replace(" ", "").replace("+", "")
            if number.startswith("0") and len(number) == 10:
                return "254" + number[1:]
            elif number.startswith("7") and len(number) == 9:
                return "254" + number
            elif number.startswith("254") and len(number) == 12:
                return number
            return number

        normalized_mpesa = normalize_number(mpesa_number)

        # Insert payment into payments table
        insert_response = supabase.table("payments").insert({
            "user_id": user_id,
            "product_name": product_name,
            "amount": amount,
            "buyer_name": buyer_name,
            "buyer_email": buyer_email,
            "mpesa_number": normalized_mpesa,
            "status": status,              # default "held"
            "paid": False,                 # starts false
            "amount_paid": 0,              # initially 0
            "timestampz": datetime.utcnow().isoformat()
        }).execute()

        if insert_response.data:
            return jsonify({
                "message": "Payment created successfully",
                "payment": insert_response.data[0]
            }), 201
        else:
            return jsonify({"error": "Failed to create payment"}), 500

    except Exception as e:
        print("❌ Error in create-payment:", e)
        return jsonify({"error": str(e)}), 500



@app.route('/sms', methods=['POST'])
def receive_sms():
    data = request.get_json()
    message = data.get("message")

    if not message:
        return jsonify({"error": "No message provided"}), 400

    try:
        response = supabase.table('sms_messages').insert({
            "message": message
        }).execute()

        return jsonify({"status": "SMS stored"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/check-payment", methods=["POST"])
def check_payment():
    data = request.get_json()
    mpesa_number = data.get("mpesa_number")

    if not mpesa_number:
        return jsonify({"error": "M-Pesa number is required"}), 400

    def normalize_number(number):
        number = number.strip().replace(" ", "").replace("+", "")
        if number.startswith("0") and len(number) == 10:
            return "254" + number[1:]
        elif number.startswith("7") and len(number) == 9:
            return "254" + number
        elif number.startswith("254") and len(number) == 12:
            return number
        return number

    normalized_number = normalize_number(mpesa_number)
    print("🔍 Normalized number:", normalized_number)

    try:
        product_response = (
            supabase.table("products")
            .select("*")
            .eq("mpesa_number", normalized_number)
            .eq("paid", False)
            .limit(1)
            .execute()
        )
        product_data = product_response.data
        print("📦 Matching unpaid product:", product_data)

        if not product_data:
            return jsonify({
                "paid": False,
                "message": "No unpaid product found for this number"
            }), 200

        product = product_data[0]
        product_id = product["id"]

        message_response = (
            supabase.table("sms_messages")
            .select("*")
            .like("message", f"%{normalized_number[-9:]}%")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )

        if message_response.data:
            matched_msg = message_response.data[0]['message']
            print("📨 Matched SMS:", matched_msg)

            def extract_amount_simple(msg):
                if "Ksh" in msg:
                    parts = msg.split("Ksh")
                    if len(parts) > 1:
                        after_ksh = parts[1].strip()
                        amount_str = after_ksh.split(" ")[0].replace(",", "")
                        try:
                            return float(amount_str)
                        except ValueError:
                            return None
                return None

            paid_amount = extract_amount_simple(matched_msg)
            print("💰 Extracted amount (string method):", paid_amount)

            update_data = {
                "paid": True,
                "status": "paid-held"
            }
            if paid_amount is not None:
                update_data["amount_paid"] = paid_amount

            update_response = supabase.table("products").update(update_data).eq("id", product_id).execute()
            print("📝 Update response:", update_response.data)

            return jsonify({
                "paid": True,
                "message": "Payment confirmed and product updated",
                "amount_paid": paid_amount
            }), 200
        else:
            return jsonify({
                "paid": False,
                "message": "No matching payment message found yet"
            }), 200

    except Exception as e:
        print("❌ Error in check-payment:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/check-payment-status', methods=['GET'])
def check_payment_status():
    product_id = request.args.get('product_id')
    if not product_id:
        return jsonify({"error": "Product ID is required"}), 400

    try:
        response = supabase.table('products').select('paid').eq('id', product_id).single().execute()
        if response.data:
            return jsonify({"paid": response.data['paid']}), 200
        else:
            return jsonify({"error": "Product not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
