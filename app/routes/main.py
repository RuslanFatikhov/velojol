from flask_login import current_user
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
                'quality': request.form.get('quality', ''),                'has_parking': request.form.get('has_parking', 'false').lower() == 'true',                'has_markings': request.form.get('has_markings', 'false').lower() == 'true',                'has_signs': request.form.get('has_signs', 'false').lower() == 'true',                'overall_quality': request.form.get('overall_quality', ''),
                'geometry': request.form.get('geometry', ''),
                'distance': request.form.get('distance', ''),  # Новое поле дистанции
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
            
            # Проверяем дистанцию
            distance_value = None
            if form_data['distance']:
                try:
                    distance_value = float(form_data['distance'])
                    if distance_value < 10:
                        errors.append('Велодорожка должна быть длиннее 10 метров')
                    elif distance_value > 50000:  # Максимум 50 км
                        errors.append('Велодорожка не может быть длиннее 50 километров')
                except (ValueError, TypeError):
                    errors.append('Некорректное значение дистанции')
            
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
            

            # Создаем объект велодорожки БЕЗ фотографий
            bikelane = BikeLane(
                title=form_data['title'],
                description=form_data['description'],
                city=form_data['city'],
                track_type=form_data['track_type'],
                quality=int(form_data['quality']),
                has_parking=form_data['has_parking'],
                has_markings=form_data['has_markings'],
                has_signs=form_data['has_signs'],
                geometry=form_data['geometry'],
                status='pending',
                user_id=current_user.id if current_user.is_authenticated else None
            )
            
            # Устанавливаем дистанцию
            if distance_value is not None:
                bikelane.distance = distance_value
            else:
                bikelane.distance = bikelane.calculate_length() * 1000
                current_app.logger.info(f"Дистанция рассчитана автоматически: {bikelane.distance} м")
            
            # Рассчитываем общее качество велодорожки
            if form_data['overall_quality']:
                try:
                    bikelane.overall_quality = int(form_data['overall_quality'])
                except (ValueError, TypeError):
                    bikelane.overall_quality = bikelane.calculate_overall_quality()
            else:
                bikelane.overall_quality = bikelane.calculate_overall_quality()
            
            current_app.logger.info(f"Качество велодорожки: {bikelane.overall_quality}/5")
            
            # Сохраняем в базу данных СНАЧАЛА
            db.session.add(bikelane)
            db.session.flush()  # Получаем ID без коммита
            
            current_app.logger.info(f"Велодорожка создана с ID: {bikelane.id}")
            
            # Получаем загруженные файлы
            uploaded_files = request.files.getlist('photos')
            # ТЕПЕРЬ сохраняем фотографии с правильным bikelane_id
            photo_paths = []
            if uploaded_files and uploaded_files[0].filename:
                try:
                    photo_paths = FileHandler.save_uploaded_files(
                        uploaded_files,
                        current_user.id if current_user.is_authenticated else None,
                        bikelane.id  # Теперь у нас есть ID!
                    )
                    current_app.logger.info(f"Сохранено {len(photo_paths)} фотографий")
                except Exception as e:
                    current_app.logger.error(f"Ошибка при сохранении фотографий: {e}")
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'error': f'Ошибка при сохранении фотографий: {str(e)}'
                    })

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
            
            # Коммитим все изменения (bikelane уже добавлен выше)
            db.session.commit()
            
            # Логируем успешное сохранение
            current_app.logger.info(f"Велодорожка создана: ID={bikelane.id}, title={bikelane.title}, distance={bikelane.distance}м")
            
            # Возвращаем успешный JSON ответ
            return jsonify({
                'success': True,
                'message': 'Велодорожка успешно добавлена!',
                'bikelane_id': bikelane.id,
                'title': form_data['title'],
                'city': form_data['city'],
                'distance': f'{bikelane.distance:.1f} м' if bikelane.distance else None
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
                    else:
                        # Проверяем дистанцию
                        coordinates = geometry_data.get('coordinates', [])
                        # Простой расчет дистанции для валидации
                        if len(coordinates) >= 2:
                            try:
                                # Создаем временный объект для расчета дистанции
                                temp_bikelane = BikeLane()
                                temp_bikelane.geometry = geometry
                                distance = temp_bikelane.calculate_distance()
                                
                                if distance and distance < 10:
                                    errors.append('Велодорожка должна быть длиннее 10 метров')
                                elif distance and distance > 50000:
                                    errors.append('Велодорожка не может быть длиннее 50 километров')
                            except Exception:
                                # Если не удалось рассчитать дистанцию, пропускаем проверку
                                pass
                                
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

@bp.route('/@<nickname>')
def user_profile(nickname):
    """Профиль пользователя по никнейму"""
    from app.models.user import User
    from app.models.bikelane import BikeLane
    from flask_login import current_user
    
    user = User.query.filter_by(nickname=nickname).first_or_404()
    
    # Получаем велодорожки пользователя
    bikelanes = BikeLane.query.filter_by(user_id=user.id).order_by(BikeLane.created_at.desc()).all()
    
    # Статистика
    total_bikelanes = len(bikelanes)
    pending_count = sum(1 for bl in bikelanes if bl.status == 'pending')
    approved_count = sum(1 for bl in bikelanes if bl.status == 'approved')
    rejected_count = sum(1 for bl in bikelanes if bl.status == 'rejected')
    
    stats = {
        'total': total_bikelanes,
        'pending': pending_count,
        'approved': approved_count,
        'rejected': rejected_count,
        'score': user.get_total_score()
    }
    
    # Проверяем, это свой профиль или чужой
    is_own_profile = current_user.is_authenticated and current_user.id == user.id
    
    return render_template('auth/profile.html', 
                         user=user,
                         bikelanes=bikelanes,
                         stats=stats,
                         is_own_profile=is_own_profile)
