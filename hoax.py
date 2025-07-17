# hoax.py
import time
import requests
import os
from datetime import datetime

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
TABLE = "hoaxping"

def ping_supabase():
    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "pinged_at": datetime.utcnow().isoformat()
    }

    try:
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/{TABLE}",
            headers=headers,
            json=data
        )
        if response.status_code in [200, 201]:
            print("✅ Supabase pinged successfully.")
        else:
            print("❌ Failed to ping Supabase:", response.text)
    except Exception as e:
        print("⚠️ Error pinging Supabase:", e)

if __name__ == "__main__":
    while True:
        ping_supabase()
        time.sleep(600)  # every 10 minutes
