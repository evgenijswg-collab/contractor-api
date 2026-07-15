from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)  # Разрешает запросы с GitHub Pages

FNS_API_KEY = os.environ.get('FNS_API_KEY')

@app.route('/api/check-company')
def check_company():
    inn = request.args.get('inn')
    
    # Запрос к api-fns.ru
    egr_resp = requests.get('https://api-fns.ru/api/egr', params={
        'req': inn, 'key': FNS_API_KEY
    })
    egr_data = egr_resp.json()
    
    # Парсим и возвращаем
    company = egr_data.get('items', [{}])[0] if egr_data.get('items') else {}
    
    return jsonify({
        'inn': inn,
        'name': company.get('ЮЛ', {}).get('НаимСокр', 'Неизвестно'),
        'status': company.get('ЮЛ', {}).get('Статус', '—')
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
