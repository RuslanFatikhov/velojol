# Добавляем в config.py

import os

class Config:
    # Существующие настройки...
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///velojol.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Настройки для загрузки файлов
    UPLOAD_FOLDER = 'app/static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB максимальный размер файла
    
    # Настройки для велодорожек
    MAX_PHOTOS_PER_BIKELANE = 10
    MAX_VIDEOS_PER_BIKELANE = 5
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    
    # Настройки валидации
    MIN_TITLE_LENGTH = 3
    MIN_DESCRIPTION_LENGTH = 20
    
    # Настройки пагинации
    BIKELANES_PER_PAGE = 10
    USERS_PER_PAGE = 20

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

# Словарь конфигураций
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}