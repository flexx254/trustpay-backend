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
def login(): I
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
@app.route('/add-product', methods=['POST'])
def add_product():
    data = request.get_json()
    user_id = data.get('user_id')
    product_name = data.get('product_name')
    amount = data.get('amount')

    if not all([user_id, product_name, amount]):
        return jsonify({"error": "Missing fields"}), 400

    try:
        # Insert product without trying to select
        insert_response = supabase.table('products').insert({
            "user_id": user_id,
            "product_name": product_name,
            "amount": amount
        }).execute()

        # Now fetch the latest inserted product for this user
        query_response = supabase.table('products') \
            .select("*") \
            .eq("user_id", user_id) \
            .order("id", desc=True) \
            .limit(1) \
            .execute()

        inserted_product = query_response.data[0] if query_response.data else None

        if inserted_product:
            return jsonify({
                "message": "Product added successfully!",
                "id": inserted_product["id"]
            }), 200
        else:
            return jsonify({"error": "Could not retrieve inserted product"}), 50

    except Exception as e:
        return jsonify({"error": str(e)}), 500

from datetime import datetime
from flask import request, jsonify
@app.route('/products', methods=['GET'])
def get_products():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    def status_priority(status):
        return {
            "paid-released": 0,
            "paid-held": 1
        }.get(status, 2)

    def parse_ts(ts):
        if not ts:
            return datetime.min
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return datetime.min

    try:
        # ✅ Fetch products only for this user (seller)
        response = supabase.table("products").select("*").eq("user_id", user_id).execute()
        products = response.data or []

        # ✅ Sort by latest timestamp
        sorted_products = sorted(products, key=lambda p: parse_ts(p.get("timestampz")), reverse=True)

        # ✅ Load SMS messages once for M-Pesa extraction
        sms_response = supabase.table("sms_messages").select("message").order("timestampz", ascending=True).execute()
        sms_messages = [sms["message"] for sms in sms_response.data] if sms_response.data else []

        def extract_paid_amount(msisdn):
            if not msisdn:
                return None
            msisdn = str(msisdn)
            suffix = msisdn[-9:]
            for msg in reversed(sms_messages):
                if suffix in msg and "Ksh" in msg:
                    try:
                        after_ksh = msg.split("Ksh")[1].strip()
                        amount_str = after_ksh.split(" ")[0].replace(",", "")
                        return float(amount_str)
                    except Exception as e:
                        print("Error parsing message:", msg, e)
                        continue
            return None

        result = []
        for product in sorted_products:
            paid_amount = extract_paid_amount(product.get("mpesa_number", ""))
            try:
                amt = float(product.get("amount", 0))
                balance = round(paid_amount - amt, 2) if paid_amount is not None else None
            except Exception as e:
                print("Error calculating balance for product:", product.get("id", "unknown"), e)
                balance = None

            result.append({
                "id": product["id"],  # ✅ Use correct UUID field
                "product_name": product["product_name"],
                "amount": product["amount"],
                "status": product.get("status", "pending"),
                "buyer_name": product.get("buyer_name"),
                "mpesa_number": product.get("mpesa_number"),
                "amount_paid": paid_amount,
                "balance": balance
            })

        return jsonify(result), 200

    except Exception as e:
        print("Server error:", e)
        return jsonify({"error": str(e)}), 500
@app.route('/update-payment', methods=['POST'])
def update_payment():
    data = request.get_json()
    product_id = data.get('product_id')
    buyer_name = data.get('buyer_name')
    buyer_email = data.get('buyer_email')
    mpesa_number = data.get('mpesa_number')

    if not product_id or not mpesa_number:
        return jsonify({"message": "Missing product ID or phone number"}), 400

    mpesa_number = normalize_number(mpesa_number)

    try:
        original = supabase.table("products").select("*").eq("id", product_id).single().execute()
        if not original.data:
            return jsonify({"message": "Product not found"}), 404

        original_product = original.data

        new_data = {
            "product_name": original_product["product_name"],
            "amount": original_product["amount"],
            "user_id": original_product["user_id"],
            "buyer_name": buyer_name,
            "buyer_email": buyer_email,
            "mpesa_number": mpesa_number,
            "paid": False,
            "status": "pending",
            "timestampz": datetime.utcnow().isoformat()
        }

        supabase.table("products").insert(new_data).execute()

        return jsonify({"message": "Payment info submitted successfully."}), 200
    except Exception as e:
        print("Error in update-payment:", e)
        return jsonify({"message": "Error submitting payment info."}), 500

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
