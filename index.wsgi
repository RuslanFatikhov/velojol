import os
import sys
import json
sys.path.append('/home/c/cc91451/velojol.kz/venv/lib/python3.10/site-packages/')
from flask import Flask, render_template, jsonify, url_for
app = Flask(__name__)
application = app
# Загрузка данных городов из файла
def load_cities():
    with open('/home/c/cc91451/velojol.kz/public_html/cities.json', 'r', encoding='utf-8') as f:
        return json.load(f)
        return render_template("posts.html", articles=articles)
# Маршрут для главной страницы
@app.route('/')
def index():
    cities = load_cities()
    return render_template('index.html', cities=cities)

# Маршрут для страницы карты с передачей названия города
@app.route('/map/<city_name>')
def map(city_name):
    cities = load_cities()
    city = next((item for item in cities if item["city"].lower() == city_name.lower()), None)
    if city:
        # Передаем в шаблон не только данные города, но и его координаты в виде строки,
        # чтобы использовать их в JavaScript для инициализации карты
        return render_template('map.html', city=city)
    else:
        return "City not found", 404

@app.route('/bike-lanes/<city_name>')
def bike_lanes(city_name):
    try:
        with open(f'{city_name}.json', 'r') as f:
            bike_lanes = json.load(f)
        return jsonify(bike_lanes)
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)

