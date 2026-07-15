from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

FNS_API_KEY = os.environ.get('FNS_API_KEY')

@app.route('/')
def home():
    return jsonify({
        'status': 'ok',
        'service': 'Contractor API',
        'endpoints': ['/api/check-company?inn=ИНН']
    })

@app.route('/api/check-company')
def check_company():
    inn = request.args.get('inn')
    
    if not inn:
        return jsonify({'error': 'Укажите ИНН'}), 400
    
    if not FNS_API_KEY:
        return jsonify({'error': 'API ключ не настроен'}), 500
    
    try:
        # ЕГРЮЛ/ЕГРИП
        egr_resp = requests.get('https://api-fns.ru/api/egr', params={
            'req': inn,
            'key': FNS_API_KEY
        }, timeout=10)
        
        if egr_resp.status_code != 200:
            return jsonify({'error': f'API ФНС вернул {egr_resp.status_code}'}), 500
        
        raw_data = egr_resp.json()
        
        # Проверка рисков
        check_resp = requests.get('https://api-fns.ru/api/check', params={
            'req': inn,
            'key': FNS_API_KEY
        }, timeout=10)
        check_raw = check_resp.json() if check_resp.status_code == 200 else {}
        
        result = {
            'inn': inn,
            'name': 'Неизвестно',
            'ogrn': '',
            'status': 'Неизвестно',
            'risk': 0,
            'risk_factors': [],
            'address': '',
            'okved': ''
        }
        
        # УНИВЕРСАЛЬНАЯ НОРМАЛИЗАЦИЯ: список или словарь
        if isinstance(raw_data, list):
            root_item = raw_data[0] if len(raw_data) > 0 else {}
        else:
            root_item = raw_data
        
        items = root_item.get('items', [])
        
        if items:
            company = items[0]
            result['ogrn'] = company.get('ОГРН', '')
            result['address'] = company.get('АдресПолн', '')
            
            ul = company.get('UL')
            ip = company.get('IP')
            
            if ul:
                result['name'] = ul.get('НаимСокр') or ul.get('НаимПолн') or 'Неизвестно'
                result['status'] = ul.get('Статус', 'Неизвестно')
                result['address'] = ul.get('АдресПолн') or result['address']
            elif ip:
                fio = ip.get('ФИОРус', {})
                parts = [fio.get('Фамилия'), fio.get('Имя'), fio.get('Отчество')]
                fio_string = ' '.join(filter(None, parts))
                result['name'] = f'ИП {fio_string}' if fio_string else 'Неизвестно'
                result['status'] = ip.get('Статус', 'Неизвестно')
                result['address'] = ip.get('АдресПолн') or result['address']
        
        # УНИВЕРСАЛЬНАЯ НОРМАЛИЗАЦИЯ: список или словарь
        if isinstance(check_raw, list):
            check_root = check_raw[0] if len(check_raw) > 0 else {}
        else:
            check_root = check_raw
        
        check_items = check_root.get('items', [])
        if check_items:
            checks = check_items[0]
            
            if checks.get('МассовыйАдрес'):
                result['risk'] += 20
                result['risk_factors'].append('Массовый адрес регистрации')
            if checks.get('МассовыйРуководитель'):
                result['risk'] += 15
                result['risk_factors'].append('Массовый руководитель')
            if checks.get('НедостоверныеСведения'):
                result['risk'] += 30
                result['risk_factors'].append('Недостоверные сведения')
        
        if result['status'] == 'Ликвидировано':
            result['risk'] = 100
            result['risk_factors'].append('Компания ликвидирована')
        
        result['risk'] = min(100, result['risk'])
        
        return jsonify(result)
    
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Таймаут API ФНС'}), 500
    except Exception as e:
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
