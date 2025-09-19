from app import db
from datetime import datetime


class City(db.Model):
    """
    Модель для городов в системе Velojol
    """
    __tablename__ = 'cities'
    
    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.String(50), unique=True, nullable=False)  # например "almaty"
    name = db.Column(db.String(100), nullable=False)  # "Алматы"
    country = db.Column(db.String(100), nullable=False)  # "Казахстан"
    distance = db.Column(db.Integer, default=0)  # километры велодорожек
    rating = db.Column(db.Float, default=0.0)  # рейтинг города
    coords_lat = db.Column(db.Float, nullable=False)  # широта
    coords_lng = db.Column(db.Float, nullable=False)  # долгота
    zoom = db.Column(db.Integer, default=12)  # уровень зума для карты
    status = db.Column(db.String(20), default='active')  # active, inactive
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с велодорожками
    bikelanes = db.relationship('BikeLane', backref='city_obj', lazy=True)
    
    def __repr__(self):
        return f'<City {self.name}>'
    
    def to_dict(self):
        """Конвертация в словарь для JSON API"""
        return {
            'id': self.city_id,
            'name': self.name,
            'country': self.country,
            'distance': self.distance,
            'rating': self.rating,
            'coords': [self.coords_lat, self.coords_lng],
            'zoom': self.zoom
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
