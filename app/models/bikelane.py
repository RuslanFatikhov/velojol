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
    
    # Геометрия (GeoJSON как текст)
    geometry = db.Column(db.Text, nullable=False)
    
    # Тип дорожки
    track_type = db.Column(db.String(50), nullable=False)
    
    # Медиафайлы (JSON массивы путей)
    photos = db.Column(db.Text, default='[]')  # JSON массив путей к фото
    videos = db.Column(db.Text, default='[]')  # JSON массив ссылок на видео
    
    # Статус и баллы
    status = db.Column(db.Enum('pending', 'approved', 'rejected', name='bikelane_status'), 
                      default='pending', nullable=False)
    score = db.Column(db.Integer, default=0)
    
    # Временные метки
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с пользователем (пока заглушка)
    user_id = db.Column(db.Integer, nullable=True)  # В будущем будет foreign key
    
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

    @property
    def photos_count(self):
        """Количество фотографий"""
        return len(self.get_photos_list())
    
    @property
    def videos_count(self):
        """Количество видео"""
        return len(self.get_videos_list())
