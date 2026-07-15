from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

FNS_API_KEY = os.environ.get('FNS_API_KEY')

@app.route('/')
def home():
    return jsonify({'status': 'ok'})

@app.route('/my-ip')
def my_ip():
    resp = requests.get('https://api.ipify.org')
    return jsonify({'ip': resp.text.strip()})

@app.route('/api/check-company')
def check_company():
    inn = request.args.get('inn')
    
    if not inn:
        return jsonify({'error': 'Укажите ИНН'}), 400
    
    try:
        resp = requests.get('https://api-fns.ru/api/egr', params={
            'req': inn, 'key': FNS_API_KEY
        }, timeout=10)
        
        data = resp.json()
        
        result = {
            'inn': inn, 'name': 'Неизвестно', 'ogrn': '',
            'status': 'Неизвестно', 'risk': 0, 'risk_factors': [], 'address': ''
        }
        
        if isinstance(data, list) and data:
            root = data[0]
        else:
            root = data
        
        items = root.get('items', [])
        if items:
            company = items[0]
            ul = company.get('ЮЛ', {})
            
            if ul:
                result['name'] = ul.get('НаимСокрЮЛ') or ul.get('НаимПолнЮЛ') or 'Неизвестно'
                result['status'] = ul.get('Статус', 'Неизвестно')
                result['ogrn'] = ul.get('ОГРН', '')
                result['address'] = ul.get('Адрес', {}).get('АдресПолн', '')
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
