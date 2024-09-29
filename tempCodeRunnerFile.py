from flask import Flask, render_template, jsonify, url_for
import json
import os
from jinja2 import TemplateNotFound

app = Flask(__name__)

# Определение базовой директории
BASE_DIR = os.path.dirname(os.path.abspath(__file__))



# Загрузка данных курсов из файла
def load_courses():
    filepath = os.path.join(BASE_DIR, 'course.json')
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


# Маршрут для страницы с курсами
@app.route('/course')
def course():
    courses = load_courses()
    return render_template('course/course.html', courses=courses)

# Маршрут для отображения страниц уроков
@app.route('/course/<lesson_url>')
def course_lesson(lesson_url):
    try:
        return render_template(f'course/{lesson_url}.html')
    except TemplateNotFound:
        return "Lesson not found", 404

if __name__ == "__main__":
    app.run(port=5004, debug=True)
