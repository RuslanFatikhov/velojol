# app/routes/admin/cities.py

from flask import render_template, request, flash, redirect, url_for, jsonify
from app import db
from app.models.city import City
from . import bp, admin_required
import json
import os
from flask import current_app
from werkzeug.utils import secure_filename

@bp.route('/cities')
@admin_required
def cities():
    """Страница управления городами"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    cities = City.query.order_by(City.name).paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    return render_template('admin/cities.html', cities=cities)

@bp.route('/cities/add', methods=['GET', 'POST'])
@admin_required
def add_city():
    """Добавление нового города"""
    if request.method == 'GET':
        return render_template('admin/add_city.html', form_data={})
    
    # Получаем данные из формы
    city_id = request.form.get('city_id', '').strip().lower()
    name = request.form.get('name', '').strip()
    country = request.form.get('country', '').strip()
    coords_lat = request.form.get('coords_lat', type=float)
    coords_lng = request.form.get('coords_lng', type=float)
    zoom = request.form.get('zoom', 12, type=int)
    
    # Валидация
    errors = []
    
    if not city_id:
        errors.append('ID города обязателен')
    elif City.query.filter_by(city_id=city_id).first():
        errors.append('Город с таким ID уже существует')
    
    if not name:
        errors.append('Название города обязательно')
    
    if not country:
        errors.append('Страна обязательна')
    
    if coords_lat is None or coords_lng is None:
        errors.append('Координаты обязательны')
    elif not (-90 <= coords_lat <= 90):
        errors.append('Некорректная широта')
    elif not (-180 <= coords_lng <= 180):
        errors.append('Некорректная долгота')
    
    if not (8 <= zoom <= 18):
        errors.append('Уровень зума должен быть от 8 до 18')
    
    # Обработка загрузки файлов
    coat_of_arms_path = None
    background_image_path = None
    
    # Обрабатываем герб
    coat_of_arms_file = request.files.get('coat_of_arms')
    if coat_of_arms_file and coat_of_arms_file.filename:
        if coat_of_arms_file.filename.lower().endswith('.png'):
            filename = secure_filename(f"{city_id}_coat.png")
            upload_path = os.path.join(current_app.static_folder, 'uploads', 'cities')
            os.makedirs(upload_path, exist_ok=True)
            file_path = os.path.join(upload_path, filename)
            coat_of_arms_file.save(file_path)
            coat_of_arms_path = f'uploads/cities/{filename}'
        else:
            errors.append('Герб должен быть в формате PNG')
    
    # Обрабатываем фон
    background_file = request.files.get('background_image')
    if background_file and background_file.filename:
        if background_file.filename.lower().endswith(('.jpg', '.jpeg')):
            filename = secure_filename(f"{city_id}_bg.jpg")
            upload_path = os.path.join(current_app.static_folder, 'uploads', 'cities')
            os.makedirs(upload_path, exist_ok=True)
            file_path = os.path.join(upload_path, filename)
            background_file.save(file_path)
            background_image_path = f'uploads/cities/{filename}'
        else:
            errors.append('Фон должен быть в формате JPG')
    
    if errors:
        for error in errors:
            flash(error, 'error')
        
        form_data = {
            'city_id': city_id,
            'name': name,
            'country': country,
            'coords_lat': coords_lat,
            'coords_lng': coords_lng,
            'zoom': zoom
        }
        return render_template('admin/add_city.html', form_data=form_data)
    
    try:
        # Создаем новый город
        city = City(
            city_id=city_id,
            name=name,
            country=country,
            coords_lat=coords_lat,
            coords_lng=coords_lng,
            zoom=zoom,
            status='active'
        )
        
        if coat_of_arms_path:
            city.coat_of_arms = coat_of_arms_path
        if background_image_path:
            city.background_image = background_image_path
        
        db.session.add(city)
        db.session.commit()
        
        # Обновляем cities.json файл
        update_cities_json()
        
        flash(f'Город "{name}" успешно добавлен!', 'success')
        return redirect(url_for('admin.cities'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Ошибка при добавлении города: {e}')
        flash('Произошла ошибка при добавлении города', 'error')
        return redirect(url_for('admin.add_city'))

@bp.route('/cities/<int:city_id>/delete', methods=['POST'])
@admin_required
def delete_city(city_id):
    """Удаление города"""
    city = City.query.get_or_404(city_id)
    
    # Проверяем, есть ли велодорожки в этом городе
    bikelanes_count = len(city.bikelanes)
    if bikelanes_count > 0:
        flash(f'Нельзя удалить город "{city.name}" - в нем есть {bikelanes_count} велодорожек', 'error')
        return redirect(url_for('admin.cities'))
    
    try:
        city_name = city.name
        db.session.delete(city)
        db.session.commit()
        
        # Обновляем cities.json файл
        update_cities_json()
        
        flash(f'Город "{city_name}" успешно удален!', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Ошибка при удалении города: {e}')
        flash('Произошла ошибка при удалении города', 'error')
    
    return redirect(url_for('admin.cities'))

def update_cities_json():
    """Обновляет файл cities.json из данных БД"""
    try:
        # Получаем все активные города
        cities = City.query.filter_by(status='active').order_by(City.name).all()
        
        # Формируем данные для JSON
        cities_data = {
            'cities': [city.to_dict() for city in cities]
        }
        
        # Путь к файлу cities.json
        cities_file_path = os.path.join(current_app.static_folder, 'data', 'cities.json')
        
        # Создаем директорию если не существует
        os.makedirs(os.path.dirname(cities_file_path), exist_ok=True)
        
        # Записываем в файл
        with open(cities_file_path, 'w', encoding='utf-8') as f:
            json.dump(cities_data, f, ensure_ascii=False, indent=2)
            
        current_app.logger.info('Файл cities.json успешно обновлен')
        
    except Exception as e:
        current_app.logger.error(f'Ошибка при обновлении cities.json: {e}')

@bp.route('/cities/<int:city_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_city(city_id):
    """Редактирование города"""
    city = City.query.get_or_404(city_id)
    
    if request.method == 'GET':
        form_data = {
            'city_id': city.city_id,
            'name': city.name,
            'country': city.country,
            'coords_lat': city.coords_lat,
            'coords_lng': city.coords_lng,
            'zoom': city.zoom,
            'status': city.status
        }
        return render_template('admin/edit_city.html', city=city, form_data=form_data)
    
    # Обработка POST запроса
    name = request.form.get('name', '').strip()
    country = request.form.get('country', '').strip()
    coords_lat = request.form.get('coords_lat', type=float)
    coords_lng = request.form.get('coords_lng', type=float)
    zoom = request.form.get('zoom', 12, type=int)
    status = request.form.get('status', 'active')
    
    # Обработка загрузки новых файлов
    coat_of_arms_file = request.files.get('coat_of_arms')
    if coat_of_arms_file and coat_of_arms_file.filename:
        if coat_of_arms_file.filename.lower().endswith('.png'):
            filename = secure_filename(f"{city.city_id}_coat.png")
            upload_path = os.path.join(current_app.static_folder, 'uploads', 'cities')
            os.makedirs(upload_path, exist_ok=True)
            file_path = os.path.join(upload_path, filename)
            coat_of_arms_file.save(file_path)
            city.coat_of_arms = f'uploads/cities/{filename}'
    
    background_file = request.files.get('background_image')
    if background_file and background_file.filename:
        if background_file.filename.lower().endswith(('.jpg', '.jpeg')):
            filename = secure_filename(f"{city.city_id}_bg.jpg")
            upload_path = os.path.join(current_app.static_folder, 'uploads', 'cities')
            os.makedirs(upload_path, exist_ok=True)
            file_path = os.path.join(upload_path, filename)
            background_file.save(file_path)
            city.background_image = f'uploads/cities/{filename}'
    
    # Обновляем основные данные
    city.name = name
    city.country = country
    city.coords_lat = coords_lat
    city.coords_lng = coords_lng
    city.zoom = zoom
    city.status = status
    
    try:
        db.session.commit()
        flash(f'Город "{name}" успешно обновлен!', 'success')
        return redirect(url_for('admin.cities'))
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при обновлении города', 'error')
        return redirect(url_for('admin.edit_city', city_id=city_id))
