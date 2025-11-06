# app/models/bikelane.py
from app import db
from datetime import datetime
import json
import math

class BikeLane(db.Model):
    """Модель велодорожки"""
    __tablename__ = 'bikelanes'
    
    # Основные поля
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    
    # Местоположение (связь с городами)
    city_id = db.Column(db.Integer, db.ForeignKey('cities.id'), nullable=True)
    city = db.Column(db.String(100), nullable=False)
    
    # Геометрия (GeoJSON как текст)
    geometry = db.Column(db.Text, nullable=False)
    
    # Тип дорожки
    track_type = db.Column(db.String(50), nullable=False)
    
    # Качество покрытия (оценка от 1 до 5)
    quality = db.Column(db.Integer, nullable=False)
    
    # Парковка автомобилей на велодорожке
    has_parking = db.Column(db.Boolean, default=False, nullable=False)
    
    # Наличие разметки на велодорожке
    has_markings = db.Column(db.Boolean, default=False, nullable=False)
    
    # Наличие дорожных знаков
    has_signs = db.Column(db.Boolean, default=False, nullable=False)
    
    # Общее качество велодорожки (рассчитывается автоматически от 1 до 5)
    overall_quality = db.Column(db.Integer, nullable=True)
    
    # Медиафайлы (JSON массивы путей)
    photos = db.Column(db.Text, default='[]')
    videos = db.Column(db.Text, default='[]')
    
    # Статус и баллы
    status = db.Column(db.Enum('pending', 'approved', 'rejected', name='bikelane_status'),
                      default='pending', nullable=False)
    score = db.Column(db.Integer, default=0)
    
    # Комментарий админа
    admin_comment = db.Column(db.Text, nullable=True)
    moderated_at = db.Column(db.DateTime, nullable=True)
    moderated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Временные метки
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с пользователем
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Связи с другими таблицами
    moderator = db.relationship('User', foreign_keys=[moderated_by], backref='moderated_bikelanes')

    def __repr__(self):
        return f'<BikeLane {self.title}>'
    
    def calculate_length(self):
        """Рассчитать длину велодорожки в километрах из геометрии"""
        try:
            geometry = json.loads(self.geometry)
            coordinates = geometry.get('coordinates', [])
            
            if len(coordinates) < 2:
                return 0
            
            total_distance = 0
            for i in range(len(coordinates) - 1):
                lon1, lat1 = coordinates[i]
                lon2, lat2 = coordinates[i + 1]
                
                # Используем формулу гаверсинуса для расчёта расстояния
                distance = self._haversine_distance(lat1, lon1, lat2, lon2)
                total_distance += distance
            
            return round(total_distance, 2)
            
        except (json.JSONDecodeError, KeyError, TypeError):
            return 0

    def calculate_overall_quality(self):
        """Рассчитать общее качество велодорожки (от 1 до 5)"""
        # Базовое значение в зависимости от типа велодорожки
        base_quality = {
            'separated': 5,  # Обособленная - отлично
            'bollards': 4,   # Полоса с боллардами - хорошо
            'lane': 3,       # Полоса - средне
            'shared': 3      # Велопешеходная - средне
        }
        
        quality = base_quality.get(self.track_type, 3)
        
        # Минус балл если паркуются автомобили
        if self.has_parking:
            quality -= 1
        
        # Плюс балл если есть разметка
        if self.has_markings:
            quality += 0.5
        
        # Плюс балл если есть знаки
        if self.has_signs:
            quality += 0.5
        
        # Влияние качества покрытия
        surface_quality = self.quality if self.quality else 3
        
        if surface_quality <= 2:
            quality -= 1  # Плохое покрытие - минус балл
        elif surface_quality >= 4:
            quality += 1  # Хорошее покрытие - плюс балл
        
        # Ограничиваем значение от 1 до 5
        return max(1, min(5, int(round(quality))))
    
    @staticmethod
    def _haversine_distance(lat1, lon1, lat2, lon2):
        """Расчёт расстояния между двумя точками по формуле гаверсинуса (в км)"""
        R = 6371  # Радиус Земли в километрах
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def get_photos_list(self):
        """Получить список фото как Python list"""
        try:
            return json.loads(self.photos) if self.photos else []
        except json.JSONDecodeError:
            return []
    
    def set_photos_list(self, photos_list):
        """Установить список фото из Python list"""
        self.photos = json.dumps(photos_list)
    
    def get_videos_list(self):
        """Получить список видео как Python list"""
        try:
            return json.loads(self.videos) if self.videos else []
        except json.JSONDecodeError:
            return []
    
    def set_videos_list(self, videos_list):
        """Установить список видео из Python list"""
        self.videos = json.dumps(videos_list)
    
    def get_geometry_dict(self):
        """Получить геометрию как Python dict"""
        try:
            return json.loads(self.geometry) if self.geometry else {}
        except json.JSONDecodeError:
            return {}
    
    def set_geometry_dict(self, geometry_dict):
        """Установить геометрию из Python dict"""
        self.geometry = json.dumps(geometry_dict)
    
    def approve(self, admin_user, comment=None):
        """Одобрить велодорожку"""
        self.status = 'approved'
        self.moderated_at = datetime.utcnow()
        self.moderated_by = admin_user.id
        self.admin_comment = comment
        if self.score == 0:
            self.score = self.calculate_score()
    
    def reject(self, admin_user, comment):
        """Отклонить велодорожку"""
        self.status = 'rejected'
        self.moderated_at = datetime.utcnow()
        self.moderated_by = admin_user.id
        self.admin_comment = comment
        self.score = 0
    
    def calculate_score(self):
        """Рассчитать баллы за велодорожку"""
        base_score = 5
        photos_count = len(self.get_photos_list())
        score = base_score + photos_count
        videos_count = len(self.get_videos_list())
        score += videos_count * 5
        return score
    
    def to_dict(self):
        """Конвертация в словарь для JSON API"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'city': self.city,
            'city_display': self.city_display,
            'geometry': self.get_geometry_dict(),
            'track_type': self.track_type,
            'track_type_display': self.track_type_display,
            'quality': self.quality,
            'quality_display': self.quality_display,
            'photos': self.get_photos_list(),
            'videos': self.get_videos_list(),
            'length': self.calculate_length(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'author': {
                'id': self.author.id if self.author else None,
                'nickname': self.author.nickname if self.author else 'Аноним',
                'avatar': self.author.display_avatar if self.author else None
            } if self.author else {'nickname': 'Аноним'}
        }
    
    @property
    def photos_count(self):
        """Количество фотографий"""
        return len(self.get_photos_list())
    
    @property
    def videos_count(self):
        """Количество видео"""
        return len(self.get_videos_list())
    
    @property
    def city_display(self):
        """Отображаемое название города"""
        if hasattr(self, 'city_obj') and self.city_obj:
            return self.city_obj.name
        
        import json
        import os
        from flask import current_app
        
        try:
            cities_path = os.path.join(current_app.static_folder, 'data', 'cities.json')
            with open(cities_path, 'r', encoding='utf-8') as f:
                cities_data = json.load(f)
            
            for city in cities_data.get('cities', []):
                if city.get('id') == self.city:
                    return city.get('name', self.city)
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            pass
        
        return self.city
    
    @property
    def track_type_display(self):
        """Отображаемое название типа дорожки"""
        track_type_names = {
            'lane': 'Полоса',
            'bollards': 'Полоса с боллардами', 
            'separated': 'Обособленная велодорожка',
            'shared': 'Вело-пешеходная дорожка'
        }
        return track_type_names.get(self.track_type, self.track_type)
    
    @property 
    def quality_display(self):
        """Отображаемое название качества"""
        quality_names = {
            1: 'Ужасно',
            2: 'Плохо',
            3: 'Средне', 
            4: 'Хорошо',
            5: 'Отлично'
        }
        return quality_names.get(self.quality, 'Не указано')
    
    @property
    def status_display(self):
        """Отображаемое название статуса"""
        status_names = {
            'pending': 'На модерации',
            'approved': 'Одобрено',
            'rejected': 'Отклонено'
        }
        return status_names.get(self.status, self.status)
    
    @property
    def quality_color(self):
        """Цвет для отображения на карте в зависимости от качества"""
        colors = {
            1: '#e74c3c',  # Красный
            2: '#e67e22',  # Оранжевый
            3: '#f39c12',  # Жёлтый
            4: '#2ecc71',  # Зелёный
            5: '#27ae60'   # Тёмно-зелёный
        }
        return colors.get(self.quality, '#3498db')