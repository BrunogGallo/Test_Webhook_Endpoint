from flask import Flask, request, jsonify
import os
import requests
from concurrent.futures import ThreadPoolExecutor
from services.mintsoft_service import MintsoftReturnService

app = Flask(__name__)
return_service = MintsoftReturnService()

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")
GAS_URL = os.environ.get("GAS_URL")

executor = ThreadPoolExecutor(max_workers=10)

session = requests.Session()

def enviar_a_google_async(datos):
    """Función para enviar datos en segundo plano"""
    try:
        session.post(GAS_URL, json=datos, timeout=30)
        print("✅ Enviado a Google Apps Script correctamente")
    except Exception as e:
        print(f"❌ Error enviando a Google: {e}")

def procesar_webhook(data):
    try:
        # Crea return interno o externo
        return_id = return_service.create_return(data)
        print(return_id)

        # Pasar items de RET o RET-QT a la caja del return si es External
        if return_id[1] == "External Return Created":
          # Pasar items a RET o RET-QT
          return_service.allocate_internal_return_items(return_id)

          # Pasar items de RET o RET-QT a la caja del return si es External
          return_service.reallocate_return_items(data)

        # Agregar items al return en caso de que sea interno
        if return_id[0] is not None:
          return_service.add_return_items(return_id[0], data)

          # Pasar items de RET o RET-QT a la caja del return si es Internal
          return_service.reallocate_return_items(data)

        print("Webhook procesado con exito")
        
    except Exception as e:
        print(f"Error procesando webhook: {e}")

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
    
    # 3. Subir JSON al Google Drive
    executor.submit(enviar_a_google_async, thread_data)

    # 4. Procesarlo en Mintsoft
    executor.submit(procesar_webhook, raw_data)

    return "", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)