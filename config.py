import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

class Config:
    """Базовая конфигурация приложения"""
    
    # Flask настройки
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    
    # База данных
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///velojol.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Настройки загрузки файлов
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'app/static/uploads')
    
    # Допустимые форматы изображений
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    
    # Ограничения для велодорожек
    MAX_PHOTOS_PER_BIKELANE = 10
    MAX_VIDEOS_PER_BIKELANE = 10
    MIN_TITLE_LENGTH = 3
    MIN_DESCRIPTION_LENGTH = 20

class DevelopmentConfig(Config):
    """Конфигурация для разработки"""
    DEBUG = True

class ProductionConfig(Config):
    """Конфигурация для продакшена"""
    DEBUG = False

# Словарь конфигураций
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
