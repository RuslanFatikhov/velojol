# app/routes/admin/cities.py

from flask import render_template, request, flash, redirect, url_for, jsonify
from app import db
from app.models.city import City
from . import bp, admin_required
from app.utils.file_handler import FileHandler
import json
import os
from flask import current_app
from werkzeug.utils import secure_filename


def _save_city_image(uploaded_file, filename, max_width, max_height):
    upload_path = os.path.join(current_app.static_folder, 'uploads', 'cities')
    os.makedirs(upload_path, exist_ok=True)
    safe_filename = secure_filename(filename)
    file_path = os.path.join(upload_path, safe_filename)

    uploaded_file.save(file_path)
    if not FileHandler.compress_image_to_jpeg(
        file_path,
        max_size_kb=50,
        max_width=max_width,
        max_height=max_height
    ):
        if os.path.exists(file_path):
            os.remove(file_path)
        return None

    return f'uploads/cities/{safe_filename}'


def _delete_city_image(relative_path):
    """Удаляет неиспользуемое изображение города из каталога загрузок."""
    if not relative_path or not relative_path.startswith('uploads/cities/'):
        return

    if (
        City.query.filter_by(coat_of_arms=relative_path).first()
        or City.query.filter_by(background_image=relative_path).first()
    ):
        return

    upload_root = os.path.abspath(
        os.path.join(current_app.static_folder, 'uploads', 'cities')
    )
    file_path = os.path.abspath(
        os.path.join(current_app.static_folder, relative_path)
    )
    if os.path.commonpath([upload_root, file_path]) != upload_root:
        return

    try:
        if os.path.isfile(file_path):
            os.remove(file_path)
    except OSError:
        current_app.logger.warning(
            'Не удалось удалить изображение города: %s',
            file_path,
            exc_info=True,
        )


@bp.route('/cities')
@admin_required
def cities():
    """Страница управления городами"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
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
        if coat_of_arms_file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            coat_of_arms_path = _save_city_image(
                coat_of_arms_file,
                f"{city_id}_coat.jpg",
                max_width=512,
                max_height=512
            )
            if not coat_of_arms_path:
                errors.append('Не удалось обработать герб города')
        else:
            errors.append('Герб должен быть изображением JPG, PNG или WebP')
    
    # Обрабатываем фон
    background_file = request.files.get('background_image')
    if background_file and background_file.filename:
        if background_file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            background_image_path = _save_city_image(
                background_file,
                f"{city_id}_bg.jpg",
                max_width=1920,
                max_height=1080
            )
            if not background_image_path:
                errors.append('Не удалось обработать фон города')
        else:
            errors.append('Фон должен быть изображением JPG, PNG или WebP')
    
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
    remove_coat_of_arms = request.form.get('remove_coat_of_arms') == '1'
    remove_background_image = request.form.get('remove_background_image') == '1'
    images_to_delete = []
    
    # Обработка загрузки новых файлов
    coat_of_arms_file = request.files.get('coat_of_arms')
    if coat_of_arms_file and coat_of_arms_file.filename:
        if coat_of_arms_file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            coat_path = _save_city_image(
                coat_of_arms_file,
                f"{city.city_id}_coat.jpg",
                max_width=512,
                max_height=512
            )
            if coat_path:
                if city.coat_of_arms and city.coat_of_arms != coat_path:
                    images_to_delete.append(city.coat_of_arms)
                city.coat_of_arms = coat_path
            else:
                flash('Не удалось обработать герб города', 'error')
        else:
            flash('Герб должен быть изображением JPG, PNG или WebP', 'error')
    elif remove_coat_of_arms and city.coat_of_arms:
        images_to_delete.append(city.coat_of_arms)
        city.coat_of_arms = None
    
    background_file = request.files.get('background_image')
    if background_file and background_file.filename:
        if background_file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            bg_path = _save_city_image(
                background_file,
                f"{city.city_id}_bg.jpg",
                max_width=1920,
                max_height=1080
            )
            if bg_path:
                if city.background_image and city.background_image != bg_path:
                    images_to_delete.append(city.background_image)
                city.background_image = bg_path
            else:
                flash('Не удалось обработать фон города', 'error')
        else:
            flash('Фон должен быть изображением JPG, PNG или WebP', 'error')
    elif remove_background_image and city.background_image:
        images_to_delete.append(city.background_image)
        city.background_image = None
    
    # Обновляем основные данные
    city.name = name
    city.country = country
    city.coords_lat = coords_lat
    city.coords_lng = coords_lng
    city.zoom = zoom
    city.status = status
    
    try:
        db.session.commit()
        update_cities_json()
        for image_path in set(images_to_delete):
            _delete_city_image(image_path)
        flash(f'Город "{name}" успешно обновлен!', 'success')
        return redirect(url_for('admin.cities'))
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при обновлении города', 'error')
        return redirect(url_for('admin.edit_city', city_id=city_id))
