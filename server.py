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
        # ЕГРЮЛ
        egr_resp = requests.get('https://api-fns.ru/api/egr', params={
            'req': inn, 'key': FNS_API_KEY
        }, timeout=10)
        
        # Проверка рисков
        check_resp = requests.get('https://api-fns.ru/api/check', params={
            'req': inn, 'key': FNS_API_KEY
        }, timeout=10)
        
        # Бухотчётность
        bo_resp = requests.get('https://api-fns.ru/api/bo', params={
            'req': inn, 'key': FNS_API_KEY
        }, timeout=10)
        
        egr_data = egr_resp.json()
        check_data = check_resp.json() if check_resp.status_code == 200 else {}
        bo_data = bo_resp.json() if bo_resp.status_code == 200 else {}
        
        result = {
            'inn': inn, 'name': 'Неизвестно', 'ogrn': '', 'status': 'Неизвестно',
            'risk': 0, 'risk_factors': [], 'address': '',
            'revenue': None, 'profit': None,
            'ens_debt': None, 'blocked': False, 'suspended': False,
            'reg_date': '', 'capital': '', 'okved': '',
            'director': '', 'mass_addr': False, 'mass_dir': False,
            'unreliable': False, 'disqualified': False
        }
        
        # ЕГРЮЛ
        if isinstance(egr_data, list) and egr_data:
            root = egr_data[0]
            items = root.get('items', [])
            if items:
                company = items[0]
                ul = company.get('ЮЛ', {})
                if ul:
                    result['name'] = ul.get('НаимСокрЮЛ') or ul.get('НаимПолнЮЛ') or 'Неизвестно'
                    result['status'] = ul.get('Статус', 'Неизвестно')
                    result['ogrn'] = ul.get('ОГРН', '')
                    result['address'] = ul.get('Адрес', {}).get('АдресПолн', '')
                    result['reg_date'] = ul.get('ДатаРег', '')
                    result['capital'] = ul.get('Капитал', {}).get('СумКап', '')
                    result['okved'] = ul.get('ОснВидДеят', {}).get('Код', '') + ' ' + ul.get('ОснВидДеят', {}).get('Текст', '')
                    
                    # Руководитель
                    head = ul.get('Руководитель', {})
                    if isinstance(head, dict) and 'ФИОПолн' in head:
                        result['director'] = head.get('ФИОПолн', '')
        
        # Риски из check
        if isinstance(check_data, list) and check_data:
            check_root = check_data[0]
            check_items = check_root.get('items', [])
            if check_items:
                checks = check_items[0]
                
                if checks.get('МассовыйАдрес'):
                    result['risk'] += 20
                    result['mass_addr'] = True
                if checks.get('МассовыйРуководитель'):
                    result['risk'] += 15
                    result['mass_dir'] = True
                if checks.get('НедостоверныеСведения'):
                    result['risk'] += 30
                    result['unreliable'] = True
                if checks.get('ДисквалифицированныеЛица'):
                    result['risk'] += 25
                    result['disqualified'] = True
                if checks.get('ЗадолженностьЕНС'):
                    result['risk'] += 25
                    result['ens_debt'] = 'Есть'
                if checks.get('БлокировкаСчетов'):
                    result['risk'] += 35
                    result['blocked'] = True
                if checks.get('ПриостановкаОпераций'):
                    result['risk'] += 30
                    result['suspended'] = True
        
        # Бухотчётность
        if isinstance(bo_data, list) and bo_data:
            bo_root = bo_data[0] if bo_data else {}
            bo_items = bo_root.get('items', []) if isinstance(bo_root, dict) else []
            if bo_items:
                bo = bo_items[0]
                result['revenue'] = bo.get('Выручка', None)
                result['profit'] = bo.get('ЧистаяПрибыль', None)
        
        if result['status'] == 'Ликвидировано':
            result['risk'] = 100
        
        result['risk'] = min(100, result['risk'])
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
