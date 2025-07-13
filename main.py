from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)  # allow requests from your frontend

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()

    business_name = data.get('businessName')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')

    print("New Signup:")
    print("Business:", business_name)
    print("Email:", email)
    print("Phone:", phone)
    print("Password:", password)

    return jsonify({"message": "Account created successfully!"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
