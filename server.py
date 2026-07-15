from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import sys

app = Flask(__name__)
CORS(app)

# Безопасное получение ключа API из переменных окружения Render
FNS_API_KEY = os.environ.get('FNS_API_KEY', '').strip(' "\'')

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
        
    # === ШАГ 1: АВТОМАТИЧЕСКИЙ ПЕРЕХВАТ ТЕКУЩЕГО IP СЕРВЕРА ===
    current_render_ip = "Не определен"
    try:
        # Делаем запрос к внешнему сервису, чтобы узнать наш текущий IPv4
        current_render_ip = requests.get('https://ipify.org', timeout=5).text.strip()
        print(f"[КРИТИЧЕСКИЙ ЛОГ] ТЕКУЩИЙ ИСХОДЯЩИЙ IP СЕРВЕРА RENDER: {current_render_ip}", flush=True)
    except Exception as ip_err:
        print(f"[ЛОГ ОШИБКА] Не удалось определить исходящий IP: {str(ip_err)}", flush=True)

    if not FNS_API_KEY:
        return jsonify({
            'error': 'FNS_API_KEY не настроен в Render',
            'your_current_render_ip': current_render_ip
        }), 500
        
    result = {
        'inn': inn, 
        'name': 'Неизвестно', 
        'ogrn': '', 
        'status': 'Неизвестно', 
        'risk': 0, 
        'risk_factors': [], 
        'address': '', 
        'okved': '',
        'render_ip_used': current_render_ip  # Добавляем в ответ для удобства дебага
    }
        
    try:
        # 2. Запрос к ЕГРЮЛ/ЕГРИП (Метод egr)
        egr_resp = requests.get('https://api-fns.ru', params={'req': inn, 'key': FNS_API_KEY}, timeout=10)
        
        # Перехватываем блокировку по IP (404 от api-fns)
        if egr_resp.status_code == 404:
            print(f"[ЛОГ КРИТИЧЕСКИЙ] Сервис ФНС заблокировал запрос! Скопируйте IP {current_render_ip} и вставьте в белый список API-ФНС.", file=sys.stderr, flush=True)
            return jsonify({
                'error': 'Доступ отклонен сервисом ФНС (Ошибка 404). IP-адрес сервера не авторизован.',
                'ip_to_add_in_white_list': current_render_ip
            }), 401
            
        if egr_resp.status_code != 200:
            return jsonify({'error': f'API ФНС вернул код {egr_resp.status_code}'}), 500
            
        egr_json = egr_resp.json()
        items = egr_json.get('items', [])
        if items and isinstance(items, list):
            company = items[0]
            ul_data = company.get('ЮЛ') or company.get('ИП', {})
            result['name'] = ul_data.get('НаимСокрЮЛ') or ul_data.get('ФИОПолн') or 'Неизвестно'
            result['status'] = ul_data.get('Статус', 'Неизвестно')
            result['address'] = ul_data.get('Адрес', {}).get('АдресПолн', '')
            
            okved_info = ul_data.get('ОснВидДеят', {})
            if okved_info:
                result['okved'] = f"{okved_info.get('Код', '')} {okved_info.get('Текст', '')}".strip()
                    
        # 3. Запрос к методу проверки рисков (Метод check)
        check_resp = requests.get('https://api-fns.ru', params={'req': inn, 'key': FNS_API_KEY}, timeout=10)
        if check_resp.status_code == 200:
            check_json = check_resp.json()
            check_items = check_json.get('items', [])
            if check_items and isinstance(check_items, list):
                negativ = (check_items[0].get('ЮЛ') or check_items[0].get('ИП') or {}).get('Негатив', {})
                if negativ:
                    factors = [f.strip() for f in negativ.get('Текст', '').split(';') if f.strip()]
                    result['risk_factors'].extend(factors)
                    if any(key in negativ for key in ['РеестрМассАдрес', 'МассАдрес', 'НедостоверАдрес']): 
                        result['risk'] += 30
                    if negativ.get('БлокСчета') == 'Да': 
                        result['risk'] += 40

        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e), 'current_ip': current_render_ip}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
