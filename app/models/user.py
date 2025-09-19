# app/models/user.py

from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from flask import url_for

class User(UserMixin, db.Model):
    """Модель пользователя"""
    
    __tablename__ = 'users'
    
    # Основные поля
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    nickname = db.Column(db.String(64), unique=True, nullable=False, index=True)
    
    # Права доступа
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    
    # Дополнительные поля профиля
    avatar_url = db.Column(db.String(256))
    strava_url = db.Column(db.String(256))
    komoot_url = db.Column(db.String(256))
    telegram_url = db.Column(db.String(256))
    instagram_url = db.Column(db.String(256))
    
    # Временные метки
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Связи с другими моделями
    bikelanes = db.relationship('BikeLane', foreign_keys='BikeLane.user_id', backref='author', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    
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
    
    def get_bikelanes_count(self):
        """Возвращает количество велодорожек пользователя"""
        return self.bikelanes.count()
    
    def get_pending_bikelanes_count(self):
        """Возвращает количество велодорожек на модерации"""
        return self.bikelanes.filter_by(status='pending').count()
    
    def get_approved_bikelanes_count(self):
        """Возвращает количество одобренных велодорожек"""
        return self.bikelanes.filter_by(status='approved').count()
    
    def get_total_score(self):
        """Возвращает общий счет пользователя"""
        approved_bikelanes = self.bikelanes.filter_by(status='approved')
        return sum(bl.score for bl in approved_bikelanes if bl.score)
