from flask import Flask, request, jsonify
import json

from clients.mintsoftClient import MintsoftOrderClient
from service.mintsoftReturnService import MintsoftReturnService

app = Flask(__name__)


# Webhook endpoint – accepts POST requests
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    twoboxes_id = data.get('id')
    event_data = data.get('event_data')
    captured_rma = event_data.get('captured_rma')
    line_items = event_data.get('line_items')

    
    print('--- Webhook received ---')
    print('Headers:', json.dumps(dict(request.headers), indent=2))
    print('Two Boxes ID:', twoboxes_id)
    print('RMA ID:', captured_rma)

    return jsonify({'received': True}), 200

    print('------------------------')

    create_external_return_data = {
        "ClientId": 3,
        "WarehouseId": 3,
        "Reference": line_items[0].get('tracking_number'), ## Almancear en data la informacion del tracking number
    }
    ## add_return_items_data = ## Almancear en data la informacion de los items que van a integrar el return

    for item in line_items:
        print('Storefront Order Number:', item.get('storefront_order_number'))
        print('SKU:', item.get('sku'))
        print('Quantity:', item.get('quantity'))
        print('Disposition:', item.get('disposition'))
        print('Tracking Number:', item.get('tracking_number'))
        print('------------------------')

    print('End of webhook')

    OrderClient = MintsoftOrderClient()
    ReturnService = MintsoftReturnService(OrderClient)

    try:
        ReturnService.create_external_return(create_external_return_data)
        ##ReturnService.add_return_items(add_return_items_data)
    except Exception as e:

    