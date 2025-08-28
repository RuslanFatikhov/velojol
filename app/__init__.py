from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os

# Инициализация расширений
db = SQLAlchemy()
migrate = Migrate()

def create_app(config_name=None):
    """Фабрика приложений Flask"""
    
    app = Flask(__name__)
    
    # Загрузка конфигурации
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    from config import config
    app.config.from_object(config[config_name])
    
    # Инициализация расширений
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Создание папки для загрузок если её нет
    uploads_dir = os.path.join(app.instance_path, '..', app.config['UPLOAD_FOLDER'])
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Регистрация Blueprint'ов
    from app.routes import main
    app.register_blueprint(main.bp)
    
    # Импорт моделей (для корректной работы миграций)
    from app.models import bikelane
    
    return app