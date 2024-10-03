import os
import sys
import json
from collections import defaultdict
from flask import Flask, render_template, jsonify, url_for, abort

# Добавляем путь к виртуальному окружению
sys.path.append('/home/c/cc91451/velojol.kz/venv/lib/python3.10/site-packages/')

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

# Загрузка данных для маршрутов Almaty
def load_routes():
    with open('/home/c/cc91451/velojol.kz/public_html/almaty_routes.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# Группировка маршрутов по группе
def group_routes_by_group(routes):
    grouped_routes = defaultdict(list)
    for route in routes:
        grouped_routes[route['group']].append(route)
    return grouped_routes

# Загрузка данных курсов из файла
def load_courses():
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'course.json')
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

# Функция транслитерации названий городов
def transliterate_city_name(city_name):
    return translit(city_name, 'ru', reversed=True).lower()

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

# Маршрут для страницы Almaty_routes
@app.route('/almaty_routes')
def almaty_routes():
    routes = load_routes()
    grouped_routes = group_routes_by_group(routes)
    return render_template('almaty_routes.html', groups=grouped_routes)

# Маршрут для отображения конкретного маршрута
@app.route('/route/<route_id>')
def route_detail(route_id):
    routes = load_routes()
    route = next((route for route in routes if route['id'] == route_id), None)
    if route:
        same_group_routes = [r for r in routes if r['group'] == route['group'] and r['id'] != route_id]
        return render_template('route.html', route=route, same_group_routes=same_group_routes, route_id=route_id)
    else:
        return "Route not found", 404

# Маршрут для получения списка изображений в папке
@app.route('/api/photos/<path:folder>')
def list_photos(folder):
    folder_path = os.path.join('/home/c/cc91451/velojol.kz/public_html', folder)
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        return jsonify(files)
    else:
        return jsonify([]), 404

# Маршрут для страницы с курсами
@app.route('/course')
def course():
    courses = load_courses()
    return render_template('course/course.html', courses=courses)

# Маршрут для отображения страниц уроков
@app.route('/course/<lesson_url>')
def course_lesson(lesson_url):
    courses = load_courses()
    
    # Ищем нужный урок по URL
    lesson = next((lesson for lesson in courses if lesson['url'] == lesson_url), None)
    
    # Если урок найден, рендерим его шаблон
    if lesson:
        return render_template(f'course/{lesson_url}.html', lesson=lesson)
    else:
        return render_template('404.html'), 404



if __name__ == "__main__":
    app.run(debug=True)
