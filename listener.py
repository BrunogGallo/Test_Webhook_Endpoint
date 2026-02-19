from flask import Flask, request, jsonify
import json

app = Flask(__name__)

# Webhook endpoint – accepts POST requests
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    return_id = data.get('id') if data else None
    
    print('--- Webhook received ---')
    print('Headers:', json.dumps(dict(request.headers), indent=2))
    print('Body:', return_id)
    print('------------------------')
    
    return jsonify({'received': True}), 200

# Optional: catch-all POST for testing (e.g. POST /)
@app.route('/', methods=['POST'])
def root():
    data = request.get_json()
    return_id = data.get('id') if data else None
    
    print('--- POST received at / ---')
    print('Headers:', json.dumps(dict(request.headers), indent=2))
    print('Body:', return_id)
    print('------------------------')
    
    return jsonify({'received': True}), 200
