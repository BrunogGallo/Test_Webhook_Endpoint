from flask import Flask, request, jsonify
import os
import requests
import threading
from typing import Any, Dict, List, Union

app = Flask(__name__)
GAS_URL = os.environ.get("https://script.google.com/u/0/home/projects/1EewwTsZb_M7g7BoEgBdDXH344XOyfsvXgJQTh8oiaTjUTB1VQffNXQm9/edit")

@app.route("/webhook", methods=["POST"])
def webhook():
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