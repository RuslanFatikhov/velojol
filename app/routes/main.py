# app/routes/main.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from app import db
from app.models.bikelane import BikeLane
from app.utils.validators import BikeLaneValidator
from app.utils.file_handler import FileHandler
import json

# Создаем Blueprint
bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    """Главная страница"""
    return render_template('base.html')

@bp.route('/add-bikelane', methods=['GET', 'POST'])
def add_bikelane():
    """Страница добавления велодорожки"""
    
    if request.method == 'GET':
        # Отображаем форму
        return render_template('add_bikelane.html')
    
    elif request.method == 'POST':
        # Обрабатываем данные формы
        
        try:
            # Получаем данные из формы
            form_data = {
                'city': request.form.get('city', '').strip(),
                'title': request.form.get('title', '').strip(),
                'description': request.form.get('description', '').strip(),
                'track_type': request.form.get('track_type', ''),
                'quality': request.form.get('quality', ''),
                'geometry': request.form.get('geometry', ''),
                'video_url': request.form.get('video_url', '').strip(),
            }
            
            # Базовая валидация на сервере
            errors = []
            
            # Проверяем обязательные поля
            if not form_data['city']:
                errors.append('Необходимо выбрать город')
            
            if len(form_data['title']) < 3:
                errors.append('Название должно содержать минимум 3 символа')
            
            if len(form_data['description']) < 20:
                errors.append('Описание должно содержать минимум 20 символов')
            
            if not form_data['track_type']:
                errors.append('Необходимо выбрать тип дорожки')
            
            if not form_data['quality']:
                errors.append('Необходимо оценить качество покрытия')
            
            # Проверяем геометрию
            if not form_data['geometry']:
                errors.append('Необходимо нарисовать линию на карте')
            else:
                try:
                    geometry_data = json.loads(form_data['geometry'])
                    if (not geometry_data.get('coordinates') or 
                        len(geometry_data.get('coordinates', [])) < 2):
                        errors.append('Линия должна содержать минимум 2 точки')
                except (json.JSONDecodeError, TypeError):
                    errors.append('Ошибка в данных геометрии')
            
            # Проверяем допустимые типы велодорожек
            allowed_track_types = ['lane', 'bollards', 'separated', 'shared']
            if form_data['track_type'] not in allowed_track_types:
                errors.append('Недопустимый тип дорожки')
            
            # Если есть ошибки - возвращаем JSON с ошибками
            if errors:
                return jsonify({
                    'success': False,
                    'error': 'Ошибки валидации: ' + '; '.join(errors)
                })
            
            # Получаем загруженные файлы
            uploaded_files = request.files.getlist('photos')
            photo_paths = []
            
            # Обрабатываем фотографии (максимум 10)
            if uploaded_files and uploaded_files[0].filename:
                max_photos = getattr(current_app.config, 'MAX_PHOTOS_PER_BIKELANE', 10)
                
                if len(uploaded_files) > max_photos:
                    return jsonify({
                        'success': False,
                        'error': f'Максимум {max_photos} фотографий'
                    })
                
                # Сохраняем файлы через FileHandler или напрямую
                try:
                    # Если есть FileHandler, используем его
                    if hasattr(FileHandler, 'save_uploaded_files'):
                        photo_paths = FileHandler.save_uploaded_files(
                            uploaded_files, 
                            None,  # user_id пока None 
                            None   # bikelane_id установим после создания
                        )
                    else:
                        # Простое сохранение файлов
                        import os
                        from werkzeug.utils import secure_filename
                        import time
                        
                        upload_folder = os.path.join(current_app.static_folder, 'uploads', 'bikelanes')
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        for i, photo in enumerate(uploaded_files[:max_photos]):
                            if photo and photo.filename:
                                # Генерируем безопасное имя файла
                                timestamp = int(time.time())
                                filename = secure_filename(f"{timestamp}_{i}_{photo.filename}")
                                filepath = os.path.join(upload_folder, filename)
                                photo.save(filepath)
                                photo_paths.append(f'uploads/bikelanes/{filename}')
                                
                except Exception as e:
                    current_app.logger.error(f"Ошибка при сохранении фотографий: {e}")
                    return jsonify({
                        'success': False,
                        'error': 'Ошибка при сохранении фотографий'
                    })
            
            # Создаем объект велодорожки
            bikelane = BikeLane(
                title=form_data['title'],
                description=form_data['description'],
                city=form_data['city'],
                track_type=form_data['track_type'],
                quality=int(form_data['quality']),
                geometry=form_data['geometry'],
                status='pending',
                user_id=None  # Пока без авторизации
            )
            
            # Устанавливаем фотографии и видео
            if photo_paths:
                if hasattr(bikelane, 'set_photos_list'):
                    bikelane.set_photos_list(photo_paths)
                else:
                    # Если метода нет, сохраняем как JSON
                    bikelane.photos = json.dumps(photo_paths)
            
            # Сохраняем видео
            videos = []
            if form_data['video_url']:
                videos = [form_data['video_url']]
            
            if videos:
                if hasattr(bikelane, 'set_videos_list'):
                    bikelane.set_videos_list(videos)
                else:
                    # Если метода нет, сохраняем как JSON
                    bikelane.videos = json.dumps(videos)
            
            # Сохраняем в базу данных
            db.session.add(bikelane)
            db.session.commit()
            
            # Логируем успешное сохранение
            current_app.logger.info(f"Велодорожка создана: ID={bikelane.id}, title={bikelane.title}")
            
            # Возвращаем успешный JSON ответ
            return jsonify({
                'success': True,
                'message': 'Велодорожка успешно добавлена!',
                'bikelane_id': bikelane.id,
                'title': form_data['title'],
                'city': form_data['city']
            })
            
        except Exception as e:
            # Откатываем транзакцию при ошибке
            db.session.rollback()
            
            # Логируем ошибку
            current_app.logger.error(f"Ошибка при сохранении велодорожки: {e}")
            
            # Возвращаем JSON с ошибкой
            return jsonify({
                'success': False,
                'error': f'Ошибка сервера: {str(e)}'
            })

@bp.route('/api/validate-geometry', methods=['POST'])
def validate_geometry():
    """API для валидации геометрии"""
    try:
        data = request.get_json()
        geometry = data.get('geometry', '')
        
        # Используем BikeLaneValidator если он есть
        if hasattr(BikeLaneValidator, 'validate_geometry'):
            errors = BikeLaneValidator.validate_geometry(geometry)
        else:
            # Простая валидация геометрии
            errors = []
            if not geometry:
                errors.append('Геометрия не может быть пустой')
            else:
                try:
                    geometry_data = json.loads(geometry)
                    if geometry_data.get('type') != 'LineString':
                        errors.append('Геометрия должна быть типа LineString')
                    elif (not geometry_data.get('coordinates') or 
                          len(geometry_data.get('coordinates', [])) < 2):
                        errors.append('Линия должна содержать минимум 2 точки')
                except (json.JSONDecodeError, TypeError):
                    errors.append('Некорректный формат геометрии')
        
        return jsonify({
            'valid': len(errors) == 0,
            'errors': errors
        })
        
    except Exception as e:
        current_app.logger.error(f"Ошибка валидации геометрии: {e}")
        return jsonify({
            'valid': False,
            'errors': ['Ошибка при валидации геометрии']
        }), 400