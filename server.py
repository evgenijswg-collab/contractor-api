from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import sys

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
        print("ОШИБКА: Переменная окружения FNS_API_KEY не настроена в Render!", file=sys.stderr, flush=True)
        return jsonify({'error': 'API ключ не настроен'}), 500
        
    # Инициализация дефолтной структуры ответа
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
        
    try:
        # 1. Запрос к основному методу реквизитов multinfo
        print(f"[ЛОГ] Отправка запроса multinfo для ИНН: {inn}", flush=True)
        # Обратите внимание на измененный URL эндпоинта
        egr_resp = requests.get('https://api-fns.ru', params={
            'req': inn,
            'key': FNS_API_KEY
        }, timeout=10)
        
        print(f"[ЛОГ] Статус ответа multinfo от API ФНС: {egr_resp.status_code}", flush=True)
        
        if egr_resp.status_code != 200:
            print(f"[ЛОГ ОШИБКА] API ФНС вернул статус {egr_resp.status_code}. Текст: {egr_resp.text[:200]}", file=sys.stderr, flush=True)
            return jsonify({'error': f'API ФНС вернул ошибку {egr_resp.status_code}'}), 500
            
        try:
            raw_data = egr_resp.json()
            print(f"[ДЕБАГ MULTINFO ОТВЕТ]: {raw_data}", flush=True)
        except Exception as json_err:
            print(f"[ЛОГ ОШИБКА] Ответ от API не является JSON. Текст ответа: {egr_resp.text[:500]}", file=sys.stderr, flush=True)
            return jsonify({'error': 'API ФНС вернул некорректный формат данных (не JSON)'}), 500
        
        # 2. Запрос к методу рисков/скоринга (проверяем тариф)
        print(f"[ЛОГ] Отправка запроса scoring для ИНН: {inn}", flush=True)
        # Если метод check выдает 404, api-fns использует метод scoring
        check_resp = requests.get('https://api-fns.ru', params={
            'req': inn,
            'key': FNS_API_KEY
        }, timeout=10)
        
        check_raw = {}
        if check_resp.status_code == 200:
            try:
                check_raw = check_resp.json()
                print(f"[ДЕБАГ SCORING ОТВЕТ]: {check_raw}", flush=True)
            except:
                pass
        
        # --- ПАРСИНГ ОТВЕТА МЕТОДА MULTINFO ---
        if isinstance(raw_data, list):
            root_item = raw_data[0] if len(raw_data) > 0 else {}
        else:
            root_item = raw_data
            
        items = root_item.get('items', [])
        
        if items:
            company = items[0]
            result['ogrn'] = company.get('ОГРН') or company.get('ogrn') or ''
            result['address'] = company.get('АдресПолн') or company.get('address') or ''
            
            # В multinfo ключи могут быть плоскими (без вложенности в UL)
            result['name'] = company.get('НаимСокр') or company.get('НаимПолн') or company.get('name') or 'Неизвестно'
            result['status'] = company.get('Статус') or company.get('status') or 'Неизвестно'
            result['okved'] = company.get('ОКВЭД') or company.get('okved') or ''
            
            # Если структура всё ещё старая вложенная (подстраховка)
            ul = company.get('UL')
            ip = company.get('IP')
            
            if ul:
                result['name'] = ul.get('НаимСокр') or ul.get('НаимПолн') or result['name']
                result['status'] = ul.get('Статус') or result['status']
            elif ip:
                fio = ip.get('ФИОРус', {})
                parts = [fio.get('Фамилия'), fio.get('Имя'), fio.get('Отчество')]
                fio_string = ' '.join(filter(None, parts))
                if fio_string:
                    result['name'] = f'ИП {fio_string}'
                result['status'] = ip.get('Статус') or result['status']
        else:
            print("[ЛОГ ПРЕДУПРЕЖДЕНИЕ] Массив 'items' пуст. Возможно, ИНН не найден.", flush=True)
                
        # --- ПАРСИНГ РИСКОВ ИЗ СКОРИНГА ---
        if isinstance(check_raw, list):
            check_root = check_raw[0] if len(check_raw) > 0 else {}
        else:
            check_root = check_raw
            
        check_items = check_root.get('items', [])
        if check_items:
            checks = check_items[0]
            
            if checks.get('МассовыйАдрес') or checks.get('mass_address'):
                result['risk'] += 20
                result['risk_factors'].append('Массовый адрес регистрации')
            if checks.get('МассовыйРуководитель') or checks.get('mass_director'):
                result['risk'] += 15
                result['risk_factors'].append('Массовый руководитель')
            if checks.get('НедостоверныеСведения') or checks.get('invalid_data'):
                result['risk'] += 30
                result['risk_factors'].append('Недостоверные сведения')
        
        if result['status'] in ['Ликвидировано', 'Ликвидирована']:
            result['risk'] = 100
            result['risk_factors'].append('Компания ликвидирована')
            
        result['risk'] = min(100, result['risk'])
        
        return jsonify(result)
        
    except requests.exceptions.Timeout:
        print("[ЛОГ ОШИБКА] Произошел таймаут запроса к api-fns.ru", file=sys.stderr, flush=True)
        return jsonify({'error': 'Таймаут API ФНС'}), 500
    except Exception as e:
        print(f"[ЛОГ КРИТИЧЕСКАЯ ОШИБКА]: {str(e)}", file=sys.stderr, flush=True)
        return jsonify({'error': f'Внутренняя ошибка парсинга: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
