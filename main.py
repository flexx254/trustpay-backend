from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
import os

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
    password = data.get('password')

    # Insert into Supabase 'users' table
    try:
        response = supabase.table('users').insert({
            "full_name": full_name,
            "business_name": business_name,
            "email": email,
            "phone": phone,
            "password": password  # Remember to hash this later for security
        }).execute()
        
        return jsonify({"message": "Account created successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
