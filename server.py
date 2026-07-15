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
        'endpoints': ['/api/check-company?inn=ИНН'],
        'fns_key_set': bool(FNS_API_KEY)
    })

@app.route('/api/check-company')
def check_company():
    inn = request.args.get('inn')
    
    if not inn:
        return jsonify({'error': 'Укажите ИНН'}), 400
    
    if not FNS_API_KEY:
        return jsonify({'error': 'API ключ не настроен'}), 500
    
    try:
        # ЕГРЮЛ
        egr_resp = requests.get('https://api-fns.ru/api/egr', params={
            'req': inn,
            'key': FNS_API_KEY
        }, timeout=10)
        
        if egr_resp.status_code != 200:
            return jsonify({
                'error': f'API ФНС вернул {egr_resp.status_code}',
                'raw': egr_resp.text[:200]
            }), 500
        
        egr_data = egr_resp.json()
        
        # Проверка
        check_resp = requests.get('https://api-fns.ru/api/check', params={
            'req': inn,
            'key': FNS_API_KEY
        }, timeout=10)
        check_data = check_resp.json() if check_resp.status_code == 200 else {}
        
        # Парсинг
        company = egr_data.get('items', [{}])[0] if egr_data.get('items') else {}
        checks = check_data.get('items', [{}])[0] if check_data.get('items') else {}
        
        ul = company.get('ЮЛ', {})
        name = ul.get('НаимСокр') or ul.get('НаимПолн') or 'Неизвестно'
        
        # Риски
        risk = 0
        risk_factors = []
        
        status = ul.get('Статус', 'Неизвестно')
        
        if status == 'Ликвидировано':
            risk = 100
            risk_factors.append('Компания ликвидирована')
        
        if checks.get('МассовыйАдрес'):
            risk += 20
            risk_factors.append('Массовый адрес регистрации')
        
        if checks.get('МассовыйРуководитель'):
            risk += 15
            risk_factors.append('Массовый руководитель')
        
        if checks.get('НедостоверныеСведения'):
            risk += 30
            risk_factors.append('Недостоверные сведения')
        
        if checks.get('ДисквалифицированныеЛица'):
            risk += 25
            risk_factors.append('Дисквалифицированные лица')
        
        return jsonify({
            'inn': inn,
            'name': name,
            'ogrn': ul.get('ОГРН', ''),
            'status': status,
            'risk': min(100, risk),
            'risk_factors': risk_factors,
            'address': ul.get('Адрес', ''),
            'okved': ul.get('ОКВЭД', '')
        })
    
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Таймаут API ФНС'}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'API ФНС недоступен'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
