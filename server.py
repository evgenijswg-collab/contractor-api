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
        # Пробуем API ФНС
        egr_resp = requests.get('https://api-fns.ru/api/egr', params={
            'req': inn,
            'key': FNS_API_KEY
        }, timeout=10)
        
        # Проверяем что вернулось
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
        
        company = egr_data.get('items', [{}])[0] if egr_data.get('items') else {}
        checks = check_data.get('items', [{}])[0] if check_data.get('items') else {}
        
        name = (company.get('ЮЛ', {}).get('НаимСокр') or 
                company.get('ЮЛ', {}).get('НаимПолн') or 'Неизвестно')
        
        risk = 0
        risk_factors = []
        
        if company.get('ЮЛ', {}).get('Статус') == 'Ликвидировано':
            risk = 100
            risk_factors.append('Ликвидировано')
        if checks.get('МассовыйАдрес'):
            risk += 20
            risk_factors.append('Массовый адрес')
        if checks.get('МассовыйРуководитель'):
            risk += 15
            risk_factors.append('Массовый руководитель')
        if checks.get('НедостоверныеСведения'):
            risk += 30
            risk_factors.append('Недостоверные сведения')
        
        return jsonify({
            'inn': inn,
            'name': name,
            'ogrn': company.get('ЮЛ', {}).get('ОГРН', ''),
            'status': company.get('ЮЛ', {}).get('Статус', 'Неизвестно'),
            'risk': min(100, risk),
            'risk_factors': risk_factors
        })
    
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Таймаут API ФНС'}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'API ФНС недоступен с сервера Render. Возможно нужен российский IP.'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
