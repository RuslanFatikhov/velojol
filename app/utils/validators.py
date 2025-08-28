import re
from flask import current_app

class BikeLaneValidator:
    """Валидатор для данных велодорожки"""
    
    @staticmethod
    def validate_title(title):
        """Валидация названия велодорожки"""
        errors = []
        
        if not title or not title.strip():
            errors.append("Название не может быть пустым")
        elif len(title.strip()) < current_app.config['MIN_TITLE_LENGTH']:
            errors.append(f"Название должно содержать минимум {current_app.config['MIN_TITLE_LENGTH']} символа")
        
        return errors
    
    @staticmethod
    def validate_description(description):
        """Валидация описания велодорожки"""
        errors = []
        
        if not description or not description.strip():
            errors.append("Описание не может быть пустым")
        elif len(description.strip()) < current_app.config['MIN_DESCRIPTION_LENGTH']:
            errors.append(f"Описание должно содержать минимум {current_app.config['MIN_DESCRIPTION_LENGTH']} символов")
        
        return errors
    
    @staticmethod
    def validate_track_type(track_type):
        """Валидация типа дорожки"""
        valid_types = [
            'separated_lane',      # Выделенная полоса
            'bike_path',          # Велодорожка
            'shared_lane',        # Общая полоса
            'bike_boulevard',     # Велобульвар
            'cycle_track'         # Велосипедная дорожка
        ]
        
        errors = []
        
        if not track_type:
            errors.append("Необходимо выбрать тип дорожки")
        elif track_type not in valid_types:
            errors.append("Недопустимый тип дорожки")
        
        return errors
    
    @staticmethod
    def validate_geometry(geometry_json):
        """Валидация геометрии (базовая проверка GeoJSON)"""
        errors = []
        
        if not geometry_json:
            errors.append("Необходимо нарисовать линию на карте")
            return errors
        
        try:
            import json
            geometry = json.loads(geometry_json)
            
            # Проверяем базовую структуру GeoJSON
            if not isinstance(geometry, dict):
                errors.append("Неверный формат геометрии")
            elif geometry.get('type') != 'LineString':
                errors.append("Геометрия должна быть линией")
            elif not geometry.get('coordinates'):
                errors.append("Отсутствуют координаты")
            elif len(geometry.get('coordinates', [])) < 2:
                errors.append("Линия должна содержать минимум 2 точки")
                
        except json.JSONDecodeError:
            errors.append("Неверный формат данных геометрии")
        
        return errors
    
    @staticmethod
    def validate_videos(videos_list):
        """Валидация списка видео"""
        errors = []
        
        if len(videos_list) > current_app.config['MAX_VIDEOS_PER_BIKELANE']:
            errors.append(f"Максимум {current_app.config['MAX_VIDEOS_PER_BIKELANE']} видео")
        
        # Валидация URL видео
        youtube_pattern = re.compile(r'^https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]+')
        
        for i, video_url in enumerate(videos_list):
            if video_url.strip():  # Пропускаем пустые строки
                if not (youtube_pattern.match(video_url) or video_url.endswith('.mp4')):
                    errors.append(f"Видео {i+1}: неподдерживаемый формат (только YouTube или mp4)")
        
        return errors
    
    @staticmethod
    def validate_all_data(data):
        """Комплексная валидация всех данных"""
        all_errors = {}
        
        # Валидация каждого поля
        title_errors = BikeLaneValidator.validate_title(data.get('title', ''))
        if title_errors:
            all_errors['title'] = title_errors
        
        description_errors = BikeLaneValidator.validate_description(data.get('description', ''))
        if description_errors:
            all_errors['description'] = description_errors
            
        track_type_errors = BikeLaneValidator.validate_track_type(data.get('track_type', ''))
        if track_type_errors:
            all_errors['track_type'] = track_type_errors
            
        geometry_errors = BikeLaneValidator.validate_geometry(data.get('geometry', ''))
        if geometry_errors:
            all_errors['geometry'] = geometry_errors
        
        # Валидация видео если они есть
        videos = data.get('videos', [])
        if videos:
            videos_errors = BikeLaneValidator.validate_videos(videos)
            if videos_errors:
                all_errors['videos'] = videos_errors
        
        return all_errors
