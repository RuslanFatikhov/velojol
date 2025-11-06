# app/routes/auth.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User
from app.models.bikelane import BikeLane
from app.models.verification import VerificationCode
from app.utils.email_sender import send_verification_code
from datetime import datetime, timezone
import re
import os

# Создаем Blueprint для аутентификации
bp = Blueprint('auth', __name__, url_prefix='/auth')

def validate_email(email):
    """Валидация email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_nickname(nickname):
    """Валидация никнейма"""
    pattern = r'^[a-zA-Z0-9_-]{3,30}$'
    return re.match(pattern, nickname) is not None

def validate_url(url):
    """Валидация URL"""
    if not url:
        return True
    pattern = r'^https?://.+\..+'
    return re.match(pattern, url) is not None

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Страница регистрации с отправкой кода на email"""
    
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        # Получаем данные из формы
        email = request.form.get('email', '').strip().lower()
        nickname = request.form.get('nickname', '').strip()
        password = request.form.get('password', '')
        
        # Социальные сети (опционально)
        strava_url = request.form.get('strava_url', '').strip()
        komoot_url = request.form.get('komoot_url', '').strip()
        telegram_url = request.form.get('telegram_url', '').strip()
        instagram_url = request.form.get('instagram_url', '').strip()
        
        # Валидация обязательных полей
        errors = []
        
        if not email:
            errors.append('Email обязателен')
        elif not validate_email(email):
            errors.append('Некорректный формат email')
        
        if not nickname:
            errors.append('Никнейм обязателен')
        elif not validate_nickname(nickname):
            errors.append('Никнейм должен содержать только буквы, цифры, дефисы и подчеркивания (3-30 символов)')
        
        if not password:
            errors.append('Пароль обязателен')
        elif len(password) < 6:
            errors.append('Пароль должен быть не менее 6 символов')
        
        # Проверка существующих пользователей
        if User.query.filter_by(email=email).first():
            errors.append('Пользователь с таким email уже существует')
        
        if User.query.filter_by(nickname=nickname).first():
            errors.append('Никнейм уже занят')
        
        # Валидация URL
        if strava_url and not validate_url(strava_url):
            errors.append('Некорректная ссылка Strava')
        if komoot_url and not validate_url(komoot_url):
            errors.append('Некорректная ссылка Komoot')
        if telegram_url and not validate_url(telegram_url):
            errors.append('Некорректная ссылка Telegram')
        if instagram_url and not validate_url(instagram_url):
            errors.append('Некорректная ссылка Instagram')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/register.html', form_data=request.form)
        
        # Проверяем существующий активный код
        existing_code = VerificationCode.get_active_code(email, 'registration')
        
        if existing_code:
            # Проверяем блокировку запросов
            if existing_code.is_request_locked():
                flash('Вы превысили лимит запросов кодов. Попробуйте через 1 час.', 'error')
                return render_template('auth/register.html', form_data=request.form)
            
            # Если код не истек, используем существующий
            if not existing_code.is_expired():
                # Обновляем данные регистрации
                existing_code.registration_data = {
                    'email': email,
                    'nickname': nickname,
                    'password': password,
                    'strava_url': strava_url,
                    'komoot_url': komoot_url,
                    'telegram_url': telegram_url,
                    'instagram_url': instagram_url
                }
                existing_code.increment_request_count()
                
                # Отправляем код повторно
                send_verification_code(email, existing_code.code, 'registration')
                
                # Сохраняем email в сессии
                session['pending_registration_email'] = email
                
                flash('Код подтверждения отправлен повторно на вашу почту', 'success')
                return render_template('auth/verify_email.html', email=email, code_type='registration')
        
        # Создаем новый код
        registration_data = {
            'email': email,
            'nickname': nickname,
            'password': password,
            'strava_url': strava_url,
            'komoot_url': komoot_url,
            'telegram_url': telegram_url,
            'instagram_url': instagram_url
        }
        
        verification = VerificationCode.create_code(email, 'registration', registration_data)
        
        # Отправляем код на email
        send_verification_code(email, verification.code, 'registration')
        
        # Сохраняем email в сессии
        session['pending_registration_email'] = email
        
        flash('Код подтверждения отправлен на вашу почту', 'success')
        return render_template('auth/verify_email.html', email=email, code_type='registration')
    
    return render_template('auth/register.html')

