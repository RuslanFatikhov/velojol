from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User
import re

# Создаем Blueprint для аутентификации
bp = Blueprint('auth', __name__, url_prefix='/auth')

def validate_email(email):
    """Валидация email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_nickname(nickname):
    """Валидация никнейма"""
    # Только буквы, цифры, дефисы и подчеркивания, длина от 3 до 30 символов
    pattern = r'^[a-zA-Z0-9_-]{3,30}$'
    return re.match(pattern, nickname) is not None

def validate_url(url):
    """Базовая валидация URL"""
    if not url:
        return True  # Пустые URL валидны (необязательные поля)
    pattern = r'^https?://'
    return re.match(pattern, url) is not None

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Регистрация нового пользователя"""
    
    # Если пользователь уже авторизован, редирект в профиль
    if current_user.is_authenticated:
        return redirect(url_for('auth.profile'))
    
    if request.method == 'GET':
        return render_template('auth/register.html')
    
    # Обработка POST запроса
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    nickname = request.form.get('nickname', '').strip()
    avatar_url = request.form.get('avatar_url', '').strip()
    strava_url = request.form.get('strava_url', '').strip()
    komoot_url = request.form.get('komoot_url', '').strip()
    telegram_url = request.form.get('telegram_url', '').strip()
    instagram_url = request.form.get('instagram_url', '').strip()
    
    # Сохраняем данные формы для повторного отображения при ошибках
    form_data = {
        'email': email,
        'nickname': nickname,
        'avatar_url': avatar_url,
        'strava_url': strava_url,
        'komoot_url': komoot_url,
        'telegram_url': telegram_url,
        'instagram_url': instagram_url,
    }
    
    # Валидация
    errors = []
    
    if not email:
        errors.append('Email обязателен')
    elif not validate_email(email):
        errors.append('Некорректный формат email')
    elif User.query.filter_by(email=email).first():
        errors.append('Пользователь с таким email уже существует')
    
    if not password:
        errors.append('Пароль обязателен')
    elif len(password) < 6:
        errors.append('Пароль должен содержать минимум 6 символов')
    
    if not nickname:
        errors.append('Никнейм обязателен')
    elif not validate_nickname(nickname):
        errors.append('Никнейм может содержать только буквы, цифры, дефисы и подчеркивания (3-30 символов)')
    elif User.query.filter_by(nickname=nickname).first():
        errors.append('Пользователь с таким никнеймом уже существует')
    
    # Валидация URL'ов
    urls_to_validate = [
        ('avatar_url', avatar_url, 'Аватар'),
        ('strava_url', strava_url, 'Strava'),
        ('komoot_url', komoot_url, 'Komoot'),
        ('telegram_url', telegram_url, 'Telegram'),
        ('instagram_url', instagram_url, 'Instagram'),
    ]
    
    for field_name, url_value, field_label in urls_to_validate:
        if url_value and not validate_url(url_value):
            errors.append(f'Некорректная ссылка в поле {field_label}')
    
    # Если есть ошибки, возвращаем форму
    if errors:
        for error in errors:
            flash(error, 'error')
        return render_template('auth/register.html', form_data=form_data)
    
    try:
        # Создаем нового пользователя
        user = User(
            email=email,
            nickname=nickname,
            avatar_url=avatar_url if avatar_url else None,
            strava_url=strava_url if strava_url else None,
            komoot_url=komoot_url if komoot_url else None,
            telegram_url=telegram_url if telegram_url else None,
            instagram_url=instagram_url if instagram_url else None
        )
        user.set_password(password)
        
        # Сохраняем в базу данных
        db.session.add(user)
        db.session.commit()
        
        # Автоматически входим в систему
        login_user(user)
        
        flash(f'Добро пожаловать, {user.nickname}! Регистрация прошла успешно.', 'success')
        return redirect(url_for('auth.profile'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Ошибка при регистрации: {e}')
        flash('Произошла ошибка при регистрации. Попробуйте еще раз.', 'error')
        return render_template('auth/register.html', form_data=form_data)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Вход пользователя в систему"""
    
    # Если пользователь уже авторизован, редирект в профиль
    if current_user.is_authenticated:
        return redirect(url_for('auth.profile'))
    
    if request.method == 'GET':
        return render_template('auth/login.html')
    
    # Обработка POST запроса
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    remember_me = request.form.get('remember_me', False)
    
    # Сохраняем email для повторного отображения при ошибке
    form_data = {'email': email}
    
    # Валидация
    if not email:
        flash('Email обязателен', 'error')
        return render_template('auth/login.html', form_data=form_data)
    
    if not password:
        flash('Пароль обязателен', 'error')
        return render_template('auth/login.html', form_data=form_data)
    
    # Ищем пользователя в базе данных
    user = User.query.filter_by(email=email).first()
    
    if not user or not user.check_password(password):
        flash('Неверный email или пароль', 'error')
        return render_template('auth/login.html', form_data=form_data)
    
    try:
        # Входим в систему
        login_user(user, remember=bool(remember_me))
        
        flash(f'Добро пожаловать, {user.nickname}!', 'success')
        
        # Редирект на запрашиваемую страницу или в профиль
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('auth.profile')
        
        return redirect(next_page)
        
    except Exception as e:
        current_app.logger.error(f'Ошибка при входе: {e}')
        flash('Произошла ошибка при входе. Попробуйте еще раз.', 'error')
        return render_template('auth/login.html', form_data=form_data)

@bp.route('/logout')
@login_required
def logout():
    """Выход пользователя из системы"""
    nickname = current_user.nickname
    logout_user()
    flash(f'До свидания, {nickname}!', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/profile')
@login_required
def profile():
    """Профиль пользователя"""
    return render_template('auth/profile.html', user=current_user)