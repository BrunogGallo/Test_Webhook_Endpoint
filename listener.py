from flask import Flask, request, jsonify
import threading
from typing import Any, Dict, List, Union

from services.mintsoft_service import MintsoftReturnService

app = Flask(__name__)
return_service = MintsoftReturnService()


def _normalise_webhook_payload(payload: Union[Dict[str, Any], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Ensure the webhook payload is always a list of events,
    which is what MintsoftReturnService expects.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return [payload]
    raise ValueError("Unexpected webhook payload format")


@app.route("/webhook", methods=["POST"])
def webhook():
    raw_data = request.get_json(silent=True)
    if raw_data is None:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    try:
        data = _normalise_webhook_payload(raw_data)
    except Exception as e:
        return jsonify({"error": f"Invalid payload format: {e}"}), 400

    print("--- Webhook received ---")

    def process_webhook():
        try:
            # Step 1: Create (or find) the Mintsoft return
            return_id = return_service.create_return(data)

            # Step 2: If a return was created, add items, allocate locations and confirm
            if return_id is not None:
                return_service.add_return_items(return_id, data)

            print("Webhook processed successfully")
        except Exception as e:
            print(f"Error processing webhook: {e}")

    threading.Thread(target=process_webhook, daemon=True).start()

    return jsonify({"received": True}), 200
