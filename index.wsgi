import os
import sys
import json
from collections import defaultdict
sys.path.append('/home/c/cc91451/velojol.kz/venv/lib/python3.10/site-packages/')
from flask import Flask, render_template, jsonify, url_for
from transliterate import translit

app = Flask(__name__)
application = app

# Загрузка данных городов из файла и сортировка по имени города
def load_cities():
    with open('/home/c/cc91451/velojol.kz/public_html/cities.json', 'r', encoding='utf-8') as f:
        cities = json.load(f)
        cities_sorted = sorted(cities, key=lambda x: x['city'])
        cities_by_country = defaultdict(list)
        for city in cities_sorted:
            cities_by_country[city['country']].append(city)
        return dict(cities_by_country)

# Функция транслитерации названий городов
def transliterate_city_name(city_name):
    return translit(city_name, 'ru', reversed=True).lower()

# Делает функцию транслитерации доступной в шаблонах
@app.context_processor
def utility_processor():
    def transliterate(city_name):
        return transliterate_city_name(city_name)
    return dict(transliterate_city_name=transliterate)

# Маршрут для главной страницы
@app.route('/')
def index():
    cities_by_country = load_cities()
    return render_template('index.html', cities_by_country=cities_by_country)

# Маршрут для страницы карты с передачей названия города
@app.route('/<city_name>')
def map(city_name):
    cities = load_cities()
    city = next((item for country_cities in cities.values() for item in country_cities if transliterate_city_name(item["city"]) == city_name.lower()), None)
    if city:
        return render_template('map.html', city=city)
    else:
        return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)
