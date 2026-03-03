from flask import Flask, request, jsonify
import os
import requests
import threading
from typing import Any, Dict, List, Union

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")
GAS_URL = os.environ.get("GAS_URL")

@app.route("/webhook", methods=["POST"])
def webhook():

    token = request.headers.get("X-Webhook-Secret")

    if not token or token != WEBHOOK_SECRET:
        print("Unauthorized Access Request")
        return jsonify({"error": "Unauthorized"}), 401
    
    raw_data = request.get_json(silent=True)
    if not raw_data:
        return jsonify({"error": "No data"}), 400

    # Enviamos el JSON al script de Google de forma ultra simple
    try:
        # Usamos timeout para que Railway no se quede colgado
        requests.post(GAS_URL, json=raw_data, timeout=5)
    except Exception as e:
        print(f"Error enviando a Google: {e}")

    print("--- Webhook recibido y enviado a Drive via Proxy ---")
    return jsonify({"received": True}), 200