@bp.route('/verify-registration', methods=['POST'])
def verify_registration():
    """Проверка кода регистрации и создание пользователя"""
    
    email = session.get('pending_registration_email')
    if not email:
        return jsonify({'success': False, 'message': 'Сессия истекла'}), 400
    
    code = request.json.get('code', '').strip()
    
    if not code:
        return jsonify({'success': False, 'message': 'Введите код'}), 400
    
    # Получаем активный код
    verification = VerificationCode.get_active_code(email, 'registration')
    
    if not verification:
        return jsonify({'success': False, 'message': 'Код не найден'}), 404
    
    # Проверяем блокировку попыток
    if verification.is_attempt_locked():
        return jsonify({'success': False, 'message': 'Превышен лимит попыток. Попробуйте через 24 часа.'}), 429
    
    # Проверяем срок действия
    if verification.is_expired():
        return jsonify({'success': False, 'message': 'Код истек. Запросите новый код.'}), 400
    
    # Проверяем код
    if verification.code != code:
        verification.increment_attempts()
        remaining = 5 - verification.attempts
        if remaining > 0:
            return jsonify({'success': False, 'message': f'Неверный код. Осталось попыток: {remaining}'}), 400
        else:
            return jsonify({'success': False, 'message': 'Превышен лимит попыток. Попробуйте через 24 часа.'}), 429
    
    # Код верный - создаем пользователя
    data = verification.registration_data
    
    user = User(
        email=data['email'],
        nickname=data['nickname'],
        strava_url=data.get('strava_url'),
        komoot_url=data.get('komoot_url'),
        telegram_url=data.get('telegram_url'),
        instagram_url=data.get('instagram_url')
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    verification.verify()
    db.session.commit()
    
    # Автоматический вход
    login_user(user, remember=True)
    
    # Очищаем сессию
    session.pop('pending_registration_email', None)
    
    return jsonify({'success': True, 'message': 'Регистрация успешна!', 'redirect': url_for('main.index')})

@bp.route('/resend-code', methods=['POST'])
def resend_code():
    """Повторная отправка кода"""
    
    email = request.json.get('email')
    code_type = request.json.get('code_type')  # 'registration' или 'password_reset'
    
    if not email or not code_type:
        return jsonify({'success': False, 'message': 'Недостаточно данных'}), 400
    
    # Получаем активный код
    verification = VerificationCode.get_active_code(email, code_type)
    
    if not verification:
        return jsonify({'success': False, 'message': 'Код не найден'}), 404
    
    # Проверяем блокировку запросов
    if verification.is_request_locked():
        return jsonify({'success': False, 'message': 'Превышен лимит запросов. Попробуйте через 1 час.'}), 429
    
    # Увеличиваем счетчик запросов
    verification.increment_request_count()
    
    # Если превысили лимит после инкремента
    if verification.is_request_locked():
        return jsonify({'success': False, 'message': 'Превышен лимит запросов. Попробуйте через 1 час.'}), 429
    
    # Отправляем код
    send_verification_code(email, verification.code, code_type)
    
    return jsonify({'success': True, 'message': 'Код отправлен повторно'})

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember_me') == 'on'
        
        if not email or not password:
            flash('Заполните все поля', 'error')
            return render_template('auth/login.html', form_data=request.form)
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            flash('Неверный email или пароль', 'error')
            return render_template('auth/login.html', form_data=request.form)
        
        if user.is_banned:
            flash(f'Ваш аккаунт заблокирован. Причина: {user.ban_reason}', 'error')
            return render_template('auth/login.html', form_data=request.form)
        
        login_user(user, remember=remember)
        
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        
        return redirect(url_for('main.index'))
    
    return render_template('auth/login.html')

@bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Запрос на восстановление пароля"""
    
    email = request.json.get('email', '').strip().lower()
    
    if not email or not validate_email(email):
        return jsonify({'success': False, 'message': 'Введите корректный email'}), 400
    
    # Проверяем существование пользователя
    user = User.query.filter_by(email=email).first()
    
    if not user:
        # В целях безопасности не сообщаем что пользователь не найден
        return jsonify({'success': True, 'message': 'Если этот email зарегистрирован, код будет отправлен'})
    
    # Проверяем существующий активный код
    existing_code = VerificationCode.get_active_code(email, 'password_reset')
    
    if existing_code:
        # Проверяем блокировку запросов
        if existing_code.is_request_locked():
            return jsonify({'success': False, 'message': 'Превышен лимит запросов. Попробуйте через 1 час.'}), 429
        
        # Если код не истек, используем существующий
        if not existing_code.is_expired():
            existing_code.increment_request_count()
            send_verification_code(email, existing_code.code, 'password_reset')
            session['password_reset_email'] = email
            return jsonify({'success': True, 'message': 'Код отправлен на вашу почту'})
    
    # Создаем новый код
    verification = VerificationCode.create_code(email, 'password_reset')
    
    # Отправляем код на email
    send_verification_code(email, verification.code, 'password_reset')
    
    # Сохраняем email в сессии
    session['password_reset_email'] = email
    
    return jsonify({'success': True, 'message': 'Код отправлен на вашу почту'})

@bp.route('/verify-reset-code', methods=['POST'])
def verify_reset_code():
    """Проверка кода восстановления пароля"""
    
    email = session.get('password_reset_email')
    if not email:
        return jsonify({'success': False, 'message': 'Сессия истекла'}), 400
    
    code = request.json.get('code', '').strip()
    
    if not code:
        return jsonify({'success': False, 'message': 'Введите код'}), 400
    
    # Получаем активный код
    verification = VerificationCode.get_active_code(email, 'password_reset')
    
    if not verification:
        return jsonify({'success': False, 'message': 'Код не найден'}), 404
    
    # Проверяем блокировку попыток
    if verification.is_attempt_locked():
        return jsonify({'success': False, 'message': 'Превышен лимит попыток. Попробуйте через 24 часа.'}), 429
    
    # Проверяем срок действия
    if verification.is_expired():
        return jsonify({'success': False, 'message': 'Код истек. Запросите новый код.'}), 400
    
    # Проверяем код
    if verification.code != code:
        verification.increment_attempts()
        remaining = 5 - verification.attempts
        if remaining > 0:
            return jsonify({'success': False, 'message': f'Неверный код. Осталось попыток: {remaining}'}), 400
        else:
            return jsonify({'success': False, 'message': 'Превышен лимит попыток. Попробуйте через 24 часа.'}), 429
    
    # Код верный - помечаем как проверенный
    verification.verify()
    db.session.commit()
    
    # Сохраняем в сессии что код проверен
    session['password_reset_verified'] = True
    
    return jsonify({'success': True, 'message': 'Код подтвержден', 'redirect': url_for('auth.reset_password')})

@bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Страница смены пароля"""
    
    email = session.get('password_reset_email')
    verified = session.get('password_reset_verified')
    
    if not email or not verified:
        flash('Неверная ссылка для восстановления пароля', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        new_password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not new_password or len(new_password) < 6:
            flash('Пароль должен быть не менее 6 символов', 'error')
            return render_template('auth/reset_password.html')
        
        if new_password != confirm_password:
            flash('Пароли не совпадают', 'error')
            return render_template('auth/reset_password.html')
        
        # Находим пользователя и меняем пароль
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Пользователь не найден', 'error')
            return redirect(url_for('auth.login'))
        
        user.set_password(new_password)
        db.session.commit()
        
        # Очищаем сессию
        session.pop('password_reset_email', None)
        session.pop('password_reset_verified', None)
        
        flash('Пароль успешно изменен! Войдите с новым паролем.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html')

@bp.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('auth.login'))

@bp.route('/profile')
@login_required
def profile():
    """Профиль пользователя - редирект на красивый URL"""
    return redirect(url_for('main.user_profile', nickname=current_user.nickname))



@bp.route('/bikelane/<int:bikelane_id>')
@login_required
def view_bikelane(bikelane_id):
    """Просмотр велодорожки пользователя"""
    from app.models.bikelane import BikeLane
    
    bikelane = BikeLane.query.get_or_404(bikelane_id)
    
    # Проверяем что это велодорожка текущего пользователя
    if bikelane.user_id != current_user.id:
        flash('У вас нет доступа к этой велодорожке', 'error')
        return redirect(url_for('auth.my_bikelanes'))
    
    return render_template('auth/view_bikelane.html', bikelane=bikelane)

@bp.route('/bikelane/<int:bikelane_id>/delete', methods=['POST'])
@login_required
def delete_bikelane(bikelane_id):
    """Удаление велодорожки пользователя"""
    from app.models.bikelane import BikeLane
    
    bikelane = BikeLane.query.get_or_404(bikelane_id)
    
    # Проверяем что это велодорожка текущего пользователя
    if bikelane.user_id != current_user.id:
        flash('У вас нет доступа к этой велодорожке', 'error')
        return redirect(url_for('auth.my_bikelanes'))
    
    # Проверяем что велодорожка не одобрена (одобренные удалить нельзя)
    if bikelane.status == 'approved':
        flash('Нельзя удалить одобренную велодорожку', 'error')
        return redirect(url_for('auth.view_bikelane', bikelane_id=bikelane_id))
    
    title = bikelane.title
    
    try:
        db.session.delete(bikelane)
        db.session.commit()
        flash(f'Велодорожка "{title}" успешно удалена', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Ошибка при удалении велодорожки: {e}')
        flash('Ошибка при удалении велодорожки', 'error')
    
    return redirect(url_for('auth.my_bikelanes'))


@bp.route('/my-bikelanes')
@login_required
def my_bikelanes():
    """Страница со списком велодорожек пользователя"""
    from app.models.bikelane import BikeLane
    
    # Получаем фильтр статуса из параметров
    status_filter = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Получаем статистику пользователя
    user_stats = {
        'total': current_user.get_bikelanes_count(),
        'pending': current_user.get_pending_bikelanes_count(),
        'approved': current_user.get_approved_bikelanes_count(),
        'rejected': current_user.bikelanes.filter_by(status='rejected').count()
    }
    
    # Фильтруем велодорожки по статусу
    query = current_user.bikelanes.order_by(BikeLane.created_at.desc())
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    # Пагинация
    bikelanes = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('auth/my_bikelanes.html',
                         user_stats=user_stats,
                         bikelanes=bikelanes,
                         status_filter=status_filter)
@bp.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Редактирование профиля"""
    from app.utils.file_handler import FileHandler
    
    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        
        # Социальные сети
        strava_url = request.form.get('strava_url', '').strip()
        komoot_url = request.form.get('komoot_url', '').strip()
        telegram_url = request.form.get('telegram_url', '').strip()
        instagram_url = request.form.get('instagram_url', '').strip()
        
        errors = []
        
        # Валидация никнейма
        if nickname != current_user.nickname:
            if not validate_nickname(nickname):
                errors.append('Некорректный никнейм')
            elif User.query.filter_by(nickname=nickname).first():
                errors.append('Никнейм уже занят')
        
        # Валидация URL
        if strava_url and not validate_url(strava_url):
            errors.append('Некорректная ссылка Strava')
        if komoot_url and not validate_url(komoot_url):
            errors.append('Некорректная ссылка Komoot')
        if telegram_url and not validate_url(telegram_url):
            errors.append('Некорректная ссылка Telegram')
        if instagram_url and not validate_url(instagram_url):
            errors.append('Некорректная ссылка Instagram')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/edit_profile.html')
        
        # Обработка аватара
        if 'avatar' in request.files:
            avatar_file = request.files['avatar']
            if avatar_file and avatar_file.filename:
                # Удаляем старый аватар если есть
                if current_user.avatar_url and current_user.avatar_url.startswith('uploads/'):
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_user.avatar_url.replace('uploads/', ''))
                    FileHandler.delete_file(old_path)
                
                # Сохраняем новый
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                file_ext = avatar_file.filename.rsplit('.', 1)[1].lower() if '.' in avatar_file.filename else ''
                
                if file_ext in allowed_extensions:
                    user_avatar_dir = os.path.join(current_app.static_folder, 'uploads', 'avatars', str(current_user.id))
                    os.makedirs(user_avatar_dir, exist_ok=True)
                    
                    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                    filename = f"avatar_{timestamp}.{file_ext}"
                    avatar_path = os.path.join(user_avatar_dir, filename)
                    
                    avatar_file.save(avatar_path)
                    current_user.avatar_url = f"uploads/avatars/{current_user.id}/{filename}"
        # Обновляем данные
        current_user.nickname = nickname
        current_user.strava_url = strava_url if strava_url else None
        current_user.komoot_url = komoot_url if komoot_url else None
        current_user.telegram_url = telegram_url if telegram_url else None
        current_user.instagram_url = instagram_url if instagram_url else None
        
        db.session.commit()
        
        flash('Профиль обновлен', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/edit_profile.html')
