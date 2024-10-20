import os
import sys
import json
from collections import defaultdict
from flask import Flask, render_template, jsonify, url_for, abort, send_from_directory, request
import threading
from transliterate import translit  # Если используете функцию transliterate_city_name

# Добавляем путь к виртуальному окружению (если необходимо)
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
    city = next(
        (item for country_cities in cities.values() for item in country_cities if transliterate_city_name(item["city"]) == city_name.lower()),
        None
    )
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

# ====== НОВЫЙ КОД ДЛЯ ЭКЗАМЕНА И СБОР СТАТИСТИКИ ======

# Маршрут для страницы экзамена
@app.route('/exam')
def exam():
    return render_template('exam.html')

# Маршрут для получения данных exam.json
@app.route('/exam_data')
def exam_data():
    filepath = os.path.join(app.root_path, 'exam.json')
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    else:
        return jsonify({"error": "exam.json not found"}), 404

# Создаём объект блокировки для потокобезопасной записи
lock = threading.Lock()

# Функция для сохранения результата в JSON-файл
def save_score(score):
    filepath = os.path.join(app.root_path, 'scores.json')

    with lock:
        # Проверяем, существует ли файл
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}

        # Обновляем счётчик для данного результата
        score_str = str(score)
        if score_str in data:
            data[score_str] += 1
        else:
            data[score_str] = 1

        # Сохраняем обновлённые данные
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

# Функция для получения статистики из JSON-файла
def get_stats():
    filepath = os.path.join(app.root_path, 'scores.json')
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    else:
        return {}

# Маршрут для приёма результатов экзамена
@app.route('/submit_score', methods=['POST'])
def submit_score():
    data = request.get_json()
    score = data.get('score')

    if score is not None and isinstance(score, int):
        # Проверяем, что score в допустимом диапазоне
        if 0 <= score <= 10:
            save_score(score)
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Invalid score value'}), 400
    else:
        return jsonify({'status': 'error', 'message': 'No score provided or invalid data'}), 400

# Маршрут для отображения статистики
@app.route('/stats')
def stats():
    stats_data = get_stats()
    return render_template('stats.html', stats=stats_data)

# ====== КОНЕЦ НОВОГО КОДА ======

if __name__ == "__main__":
    app.run(debug=True)
