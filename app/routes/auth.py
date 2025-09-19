# app/routes/auth.py

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
    # Получаем статистику пользователя
    user_stats = {
        'bikelanes_total': current_user.get_bikelanes_count(),
        'bikelanes_pending': current_user.get_pending_bikelanes_count(),
        'bikelanes_approved': current_user.get_approved_bikelanes_count(),
        'total_score': current_user.get_total_score()
    }
    
    return render_template('auth/profile.html', user=current_user, user_stats=user_stats)

@bp.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Редактирование профиля пользователя"""
    
    import os
    from datetime import datetime
    
    if request.method == 'GET':
        # Заполняем форму текущими данными пользователя
        form_data = {
            'nickname': current_user.nickname,
            'email': current_user.email,
            'strava_url': current_user.strava_url or '',
            'komoot_url': current_user.komoot_url or '',
            'telegram_url': current_user.telegram_url or '',
            'instagram_url': current_user.instagram_url or ''
        }
        return render_template('auth/edit_profile.html', form_data=form_data)
    
    # Обработка POST запроса
    nickname = request.form.get('nickname', '').strip()
    email = request.form.get('email', '').strip().lower()
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    strava_url = request.form.get('strava_url', '').strip()
    komoot_url = request.form.get('komoot_url', '').strip()
    telegram_url = request.form.get('telegram_url', '').strip()
    instagram_url = request.form.get('instagram_url', '').strip()
    
    # Обработка загрузки аватара
    avatar_file = request.files.get('avatar')
    avatar_relative_path = None
    
    print(f"DEBUG: Avatar file received: {avatar_file}")
    if avatar_file:
        print(f"DEBUG: Avatar filename: {avatar_file.filename}")
    
    # Сохраняем данные формы для повторного отображения при ошибках
    form_data = {
        'nickname': nickname,
        'email': email,
        'strava_url': strava_url,
        'komoot_url': komoot_url,
        'telegram_url': telegram_url,
        'instagram_url': instagram_url,
    }
    
    # Валидация
    errors = []
    
    # Проверка никнейма
    if not nickname:
        errors.append('Никнейм обязателен')
    elif not validate_nickname(nickname):
        errors.append('Никнейм может содержать только буквы, цифры, дефисы и подчеркивания (3-30 символов)')
    elif nickname != current_user.nickname and User.query.filter_by(nickname=nickname).first():
        errors.append('Пользователь с таким никнеймом уже существует')
    
    # Проверка email
    if not email:
        errors.append('Email обязателен')
    elif not validate_email(email):
        errors.append('Некорректный формат email')
    elif email != current_user.email and User.query.filter_by(email=email).first():
        errors.append('Пользователь с таким email уже существует')
    
    # Проверка смены пароля
    password_change_requested = bool(current_password or new_password or confirm_password)
    
    if password_change_requested:
        if not current_password:
            errors.append('Введите текущий пароль для смены')
        elif not current_user.check_password(current_password):
            errors.append('Неверный текущий пароль')
        
        if not new_password:
            errors.append('Введите новый пароль')
        elif len(new_password) < 6:
            errors.append('Новый пароль должен содержать минимум 6 символов')
        
        if new_password != confirm_password:
            errors.append('Пароли не совпадают')
    
    # Обработка загрузки аватара
    if avatar_file and avatar_file.filename:
        print("DEBUG: Processing avatar upload...")
        
        # Проверка типа файла
        allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
        file_ext = avatar_file.filename.rsplit('.', 1)[1].lower() if '.' in avatar_file.filename else ''
        
        if file_ext not in allowed_extensions:
            errors.append('Недопустимый формат файла аватара. Разрешены: JPG, PNG, GIF, WebP')
        else:
            # Проверка размера файла (максимум 5MB)
            avatar_file.seek(0, 2)  # Переходим в конец файла
            file_size = avatar_file.tell()  # Получаем размер
            avatar_file.seek(0)  # Возвращаемся в начало
            
            if file_size > 5 * 1024 * 1024:  # 5MB
                errors.append('Размер файла аватара не должен превышать 5MB')
            else:
                try:
                    # Создаем папку для аватаров пользователя в static
                    static_folder = current_app.static_folder
                    user_avatar_dir = os.path.join(static_folder, 'uploads', 'avatars', str(current_user.id))
                    os.makedirs(user_avatar_dir, exist_ok=True)
                    
                    # Генерируем уникальное имя файла
                    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                    filename = f"avatar_{timestamp}.{file_ext}"
                    avatar_path = os.path.join(user_avatar_dir, filename)
                    
                    # Сохраняем файл
                    avatar_file.save(avatar_path)
                    
                    # Сохраняем относительный путь для базы данных (от папки static)
                    avatar_relative_path = f"uploads/avatars/{current_user.id}/{filename}"
                    
                    print(f"DEBUG: Avatar saved to: {avatar_path}")
                    print(f"DEBUG: Avatar relative path: {avatar_relative_path}")
                    print(f"DEBUG: File exists after save: {os.path.exists(avatar_path)}")
                    
                except Exception as e:
                    current_app.logger.error(f'Ошибка при сохранении аватара: {e}')
                    errors.append('Ошибка при загрузке аватара. Попробуйте еще раз.')
    
    # Валидация URL'ов
    urls_to_validate = [
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
        return render_template('auth/edit_profile.html', form_data=form_data)
    
    try:
        # Обновляем данные пользователя
        current_user.nickname = nickname
        current_user.email = email
        current_user.strava_url = strava_url if strava_url else None
        current_user.komoot_url = komoot_url if komoot_url else None
        current_user.telegram_url = telegram_url if telegram_url else None
        current_user.instagram_url = instagram_url if instagram_url else None
        
        # Обновляем аватар если загружен новый файл
        if avatar_relative_path:
            print(f"DEBUG: Updating avatar_url in database to: {avatar_relative_path}")
            
            # Удаляем старый аватар если он существует и это загруженный файл
            if current_user.avatar_url and current_user.avatar_url.startswith('uploads/avatars/'):
                old_avatar_path = os.path.join(current_app.static_folder, current_user.avatar_url)
                if os.path.exists(old_avatar_path):
                    try:
                        os.remove(old_avatar_path)
                        print(f"DEBUG: Old avatar deleted: {old_avatar_path}")
                    except Exception as e:
                        print(f"DEBUG: Failed to delete old avatar: {e}")
            
            current_user.avatar_url = avatar_relative_path
            print(f"DEBUG: User avatar_url updated to: {current_user.avatar_url}")
        
        # Обновляем пароль если запрошено
        if password_change_requested and new_password:
            current_user.set_password(new_password)
        
        # Сохраняем в базу данных
        db.session.commit()
        
        flash('Профиль успешно обновлен!', 'success')
        return redirect(url_for('auth.profile'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Ошибка при обновлении профиля: {e}')
        flash('Произошла ошибка при сохранении данных. Попробуйте еще раз.', 'error')
        return render_template('auth/edit_profile.html', form_data=form_data)