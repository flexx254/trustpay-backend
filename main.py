import bcrypt
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from supabase import create_client, Client
import os
import re
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def send_email(to_email, subject, body):
    """
    Send an email using SendGrid API
    """
    try:
        message = Mail(
            from_email="felixmoseti254@gmail.com",  # your verified SendGrid sender
            to_emails=to_email,
            subject=subject,
            html_content=body
        )

        sg = SendGridAPIClient(os.environ.get("trustpay-api-key"))
        response = sg.send(message)
        print(f"📧 Email sent to {to_email} | Status: {response.status_code}")
    except Exception as e:
        print("❌ SendGrid error:", e)

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

import secrets

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
        status = data.get("status", "Not paid")

        # ✅ Validate required fields
        if not user_id or not product_name or not amount or not buyer_name or not buyer_email or not mpesa_number:
            return jsonify({"error": "Missing required fields"}), 400

        # ✅ Normalize phone number
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

        # ✅ Generate secure token
        auth_token = secrets.token_hex(16)  # 32-char random hex string

        # ✅ Insert payment into payments table
        insert_response = supabase.table("payments").insert({
            "user_id": user_id,
            "product_name": product_name,
            "amount": amount,
            "buyer_name": buyer_name,
            "buyer_email": buyer_email,
            "mpesa_number": normalized_mpesa,
            "status": "Not paid",
            "paid": False,
            "amount_paid": 0,
            "auth_token": auth_token,   # <-- store token
            "timestampz": datetime.utcnow().isoformat()
        }).execute()

        if insert_response.data:
            return jsonify({
                "message": "Payment created successfully",
                "payment": insert_response.data[0],
                "token": auth_token    # <-- return token
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

        return jsonify({"status": "SMS stoed"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

                        
@app.route("/check-payment", methods=["POST"])
def check_payment():
    data = request.get_json()
    mpesa_number = data.get("mpesa_number")
    payment_id = data.get("payment_id")  # from bal.html
    auth_token = data.get("auth_token")  # ✅ new for secure check

    if not mpesa_number and not payment_id:
        return jsonify({"error": "M-Pesa number or Payment ID is required"}), 400

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

    normalized_number = normalize_number(mpesa_number) if mpesa_number else None
    print("🔍 Normalized number:", normalized_number)

    try:
        # 1️⃣ Secure lookup first: by ID + token
        if payment_id and auth_token:
            payment_response = (
                supabase.table("payments")
                .select("*")
                .eq("id", payment_id)
                .eq("auth_token", auth_token)  # ✅ enforce token check
                .single()
                .execute()
            )
            payment_data = [payment_response.data] if payment_response.data else []

        # 2️⃣ Fallback lookup: by ID only (for older bal.html links)
        elif payment_id:
            payment_response = (
                supabase.table("payments")
                .select("*")
                .eq("id", payment_id)
                .single()
                .execute()
            )
            payment_data = [payment_response.data] if payment_response.data else []

        # 3️⃣ Legacy fallback: by phone number (pay.html flow)
        else:
            payment_response = (
                supabase.table("payments")
                .select("*")
                .eq("mpesa_number", normalized_number)
                .eq("paid", False)
                .order("timestampz", desc=True)
                .limit(1)
                .execute()
            )
            payment_data = payment_response.data

        print("📦 Matching unpaid payment:", payment_data)

        if not payment_data:
            return jsonify({
                "paid": False,
                "message": "No unpaid payment found for this request"
            }), 200

        payment = payment_data[0]
        payment_id = payment["id"]
        expected_amount = float(payment.get("amount", 0))
        buyer_email = payment.get("buyer_email")
        buyer_name = payment.get("buyer_name")
        product_name = payment.get("product_name")

        # 4️⃣ Match latest unused SMS
        message_response = (
            supabase.table("sms_messages")
            .select("*")
            .like("message", f"%{normalized_number[-9:]}%")
            .eq("used", False)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )

        if message_response.data:
            sms_row = message_response.data[0]
            sms_id = sms_row["id"]
            matched_msg = sms_row["message"]
            print("📨 Matched SMS:", matched_msg)

            # Extract amount
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
            print("💰 Extracted amount:", paid_amount)

            # Mark SMS as used
            supabase.table("sms_messages").update({"used": True}).eq("id", sms_id).execute()

            # Update payment
            update_data = {"paid": True, "status": "paid-held"}
            if paid_amount is not None:
                old_paid = float(payment.get("amount_paid", 0))
                new_total_paid = old_paid + paid_amount
                update_data["amount_paid"] = new_total_paid
            else:
                new_total_paid = float(payment.get("amount_paid", 0))

            supabase.table("payments").update(update_data).eq("id", payment_id).execute()

            # Email handling
            if buyer_email:
                if new_total_paid < expected_amount:
                    balance = expected_amount - new_total_paid
                    subject = "Partial Payment Received"
                    body = f"""
                    <html>
                      <body>
                        <p>Hello {buyer_name},</p>
                        <p>We have received <b>KES {new_total_paid}</b> for <b>{product_name}</b>, 
                        but the expected amount was KES {expected_amount}.</p>
                        <p>You still owe <b>KES {balance}</b>.</p>
                        <p>
                          <a href="https://trustpay-backend.onrender.com/pay-balance/{payment_id}"
                             style="padding:10px 20px; background-color:orange; color:white; text-decoration:none; border-radius:5px;">
                             💳 Pay Balance
                          </a>
                        </p>
                        <p>Thank you,<br>TrustPay Team</p>
                      </body>
                    </html>
                    """
                    send_email(buyer_email, subject, body)
                else:
                    from hashlib import sha256
                    import hmac
                    SECRET_KEY = os.environ.get("SECRET_KEY", "supersecret")

                    def generate_secure_token(payment_id: str):
                        return hmac.new(
                            SECRET_KEY.encode(),
                            str(payment_id).encode(),
                            sha256
                        ).hexdigest()

                    token = generate_secure_token(str(payment_id))
                    confirm_url = f"https://trustpay-backend.onrender.com/confirm-delivery/{payment_id}/{token}"

                    subject = "Confirm Delivery"
                    body = f"""
                    <html>
                      <body>
                        <p>Hello {buyer_name},</p>
                        <p>Your full payment of <b>KES {new_total_paid}</b> for <b>{product_name}</b> has been received and is being held safely.</p>
                        <p>Please confirm you have received your product:</p>
                        <a href="{confirm_url}"
                           style="padding:10px 20px; background-color:green; color:white; text-decoration:none; border-radius:5px;">
                           ✅ Confirm Delivery
                        </a>
                        <p>Once confirmed, your seller will receive the funds.</p>
                        <br>
                        <p>Thank you,<br>TrustPay Team</p>
                      </body>
                    </html>
                    """
                    send_email(buyer_email, subject, body)

            return jsonify({
                "paid": True,
                "message": "Payment confirmed (held), email sent to buyer",
                "amount_paid": new_total_paid
            }), 200

        else:
            return jsonify({
                "paid": False,
                "message": "No matching unused payment message found yet"
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

# ===================== PRODUCTS.HTML ROUTE =====================
@app.route('/products-page', methods=['GET'])
def get_products_page():
    """
    Specil route used ONLY for products.html.
    Returns the product list for a given user_id
    without touching payments table.
    """
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400

        # Fetch products created by this user
        response = (
            supabase.table('products')
            .select('id, product_name, amount, user_id, status')
            .eq('user_id', user_id)
            .execute()
        )

        return jsonify(response.data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
@app.route('/buyer-transactions', methods=['GET'])
def get_buyer_transactions():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400

        response = (
            supabase.table('payments')
            .select('id, product_name, amount, buyer_name, mpesa_number, amount_paid, status, user_id')
            .eq('user_id', user_id)
            .execute()
        )

        return jsonify(response.data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



from hashlib import sha256
import hmac

@app.route("/confirm-delivery/<payment_id>/<token>", methods=["GET"])
def confirm_delivery(payment_id, token):
    try:
        SECRET_KEY = os.environ.get("SECRET_KEY", "supersecret")

        # 🔐 Verify token
        expected_token = hmac.new(
            SECRET_KEY.encode(),
            str(payment_id).encode(),
            sha256
        ).hexdigest()

        if token != expected_token:
            return "❌ Invalid or expired confirmation link.", 400

        # ✅ Update payment status to paid-released
        supabase.table("payments").update({
            "status": "paid-released"
        }).eq("id", payment_id).execute()

        return """
        <html>
          <body style="font-family: Arial; text-align:center; margin-top:50px;">
            <h2>✅ Delivery Confirmed</h2>
            <p>Your delivery has been confirmed successfully. Funds have been released to the seller.</p>
            <p>Thank you for using <b>TrustPay</b>!</p>
          </body>
        </html>
        """, 200

    except Exception as e:
        print("❌ Error in confirm-delivery:", e)
        return "An error occurred while confirming delivery.", 500


@app.route("/pay-balance/<payment_id>", methods=["GET"])
def pay_balance(payment_id):
    try:
        # Check if payment exists
        payment = supabase.table("payments").select("id").eq("id", payment_id).single().execute()
        if not payment.data:
            return "❌ Payment not found", 404

        # Redirect to your frontend bal.html with payment_id
        return redirect(f"https://flexx254.github.io/trustpay-frontend/bal.html?payment_id={payment_id}")
    except Exception as e:
        print("❌ Error in pay-balance:", e)
        return "An error occurred while loading balance payment page.", 500

@app.route("/release-payment/<payment_id>", methods=["POST"])
def release_payment(payment_id):
    try:
        supabase.table("payments").update({
            "status": "paid-released"
        }).eq("id", payment_id).execute()

        return jsonify({"message": "✅ Payment released successfully"}), 200
    except Exception as e:
        print("❌ Error in release-payment:", e)
        return jsonify({"error": "Could not release payment"}), 500

@app.route("/get-payment/<payment_id>", methods=["GET"])
def get_payment(payment_id):
    try:
        response = supabase.table("payments").select("*").eq("id", payment_id).single().execute()
        if response.data:
            return jsonify(response.data), 200
        else:
            return jsonify({"error": "Payment not found"}), 404
    except Exception as e:
        print("❌ Error in get-payment:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/update-balance/<payment_id>", methods=["POST"])
def update_balance(payment_id):
    try:
        data = request.get_json()
        extra_paid = float(data.get("amount_paid", 0))

        # Fetch payment first
        payment = supabase.table("payments").select("*").eq("id", payment_id).single().execute()
        if not payment.data:
            return jsonify({"error": "Payment not found"}), 404

        payment_data = payment.data
        buyer_email = payment_data.get("buyer_email")
        buyer_name = payment_data.get("buyer_name")
        product_name = payment_data.get("product_name")

        new_total_paid = float(payment_data.get("amount_paid", 0)) + extra_paid
        expected_amount = float(payment_data.get("amount", 0))

        status = "paid-held"
        fully_paid = new_total_paid >= expected_amount
        if fully_paid:
            status = "paid-held"  # fully paid, still held until delivery confirm

        # Update payment row
        supabase.table("payments").update({
            "amount_paid": new_total_paid,
            "paid": fully_paid,
            "status": status
        }).eq("id", payment_id).execute()

        # ✅ If fully paid → send Confirm Delivery email
        if fully_paid and buyer_email:
            from hashlib import sha256
            import hmac

            SECRET_KEY = os.environ.get("SECRET_KEY", "supersecret")

            def generate_secure_token(payment_id: str):
                return hmac.new(
                    SECRET_KEY.encode(),
                    str(payment_id).encode(),
                    sha256
                ).hexdigest()

            token = generate_secure_token(str(payment_id))
            confirm_url = f"https://trustpay-backend.onrender.com/confirm-delivery/{payment_id}/{token}"

            subject = "Confirm Delivery"
            body = f"""
            <html>
              <body>
                <p>Hello {buyer_name},</p>
                <p>Your payment of KES {new_total_paid} for <b>{product_name}</b> has now been fully received and is being held safely.</p>
                <p>Please confirm you have received your product:</p>
                <a href="{confirm_url}"
                   style="padding:10px 20px; background-color:green; color:white; text-decoration:none; border-radius:5px;">
                   ✅ Confirm Delivery
                </a>
                <p>Once confirmed, your seller will receive the funds.</p>
                <br>
                <p>Thank you,<br>TrustPay Team</p>
              </body>
            </html>
            """
            send_email(buyer_email, subject, body)

        return jsonify({
            "message": "Balance updated successfully",
            "new_amount_paid": new_total_paid,
            "status": status,
            "confirm_email_sent": fully_paid
        }), 200

    except Exception as e:
        print("❌ Error in update-balance:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/update-payment/<payment_id>", methods=["POST"])
def update_payment(payment_id):
    try:
        data = request.json
        mpesa_number = data.get("mpesa_number")

        # Fetch current payment row
        payment = supabase.table("payments").select("*").eq("id", payment_id).single().execute()
        if not payment.data:
            return jsonify({"error": "Payment not found"}), 404

        current_paid = payment.data.get("amount_paid", 0)
        total_amount = payment.data["amount"]

        # Calculate new paid amount (assume full balance is settled)
        new_paid = total_amount
        status = "paid-held" if new_paid >= total_amount else "held"

        # Update row
        updated = supabase.table("payments").update({
            "amount_paid": new_paid,
            "status": status,
            "mpesa_number": mpesa_number
        }).eq("id", payment_id).execute()

        return jsonify(updated.data[0]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/debug_sendgrid")
def debug_sendgrid():
    import time
    start = time.time()
    try:
        send_email("your-test-email@example.com", "SendGrid Test", "<p>✅ SendGrid working!</p>")
        return f"✅ SendGrid connected and email sent in {round(time.time() - start, 2)}s"
    except Exception as e:
        return f"⚠️ SendGrid error: {e}"
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
