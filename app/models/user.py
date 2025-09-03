from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(UserMixin, db.Model):
    """Модель пользователя"""
    
    __tablename__ = 'users'
    
    # Основные поля
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    nickname = db.Column(db.String(64), unique=True, nullable=False, index=True)
    
    # Дополнительные поля профиля
    avatar_url = db.Column(db.String(256))
    strava_url = db.Column(db.String(256))
    komoot_url = db.Column(db.String(256))
    telegram_url = db.Column(db.String(256))
    instagram_url = db.Column(db.String(256))
    
    # Временные метки
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи с другими моделями (для будущих фич)
    # bikelanes = db.relationship('BikeLane', backref='author', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.nickname}>'
    
    def set_password(self, password):
        """Устанавливает хэш пароля"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Проверяет пароль"""
        return check_password_hash(self.password_hash, password)
    
    def get_social_links(self):
        """Возвращает словарь с социальными ссылками"""
        links = {}
        
        if self.strava_url:
            links['Strava'] = self.strava_url
        if self.komoot_url:
            links['Komoot'] = self.komoot_url
        if self.telegram_url:
            links['Telegram'] = self.telegram_url
        if self.instagram_url:
            links['Instagram'] = self.instagram_url
            
        return links
    
    @property
    def display_avatar(self):
        """Возвращает URL аватара или дефолтный"""
        if self.avatar_url:
            return self.avatar_url
        # Генерируем аватар на основе initials или используем placeholder
        return f"https://ui-avatars.com/api/?name={self.nickname}&background=3498db&color=fff&size=150"