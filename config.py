import os
from datetime import timedelta
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    """Базовая конфигурация приложения"""
    BASE_DIR = basedir
    APP_ENV = os.environ.get('APP_ENV', 'development')
    IS_PRODUCTION = APP_ENV == 'production'
    
    # Основные настройки Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    PREFERRED_URL_SCHEME = 'https' if IS_PRODUCTION else 'http'
    
    # База данных
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'velojol.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Загрузка файлов
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    MAX_UPLOAD_MB = int(os.environ.get('MAX_UPLOAD_MB', '128'))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    MAX_PHOTOS_PER_BIKELANE = 10
    
    # Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    # По умолчанию не помечаем auth-cookie как Secure, потому что текущий прод
    # может обслуживаться по обычному HTTP. Для HTTPS можно явно включить через env.
    SESSION_COOKIE_SECURE = os.environ.get(
        'SESSION_COOKIE_SECURE',
        'False'
    ).lower() in ['true', '1', 'yes']
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = os.environ.get(
        'REMEMBER_COOKIE_SECURE',
        'False'
    ).lower() in ['true', '1', 'yes']
    SESSION_REFRESH_EACH_REQUEST = True

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    
    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.timeweb.ru'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 465)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'False').lower() in ['true', '1', 'yes']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'True').lower() in ['true', '1', 'yes']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME')
    
    # Velojol специфичные настройки
    BIKELANE_PHOTOS_MAX = 10
    BIKELANE_VIDEOS_MAX = 10
    MIN_BIKELANE_LENGTH = 50  # метров
    MAPBOX_TOKEN = os.environ.get('MAPBOX_TOKEN', '')
