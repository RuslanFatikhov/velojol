from app import db
from datetime import datetime
import math


class City(db.Model):
    """
    Модель для городов в системе Velojol
    """
    __tablename__ = 'cities'
    
    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    distance = db.Column(db.Integer, default=0)  # километры велодорожек (кэш)
    rating = db.Column(db.Float, default=0.0)  # рейтинг города (кэш)
    coords_lat = db.Column(db.Float, nullable=False)
    coords_lng = db.Column(db.Float, nullable=False)
    zoom = db.Column(db.Integer, default=12)
    coat_of_arms = db.Column(db.String(256), nullable=True)
    background_image = db.Column(db.String(256), nullable=True)
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с велодорожками
    bikelanes = db.relationship('BikeLane', backref='city_obj', lazy=True)
    
    def __repr__(self):
        return f'<City {self.name}>'
    
    def get_approved_bikelanes(self):
        """Получить только одобренные велодорожки"""
        return [bl for bl in self.bikelanes if bl.status == 'approved']
    
    def get_total_distance(self):
        """Рассчитать общую протяжённость велодорожек в км"""
        total = 0
        for bikelane in self.get_approved_bikelanes():
            length = bikelane.calculate_length()
            if length:
                total += length
        return round(total, 2)
    
    def get_average_rating(self):
        """Рассчитать средний рейтинг (качество покрытия)"""
        approved = self.get_approved_bikelanes()
        if not approved:
            return 0.0
        
        total_quality = sum(bl.quality for bl in approved)
        return round(total_quality / len(approved), 1)
    
    def get_bikelanes_count(self):
        """Количество одобренных велодорожек"""
        return len(self.get_approved_bikelanes())
    
    def update_stats(self):
        """Обновить кэшированную статистику"""
        self.distance = int(self.get_total_distance())
        self.rating = self.get_average_rating()
    
    def to_dict(self):
        """Конвертация в словарь для JSON API"""
        return {
            'id': self.city_id,
            'name': self.name,
            'country': self.country,
            'distance': self.get_total_distance(),
            'rating': self.get_average_rating(),
            'coords': [self.coords_lat, self.coords_lng],
            'zoom': self.zoom,
            'bikelanes_count': self.get_bikelanes_count(),
            'coat_of_arms': self.coat_of_arms,
            'background_image': self.background_image
        }
    
    @staticmethod
    def from_json_data(data):
        """Создание объекта City из JSON данных"""
        return City(
            city_id=data['id'],
            name=data['name'],
            country=data['country'],
            distance=data.get('distance', 0),
            rating=data.get('rating', 0.0),
            coords_lat=data['coords'][0],
            coords_lng=data['coords'][1],
            zoom=data.get('zoom', 12)
        )