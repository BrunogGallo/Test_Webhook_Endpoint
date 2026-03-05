from flask import Flask, request, jsonify
import os
import requests
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")
GAS_URL = os.environ.get("GAS_URL")

# 1. Create a Thread Pool with a strict limit (e.g., 5 to 10 workers)
# This prevents RAM exhaustion. If a burst of 50 webhooks comes in, 
# it processes 5 at a time and queues the rest automatically.
executor = ThreadPoolExecutor(max_workers=5)

# 2. Use a Session to reuse underlying TCP connections
# This prevents socket exhaustion when making dozens of requests to Google.
session = requests.Session()

def enviar_a_google_async(datos):
    """Función para enviar datos en segundo plano"""
    try:
        # Use the session instead of requests.post
        session.post(GAS_URL, json=datos, timeout=30)
        print("✅ Enviado a Google Apps Script correctamente")
    except Exception as e:
        print(f"❌ Error enviando a Google: {e}")

@app.route("/webhook", methods=["POST"])
def webhook():
    token = request.headers.get("x-two-boxes-authorization")
    if not token or token != WEBHOOK_SECRET:
        print("Unauthorized Access Request")
        return jsonify({"error": "Unauthorized"}), 401
    
    raw_data = request.get_json(silent=True)
    if not raw_data:
        return jsonify({"error": "No data"}), 400

    thread_data = raw_data.copy() if isinstance(raw_data, dict) else raw_data
    
    # 3. Submit the task to the queue instead of spawning a wild thread
    executor.submit(enviar_a_google_async, thread_data)

    return "", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)