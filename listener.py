from flask import Flask, request, jsonify
import json

app = Flask(__name__)

# Webhook endpoint – accepts POST requests
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    2boxes_id = data.get('id')
    rma_id = data.get('captured_rma')
    line_items = data.get('line_items')

    
    print('--- Webhook received ---')
    print('Headers:', json.dumps(dict(request.headers), indent=2))
    print('Two Boxes ID:', 2boxes_id)
    print('RMA ID:', rma_id)
    print('------------------------')

    for item in line_items:
        print('SKU:', item.get('sku'))
        print('Quantity:', item.get('quantity'))
        print('Order ID:', item.get('id'))
        print('Disposition:', item.get('disposition'))

    
    return jsonify({'received': True}), 200

