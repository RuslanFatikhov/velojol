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
        
        # Получаем данные из формы
        form_data = {
            'title': request.form.get('title', '').strip(),
            'description': request.form.get('description', '').strip(),
            'track_type': request.form.get('track_type', ''),
            'geometry': request.form.get('geometry', ''),
        }
        
        # Получаем видео (до 10 штук)
        videos = []
        for i in range(current_app.config['MAX_VIDEOS_PER_BIKELANE']):
            video_url = request.form.get(f'video_{i}', '').strip()
            if video_url:
                videos.append(video_url)
        form_data['videos'] = videos
        
        # Валидируем данные
        errors = BikeLaneValidator.validate_all_data(form_data)
        
        # Получаем загруженные файлы
        uploaded_files = request.files.getlist('photos')
        if len(uploaded_files) > current_app.config['MAX_PHOTOS_PER_BIKELANE']:
            if 'photos' not in errors:
                errors['photos'] = []
            errors['photos'].append(f"Максимум {current_app.config['MAX_PHOTOS_PER_BIKELANE']} фотографий")
        
        # Если есть ошибки - возвращаем форму с ошибками
        if errors:
            for field, field_errors in errors.items():
                for error in field_errors:
                    flash(error, 'error')
            return render_template('add_bikelane.html', form_data=form_data, errors=errors)
        
        try:
            # Создаем объект велодорожки
            bikelane = BikeLane(
                title=form_data['title'],
                description=form_data['description'],
                track_type=form_data['track_type'],
                geometry=form_data['geometry'],
                status='pending',
                user_id=None  # Пока без авторизации
            )
            
            # Сохраняем видео
            if videos:
                bikelane.set_videos_list(videos)
            
            # Сохраняем в базу данных
            db.session.add(bikelane)
            db.session.commit()
            
            # Сохраняем фотографии после создания записи (нужен ID)
            if uploaded_files and uploaded_files[0].filename:
                saved_photos = FileHandler.save_uploaded_files(
                    uploaded_files, 
                    bikelane.user_id, 
                    bikelane.id
                )
                
                if saved_photos:
                    bikelane.set_photos_list(saved_photos)
                    db.session.commit()
            
            flash('Велодорожка отправлена на модерацию!', 'success')
            return redirect(url_for('main.add_bikelane'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Ошибка при сохранении велодорожки: {e}")
            flash('Произошла ошибка при сохранении данных', 'error')
            return render_template('add_bikelane.html', form_data=form_data)

@bp.route('/api/validate-geometry', methods=['POST'])
def validate_geometry():
    """API для валидации геометрии"""
    try:
        data = request.get_json()
        geometry = data.get('geometry', '')
        
        errors = BikeLaneValidator.validate_geometry(geometry)
        
        return jsonify({
            'valid': len(errors) == 0,
            'errors': errors
        })
        
    except Exception as e:
        return jsonify({
            'valid': False,
            'errors': ['Ошибка при валидации геометрии']
        }), 400
