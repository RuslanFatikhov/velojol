# app/models/bikelane.py
from app import db
from datetime import datetime
import json

class BikeLane(db.Model):
    """Модель велодорожки"""
    __tablename__ = 'bikelanes'
    
    # Основные поля
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    
    # Местоположение (связь с городами)
    city_id = db.Column(db.Integer, db.ForeignKey('cities.id'), nullable=True)
    city = db.Column(db.String(100), nullable=False)  # Временно оставляем для совместимости
    
    # Геометрия (GeoJSON как текст)
    geometry = db.Column(db.Text, nullable=False)
    
    # Тип дорожки
    track_type = db.Column(db.String(50), nullable=False)
    
    # Качество покрытия (оценка от 1 до 5)
    quality = db.Column(db.Integer, nullable=False)  # 1-5 звездочек
    
    # Медиафайлы (JSON массивы путей)
    photos = db.Column(db.Text, default='[]')  # JSON массив путей к фото
    videos = db.Column(db.Text, default='[]')  # JSON массив ссылок на видео
    
    # Статус и баллы
    status = db.Column(db.Enum('pending', 'approved', 'rejected', name='bikelane_status'),
                      default='pending', nullable=False)
    score = db.Column(db.Integer, default=0)
    
    # Комментарий админа (при отклонении или замечании)
    admin_comment = db.Column(db.Text, nullable=True)
    moderated_at = db.Column(db.DateTime, nullable=True)  # Когда была модерация
    moderated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Кто модерировал
    
    # Временные метки
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с пользователем
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Связи с другими таблицами
    moderator = db.relationship('User', foreign_keys=[moderated_by], backref='moderated_bikelanes')

    def __repr__(self):
        return f'<BikeLane {self.title}>'
    
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
        # Начисляем баллы за одобренную велодорожку
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
        base_score = 10  # Базовые баллы
        
        # Бонус за качество
        quality_bonus = {1: 0, 2: 2, 3: 5, 4: 8, 5: 12}
        score = base_score + quality_bonus.get(self.quality, 0)
        
        # Бонус за фото
        photos_count = len(self.get_photos_list())
        score += min(photos_count * 2, 10)  # Максимум 10 баллов за фото
        
        # Бонус за видео
        videos_count = len(self.get_videos_list())
        score += min(videos_count * 5, 15)  # Максимум 15 баллов за видео
        
        # Бонус за детальное описание
        if len(self.description) > 100:
            score += 5
        
        return score
    
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
        
        # Fallback к старому методу
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
