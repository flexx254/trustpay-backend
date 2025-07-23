import bcrypt
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
import os
import re

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

@app.route('/add-product', methods=['POST'])
def add_product():
    data = request.get_json()
    user_id = data.get('user_id')
    product_name = data.get('product_name')
    amount = data.get('amount')

    if not all([user_id, product_name, amount]):
        return jsonify({"error": "Missing fields"}), 400

    try:
        response = supabase.table('products').insert({
            "user_id": user_id,
            "product_name": product_name,
            "amount": amount
        }).execute()
        return jsonify({"message": "Product added successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/products', methods=['GET'])
def get_products():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        response = supabase.table('products').select('*').eq('user_id', user_id).order('id', desc=True).execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/product-details', methods=['GET'])
def product_details():
    product_id = request.args.get('product_id')
    if not product_id:
        return jsonify({"error": "Product ID is required"}), 400

    try:
        response = supabase.table('products').select('*').eq('id', product_id).single().execute()
        if response.data:
            return jsonify(response.data), 200
        else:
            return jsonify({"error": "Product not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ FIXED: correctly placed update-payment route


@app.route('/update-payment', methods=['POST'])
def update_payment():
    data = request.get_json()
    product_id = data.get('product_id')
    buyer_name = data.get('buyer_name')
    buyer_email = data.get('buyer_email')
    mpesa_number = data.get('mpesa_number')
    paid = True

    if not all([product_id, buyer_name, buyer_email, mpesa_number]):
        return jsonify({"error": "Missing fields"}), 400

    try:
        response = supabase.table('products').update({
            "buyer_name": buyer_name,
            "buyer_email": buyer_email,
            "mpesa_number": mpesa_number,
            "paid": paid
        }).eq('id', product_id).execute()

        return jsonify({"message": "Payment updated"}), 200
    except Exception as e:
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



@app.route('/check-payment', methods=['POST'])
def check_payment():
    data = request.get_json()
    product_id = data.get("product_id")

    if not product_id:
        return jsonify({"error": "Product ID is required"}), 400

    try:
        # Step 1: Get the product and its mpesa_number
        product_res = supabase.table("products").select("*").eq("id", product_id).single().execute()
        product = product_res.data

        if not product:
            return jsonify({"error": "Product not found"}), 404

        buyer_mpesa_number = product.get("mpesa_number")
        if not buyer_mpesa_number:
            return jsonify({"error": "No mpesa_number found for product"}), 400

        # Step 2: Search recent messages
        messages_res = supabase.table("sms_messages").select("*").order("id", desc=True).limit(20).execute()
        messages = messages_res.data

        # Step 3: Extract phone numbers from each message and compare
        def extract_phone(message):
            match = re.search(r'\+?\d{10,15}', message)
            return match.group() if match else None

        for sms in messages:
            phone_in_sms = extract_phone(sms.get("message", ""))
            if phone_in_sms and phone_in_sms.strip() == buyer_mpesa_number.strip():
                return jsonify({"match": True, "message": "Payment confirmed."}), 200

        # If no match
        return jsonify({"match": False, "message": "Payment not yet detected."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


                            
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
