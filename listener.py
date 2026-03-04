from flask import Flask, request, jsonify
import os
import requests
import threading
from typing import Any, Dict, List, Union

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")
GAS_URL = os.environ.get("GAS_URL")

def enviar_a_google_async(datos):
    """Función para enviar datos en segundo plano"""
    try:
        # Aquí el timeout puede ser largo porque no bloquea al emisor
        requests.post(GAS_URL, json=datos, timeout=30)
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
    threading.Thread(target=enviar_a_google_async, args=(thread_data,)).start()

    return "", 200