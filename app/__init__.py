from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from authlib.integrations.flask_client import OAuth
from werkzeug.exceptions import RequestEntityTooLarge
import logging
from config import Config
from app.version import load_app_version

# Инициализация расширений
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
oauth = OAuth()


def configure_logging(app):
    """Настройка логирования приложения."""
    level_name = app.config.get('LOG_LEVEL', 'INFO')
    level = getattr(logging, level_name, logging.INFO)

    app.logger.setLevel(level)
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=level,
            format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
        )

def create_app(config_class=Config):
    """Фабрика приложения Flask"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config['APP_VERSION'] = load_app_version()
    configure_logging(app)

    @app.context_processor
    def inject_app_version():
        return {'app_version': app.config['APP_VERSION']}
    
    # Инициализация расширений с приложением
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )
    oauth.register(
        name='telegram',
        client_id=app.config.get('TELEGRAM_CLIENT_ID'),
        client_secret=app.config.get('TELEGRAM_CLIENT_SECRET'),
        server_metadata_url='https://oauth.telegram.org/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid profile',
            'code_challenge_method': 'S256',
        },
    )
    
    # Настройка Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'
    login_manager.login_message_category = 'info'

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(error):
        max_upload_mb = app.config.get('MAX_UPLOAD_MB', 128)
        message = f'Размер загружаемых файлов превышает лимит {max_upload_mb} МБ'

        if (
            request.accept_mimetypes.accept_json
            or request.path.startswith('/add-bikelane')
            or request.path.startswith('/api/reviews/')
        ):
            return jsonify({
                'success': False,
                'error': message
            }), 413

        return message, 413
    
    # Импорт моделей
    from app.models import (
        User,
        BikeLane,
        Notification,
        City,
        CityRequest,
        VerificationCode,
        InfrastructurePoint,
        Review,
    )
    
    # Загрузка пользователя для Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Регистрация blueprints
    from app.routes.auth import bp as auth_bp
    from app.routes.main import bp as main_bp
    from app.routes.public import bp as public_bp
    from app.routes.reviews import bp as reviews_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(reviews_bp)
    
    # Регистрация admin blueprint если существует
    try:
        from app.routes.admin import bp as admin_bp
        app.register_blueprint(admin_bp)
    except ImportError:
        app.logger.exception('Не удалось зарегистрировать admin blueprint')
    
    return app
