from flask import Flask, request, jsonify
import json
import threading

from clients.mintsoftClient import MintsoftOrderClient
from service.mintsoftReturnService import MintsoftReturnService

app = Flask(__name__)
OrderClient = MintsoftOrderClient()
ReturnService = MintsoftReturnService(OrderClient)


# Webhook endpoint – accepts POST requests
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    twoboxes_id = data.get('id')
    event_data = data.get('event_data')
    captured_rma = event_data.get('captured_rma')
    line_items = event_data.get('line_items')

    print('--- Webhook received ---')
    print('Two Boxes ID:', twoboxes_id)
    print('RMA ID:', captured_rma)

    def process_webhook():
        create_external_return_data = {
            "ClientId": 3,
            "WarehouseId": 3,
            "Reference": line_items[0].get('tracking_number'),
        }
        # add_return_items_data = ...  ## Datos de los items que integran el return

        for item in line_items:
            print('Storefront Order Number:', item.get('storefront_order_number'))
            print('SKU:', item.get('sku'))
            print('Quantity:', item.get('quantity'))
            print('Disposition:', item.get('disposition'))
            print('Tracking Number:', item.get('tracking_number'))
            print('------------------------')

        try:
            ReturnService.create_external_return(create_external_return_data)
            # ReturnService.add_return_items(add_return_items_data)
        except Exception as e:
            print(f"Error processing webhook: {e}")

        print('End of webhook processing')

    threading.Thread(target=process_webhook, daemon=True).start()

    return jsonify({'received': True}), 200


    