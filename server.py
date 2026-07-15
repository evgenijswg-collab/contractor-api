from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import re

app = Flask(__name__)
CORS(app)

FNS_API_KEY = os.environ.get('FNS_API_KEY', '').strip(' "\'')

@app.route('/api/check-company')
def check_company():
    inn = request.args.get('inn')
    if not inn:
        return jsonify({'error': 'Укажите ИНН'}), 400
        
    # 1. Надежный перехват исходящего IPv4 через альтернативный сервис
    current_render_ip = "Не определен"
    try:
        # Используем стабильный ifconfig.co, который отдает чистый IP
        ip_resp = requests.get('https://ifconfig.co', timeout=5)
        if ip_resp.status_code == 200:
            current_render_ip = ip_resp.text.strip()
        else:
            # Резервный шлюз от Яндекса
            ip_resp = requests.get('https://yandex.ru', timeout=5)
            current_render_ip = ip_resp.text.strip().replace('"', '')
            
        # Защита: если сервис вернул HTML страницу вместо IP, обрезаем её
        if "<html" in current_render_ip.lower() or len(current_render_ip) > 45:
            # Ищем что-то похожее на IP регулярным выражением
            found = re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', current_render_ip)
            current_render_ip = found.group(0) if found else "Ошибка: Сервис определения IP вернул HTML"
            
    except Exception as e:
        current_render_ip = f"Ошибка определения IP: {str(e)}"

    if not FNS_API_KEY:
        return jsonify({'error': 'Ключ FNS_API_KEY не задан', 'current_ip': current_render_ip}), 500
        
    try:
        # 2. Запрос к API ФНС
        egr_resp = requests.get('https://api-fns.ru', params={'req': inn, 'key': FNS_API_KEY}, timeout=10)
        
        # Если API-ФНС заблокировал нас по IP (отдал 404), выводим чистый IP на экран
        if egr_resp.status_code == 404:
            return jsonify({
                'status': 'Заблокировано API-ФНС по IP',
                'ИНСТРУКЦИЯ': 'Скопируйте IP ниже и вставьте в белый список личного кабинета api-fns.ru',
                'ДОБАВИТЬ_В_БЕЛЫЙ_СПИСОК_IP': current_render_ip
            }), 401
            
        egr_json = egr_resp.json()
        items = egr_json.get('items', [])
        
        result = {'inn': inn, 'name': 'Неизвестно', 'status': 'Неизвестно', 'address': '', 'render_ip_used': current_render_ip}
        
        if items and isinstance(items, list):
            company = items if items else {}
            ul_data = company.get('ЮЛ') or company.get('ИП', {})
            result['name'] = ul_data.get('НаимСокрЮЛ') or ul_data.get('ФИОПолн') or 'Неизвестно'
            result['status'] = ul_data.get('Статус', 'Неизвестно')
            result['address'] = ul_data.get('Адрес', {}).get('АдресПолн', '')
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e), 'your_current_ip': current_render_ip}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
