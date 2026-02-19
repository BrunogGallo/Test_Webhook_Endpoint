from flask import Flask, request, jsonify
import json

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
    print('------------------------')

    for item in line_items:
        print('SKU:', item.get('sku'))
        print('Quantity:', item.get('quantity'))
        print('Order ID:', item.get('id'))
        print('Disposition:', item.get('disposition'))
        print('------------------------')

    print('End of webhook')

    
    return jsonify({'received': True}), 200

