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

@app.route('/api/check-company')
def check_company():
    inn = request.args.get('inn')
    if not inn:
        return jsonify({'error': 'Укажите ИНН'}), 400
    try:
        resp = requests.get('https://api-fns.ru/api/egr', params={'req': inn, 'key': FNS_API_KEY}, timeout=10)
        data = resp.json()
        
        # Базовая структура (которая работала)
        result = {
            'inn': inn, 'name': 'Неизвестно', 'ogrn': '', 'status': 'Неизвестно', 
            'risk': 0, 'risk_factors': [], 'address': '',
            'revenue': None, 'profit': None, 'ens_debt': None, 'blocked': False, 'suspended': False
        }
        
        if isinstance(data, list) and data:
            root = data[0]
        else:
            root = data
        
        items = root.get('items', [])
        if items:
            ul = items[0].get('ЮЛ', {})
            if ul:
                result['name'] = ul.get('НаимСокрЮЛ') or ul.get('НаимПолнЮЛ') or 'Неизвестно'
                result['status'] = ul.get('Статус', 'Неизвестно')
                result['ogrn'] = ul.get('ОГРН', '')
                result['address'] = ul.get('Адрес', {}).get('АдресПолн', '')
        
        # Добавляем check
        try:
            check_resp = requests.get('https://api-fns.ru/api/check', params={'req': inn, 'key': FNS_API_KEY}, timeout=10)
            check_data = check_resp.json()
            if isinstance(check_data, list) and check_data:
                cr = check_data[0]
                ci = cr.get('items', [])
                if ci:
                    c = ci[0]
                    if c.get('ЗадолженностьЕНС'): result['ens_debt'] = 'Есть'; result['risk'] += 25
                    if c.get('БлокировкаСчетов'): result['blocked'] = True; result['risk'] += 35
                    if c.get('ПриостановкаОпераций'): result['suspended'] = True; result['risk'] += 30
        except:
            pass
        
        # Добавляем bo
        try:
            bo_resp = requests.get('https://api-fns.ru/api/bo', params={'req': inn, 'key': FNS_API_KEY}, timeout=10)
            bo_data = bo_resp.json()
            if isinstance(bo_data, list) and bo_data:
                br = bo_data[0] if bo_data else {}
                bi = br.get('items', []) if isinstance(br, dict) else []
                if bi:
                    result['revenue'] = bi[0].get('Выручка')
                    result['profit'] = bi[0].get('ЧистаяПрибыль')
        except:
            pass
        
        result['risk'] = min(100, result['risk'])
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
