from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import re

app = Flask(__name__)
CORS(app)

FNS_API_KEY = os.environ.get('FNS_API_KEY')
GOOGLE_SCRIPT_URL = os.environ.get('GOOGLE_SCRIPT_URL')

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
        
        # CHECK
        try:
            check_resp = requests.get('https://api-fns.ru/api/check', params={'req': inn, 'key': FNS_API_KEY}, timeout=10)
            check_data = check_resp.json()
            if isinstance(check_data, dict) and 'items' in check_data:
                items_list = check_data['items']
                if items_list:
                    c = items_list[0]
                    ul_check = c.get('ЮЛ', {})
                    if ul_check:
                        neg = ul_check.get('Негатив', {})
                        
                        ned = neg.get('НедоимкаНалог', '')
                        debt_amount = 0
                        if ned and 'Да' in str(ned):
                            match = re.search(r'([\d.]+)', str(ned))
                            if match:
                                debt_amount = float(match.group(1))
                                if debt_amount >= 1e6:
                                    result['ens_debt'] = f"{debt_amount/1e6:.1f} млн ₽"
                                else:
                                    result['ens_debt'] = f"{debt_amount:,.0f} ₽"
                            else:
                                result['ens_debt'] = 'Есть'
                            
                            if debt_amount > 10_000_000:
                                result['risk'] += 50
                            elif debt_amount > 5_000_000:
                                result['risk'] += 35
                            elif debt_amount > 1_000_000:
                                result['risk'] += 25
                            elif debt_amount > 300_000:
                                result['risk'] += 15
                            else:
                                result['risk'] += 10
                        
                        if neg.get('Обременения') == 'Да':
                            result['blocked'] = True
                            result['risk'] += 35
                        
                        if neg.get('ПриостановкаОпераций') == 'Да':
                            result['suspended'] = True
                            result['risk'] += 30
        except:
            pass
        
        # BO
        try:
            bo_resp = requests.get('https://api-fns.ru/api/bo', params={'req': inn, 'key': FNS_API_KEY}, timeout=10)
            bo_data = bo_resp.json()
            if isinstance(bo_data, dict) and inn in bo_data:
                years = bo_data[inn]
                last_year = sorted(years.keys())[-1]
                year_data = years[last_year]
                rev = year_data.get('2110')
                prof = year_data.get('2400')
                if rev: result['revenue'] = f"{float(rev):,.0f} ₽"
                if prof: result['profit'] = f"{float(prof):,.0f} ₽"
        except:
            pass
        
        result['risk'] = min(100, result['risk'])
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/save-check', methods=['POST'])
def save_check():
    if not GOOGLE_SCRIPT_URL:
        return jsonify({'error': 'GOOGLE_SCRIPT_URL not set'}), 500
    try:
        payload = request.get_json()
        resp = requests.post(GOOGLE_SCRIPT_URL, json=payload, timeout=10)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
