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
    is_banned = db.Column(db.Boolean, default=False, nullable=False)
    ban_reason = db.Column(db.Text, nullable=True)
    manual_score = db.Column(db.Integer, default=0, nullable=False)  # Баллы от админа
    banned_at = db.Column(db.DateTime, nullable=True)
    banned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
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
    
    @property
    def display_avatar(self):
        """Возвращает URL аватара для отображения"""
        print(f"DEBUG: display_avatar called, avatar_url = {self.avatar_url}")
        
        if self.avatar_url:
            # Если это загруженный файл (начинается с uploads/)
            if self.avatar_url.startswith('uploads/'):
                avatar_url = url_for('static', filename=self.avatar_url)
                print(f"DEBUG: Generated avatar URL: {avatar_url}")
                return avatar_url
            # Если это внешняя ссылка
            elif self.avatar_url.startswith('http'):
                return self.avatar_url
            # Если это относительный путь к статическому файлу
            else:
                return url_for('static', filename=self.avatar_url)
        
        # Дефолтный аватар
        default_url = url_for('static', filename='img/default-avatar.svg')
        print(f"DEBUG: Using default avatar: {default_url}")
        return default_url
    
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
        return sum(bl.score for bl in approved_bikelanes if bl.score) + self.manual_score
