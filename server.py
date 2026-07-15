from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import socket
import subprocess

app = Flask(__name__)
CORS(app)

FNS_API_KEY = os.environ.get('FNS_API_KEY', '').strip(' "\'')

@app.route('/api/check-company')
def check_company():
    inn = request.args.get('inn')
    if not inn:
        return jsonify({'error': 'Укажите ИНН'}), 400
        
    # === НАДЕЖНОЕ СИСТЕМНОЕ ОПРЕДЕЛЕНИЕ IP ИЗ СЕТЕВОЙ КАРТЫ RENDER ===
    current_render_ip = "Не определен"
    try:
        # Пытаемся получить IP через системный сокет хоста
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Подключаемся к публичному DNS (запрос не отправляется, просто инициализирует интерфейс)
        s.connect(("8.8.8.8", 80))
        current_render_ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            # Резервный способ: вызов Linux команды hostname
            current_render_ip = subprocess.check_output(["hostname", "-I"]).decode().strip().split()[0]
        except Exception as e:
            current_render_ip = f"Системная ошибка: {str(e)}"

    if not FNS_API_KEY:
        return jsonify({'error': 'Ключ FNS_API_KEY не задан', 'current_ip': current_render_ip}), 500
        
    try:
        # 2. Запрос к API ФНС
        egr_resp = requests.get('https://api-fns.ru', params={'req': inn, 'key': FNS_API_KEY}, timeout=10)
        
        # Если заблокировано, отдаем точный локальный IP
        if egr_resp.status_code == 404:
            return jsonify({
                'status': 'Заблокировано API-ФНС по IP',
                'ИНСТРУКЦИЯ': 'Вставьте IP из поля ниже в белый список личного кабинета api-fns.ru',
                'ДОБАВИТЬ_В_БЕЛЫЙ_СПИСОК_IP': current_render_ip
            }), 401
            
        egr_json = egr_resp.json()
        items = egr_json.get('items', [])
        
        result = {'inn': inn, 'name': 'Неизвестно', 'status': 'Неизвестно', 'address': '', 'render_ip_used': current_render_ip}
        
        if items and isinstance(items, list):
            company = items[0] if items else {}
            ul_data = company.get('ЮЛ') or company.get('ИП', {})
            result['name'] = ul_data.get('НаимСокрЮЛ') or ul_data.get('ФИОПолн') or 'Неизвестно'
            result['status'] = ul_data.get('Статус', 'Неизвестно')
            result['address'] = ul_data.get('Адрес', {}).get('АдресПолн', '')
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e), 'your_current_ip': current_render_ip}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
