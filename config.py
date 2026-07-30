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
    MAX_PHOTOS_PER_REVIEW = 5
    MAX_REVIEW_LENGTH = 2000
    
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

    # Google OpenID Connect
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', '')
    GOOGLE_OAUTH_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

    # Telegram OpenID Connect
    TELEGRAM_CLIENT_ID = os.environ.get('TELEGRAM_CLIENT_ID', '')
    TELEGRAM_CLIENT_SECRET = os.environ.get('TELEGRAM_CLIENT_SECRET', '')
    TELEGRAM_REDIRECT_URI = os.environ.get('TELEGRAM_REDIRECT_URI', '')
    TELEGRAM_OAUTH_ENABLED = bool(TELEGRAM_CLIENT_ID and TELEGRAM_CLIENT_SECRET)

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
    MAIL_TIMEOUT = int(os.environ.get('MAIL_TIMEOUT', '10'))
    EMAIL_PROVIDER = os.environ.get('EMAIL_PROVIDER', 'smtp').lower()
    EMAIL_SEND_ASYNC = os.environ.get('EMAIL_SEND_ASYNC', 'False').lower() in ['true', '1', 'yes']
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
    RESEND_FROM = os.environ.get('RESEND_FROM') or MAIL_DEFAULT_SENDER
    
    # Velojol специфичные настройки
    BIKELANE_PHOTOS_MAX = 10
    BIKELANE_VIDEOS_MAX = 10
    MIN_BIKELANE_LENGTH = 50  # метров
    MAPBOX_TOKEN = os.environ.get('MAPBOX_TOKEN', '')
