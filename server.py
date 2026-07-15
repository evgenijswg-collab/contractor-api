from flask import Flask, request, jsonify
import requests
import os
import sys

app = Flask(__name__)

# Инициализация API ключа
FNS_API_KEY = os.environ.get('FNS_API_KEY', '').strip(' "\'')

@app.route('/api/check-company')
def check_company():
    inn = request.args.get('inn')
    if not inn or not FNS_API_KEY:
        return jsonify({'error': 'Укажите ИНН и настройте ключ'}), 400
        
    result = {'inn': inn, 'name': 'Неизвестно', 'risk_factors': [], 'risk': 0}
        
    try:
        # 1. Запрос к EGR (Основная информация)
        egr_resp = requests.get('https://api-fns.ru', 
                               params={'req': inn, 'key': FNS_API_KEY}, timeout=10)
        
        if egr_resp.status_code == 404:
            return jsonify({'error': 'Ошибка 404: Проверьте ключ или IP в ЛК api-fns.ru'}), 401
            
        egr_json = egr_resp.json()
        items = egr_json.get('items', [])
        
        if items:
            # Парсинг по структурам из документации
            data = items[0].get('ЮЛ') or items[0].get('ИП') or {}
            result['name'] = data.get('НаимСокрЮЛ') or data.get('ФИОПолн') or 'Неизвестно'
            result['status'] = data.get('Статус', 'Неизвестно')
            result['address'] = data.get('Адрес', {}).get('АдресПолн', '')

        # 2. Запрос к CHECK (Риски)
        check_resp = requests.get('https://api-fns.ru', 
                                 params={'req': inn, 'key': FNS_API_KEY}, timeout=10)
        
        if check_resp.status_code == 200:
            check_json = check_resp.json()
            check_items = check_json.get('items', [])
            if check_items:
                negativ = (check_items[0].get('ЮЛ') or check_items[0].get('ИП') or {}).get('Негатив', {})
                # Обработка маркеров риска
                if negativ.get('НедостоверАдрес') or negativ.get('БлокСчета'):
                    result['risk'] = 100
                    result['risk_factors'].append('Высокий риск: Недостоверность/Блокировка')
                
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
