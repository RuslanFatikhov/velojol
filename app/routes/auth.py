# app/routes/auth.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db, oauth
from app.models.user import User
from app.models.bikelane import BikeLane
from app.models.verification import VerificationCode
from app.utils.email_sender import send_verification_code
from app.utils.file_handler import FileHandler
from datetime import datetime, timezone
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from authlib.integrations.base_client.errors import OAuthError
from authlib.jose import JsonWebToken
from authlib.jose.errors import JoseError
from urllib.parse import urlsplit
import json
import secrets
import re
import os

# Создаем Blueprint для аутентификации
bp = Blueprint('auth', __name__, url_prefix='/auth')


def _safe_next_url(target):
    """Возвращает только локальный URL, чтобы не допустить open redirect."""
    if not target:
        return None

    reference = urlsplit(request.host_url)
    candidate = urlsplit(target)
    if candidate.scheme not in ('', reference.scheme):
        return None
    if candidate.netloc not in ('', reference.netloc):
        return None
    if not candidate.path.startswith('/'):
        return None
    return candidate.path + (f'?{candidate.query}' if candidate.query else '')


def _get_google_client():
    """Отдельная точка получения клиента упрощает безопасное тестирование OAuth."""
    return oauth.create_client('google')


def _get_telegram_client():
    """Возвращает OIDC-клиент Telegram."""
    return oauth.create_client('telegram')


def _google_redirect_uri():
    configured_uri = current_app.config.get('GOOGLE_REDIRECT_URI', '').strip()
    if configured_uri:
        return configured_uri
    return url_for(
        'auth.google_callback',
        _external=True,
        _scheme=current_app.config.get('PREFERRED_URL_SCHEME', 'http'),
    )


def _telegram_redirect_uri():
    configured_uri = current_app.config.get('TELEGRAM_REDIRECT_URI', '').strip()
    if configured_uri:
        return configured_uri
    return url_for(
        'auth.telegram_callback',
        _external=True,
        _scheme=current_app.config.get('PREFERRED_URL_SCHEME', 'http'),
    )


def _build_unique_nickname(source, fallback='rider'):
    """Создает допустимый свободный никнейм из внешнего профиля."""
    base = re.sub(r'[^a-zA-Z0-9_-]+', '_', str(source or '')).strip('_')
    if len(base) < 3:
        base = re.sub(
            r'[^a-zA-Z0-9_-]+',
            '_',
            str(fallback or ''),
        ).strip('_')
    if len(base) < 3:
        base = 'rider'
    base = base[:30]

    nickname = base
    suffix = 2
    while User.query.filter_by(nickname=nickname).first():
        suffix_text = f'_{suffix}'
        nickname = f'{base[:30 - len(suffix_text)]}{suffix_text}'
        suffix += 1
    return nickname


def _build_google_nickname(userinfo):
    """Создает допустимый и свободный никнейм из профиля Google."""
    source = userinfo.get('given_name') or userinfo.get('name') or userinfo['email'].split('@')[0]
    fallback = re.sub(
        r'[^a-zA-Z0-9_-]+',
        '_',
        userinfo['email'].split('@')[0],
    ).strip('_')
    return _build_unique_nickname(source, fallback=fallback or 'rider')


def _build_telegram_nickname(userinfo, telegram_sub):
    """Создает никнейм из username/имени Telegram без доверия к их уникальности."""
    source = (
        userinfo.get('preferred_username')
        or userinfo.get('given_name')
        or userinfo.get('name')
    )
    return _build_unique_nickname(source, fallback=f'rider_{telegram_sub[-8:]}')


def _load_telegram_jwks():
    configured_jwks = current_app.config.get('TELEGRAM_JWKS')
    if configured_jwks:
        return configured_jwks

    with current_app.open_resource('data/telegram_jwks.json') as jwks_file:
        return json.load(jwks_file)


def _telegram_id_token_userinfo(id_token):
    """Проверяет Telegram ID token по закреплённым публичным ключам."""
    expected_nonce = session.pop('telegram_login_nonce', None)
    client_id = str(current_app.config.get('TELEGRAM_CLIENT_ID', '')).strip()
    if not id_token or not expected_nonce or not client_id:
        return None

    try:
        claims = JsonWebToken(['RS256']).decode(
            id_token,
            _load_telegram_jwks(),
        )
        claims.validate(leeway=60)
    except (JoseError, ValueError, TypeError, KeyError):
        return None

    audience = claims.get('aud')
    valid_audience = (
        client_id in audience
        if isinstance(audience, list)
        else str(audience or '') == client_id
    )
    if (
        claims.get('iss') != 'https://oauth.telegram.org'
        or not valid_audience
        or not secrets.compare_digest(
            str(claims.get('nonce', '')),
            expected_nonce,
        )
        or not str(claims.get('sub', '')).strip()
    ):
        return None

    return dict(claims)


def _finish_telegram_login(userinfo):
    """Создаёт/находит Telegram-пользователя и завершает вход."""
    telegram_sub = str(userinfo.get('sub', '')).strip()
    if not telegram_sub:
        flash('Telegram не передал идентификатор аккаунта', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(telegram_sub=telegram_sub).first()
    if user is None:
        username = str(userinfo.get('preferred_username', '')).strip()
        user = User(
            email=None,
            nickname=_build_telegram_nickname(userinfo, telegram_sub),
            telegram_sub=telegram_sub,
            telegram_url=f'https://t.me/{username}' if re.fullmatch(
                r'[a-zA-Z0-9_]{5,32}',
                username,
            ) else None,
        )
        # password_hash остается обязательным для старых локальных аккаунтов.
        # Случайное значение никогда не используется для Telegram-входа.
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)

    picture = str(userinfo.get('picture', '')).strip()
    if picture and not user.avatar_url:
        user.avatar_url = picture

    if user.is_banned:
        db.session.rollback()
        flash(f'Ваш аккаунт заблокирован. Причина: {user.ban_reason}', 'error')
        return redirect(url_for('auth.login'))

    db.session.commit()
    session.permanent = True
    login_user(user, remember=True)

    next_page = session.pop('telegram_oauth_next', None)
    return redirect(next_page or url_for('main.index'))


def _get_json_payload():
    """Безопасно возвращает JSON body для XHR-запросов."""
    return request.get_json(silent=True) or {}


def _get_verification_email(session_key):
    """Берет email из JSON-запроса, либо из сессии как fallback."""
    payload = _get_json_payload()
    email = payload.get('email', '')

    if isinstance(email, str):
        email = email.strip().lower()
    else:
        email = ''

    if not email:
        email = session.get(session_key, '')

    return email


def _build_password_reset_token(email):
    """Создает подписанный токен для перехода к смене пароля."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps({'email': email}, salt='password-reset')


def _load_password_reset_token(token, max_age=1800):
    """Проверяет токен восстановления и возвращает email."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

    try:
        payload = serializer.loads(token, salt='password-reset', max_age=max_age)
    except SignatureExpired:
        return None, 'Ссылка для восстановления истекла. Запросите новый код.'
    except BadSignature:
        return None, 'Неверная ссылка для восстановления пароля'

    email = payload.get('email')
    if not isinstance(email, str) or not email.strip():
        return None, 'Неверная ссылка для восстановления пароля'

    return email.strip().lower(), None

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
                if not send_verification_code(email, existing_code.code, 'registration'):
                    flash('Не удалось отправить код на почту. Попробуйте позже или свяжитесь с администратором.', 'error')
                    return render_template('auth/register.html', form_data=request.form)
                
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
        if not send_verification_code(email, verification.code, 'registration'):
            flash('Не удалось отправить код на почту. Попробуйте позже или свяжитесь с администратором.', 'error')
            return render_template('auth/register.html', form_data=request.form)
        
        # Сохраняем email в сессии
        session['pending_registration_email'] = email
        
        flash('Код подтверждения отправлен на вашу почту', 'success')
        return render_template('auth/verify_email.html', email=email, code_type='registration')
    
    return render_template('auth/register.html')

@bp.route('/verify-registration', methods=['POST'])
def verify_registration():
    """Проверка кода регистрации и создание пользователя"""

    payload = _get_json_payload()
    email = _get_verification_email('pending_registration_email')
    if not email:
        return jsonify({'success': False, 'message': 'Сессия истекла'}), 400

    code = str(payload.get('code', '')).strip()
    
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
    session['pending_registration_email'] = email
    
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

    payload = _get_json_payload()
    email = payload.get('email')
    code_type = payload.get('code_type')  # 'registration' или 'password_reset'

    if not email or not code_type:
        return jsonify({'success': False, 'message': 'Недостаточно данных'}), 400

    email = email.strip().lower()
    
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
    if not send_verification_code(email, verification.code, code_type):
        return jsonify({'success': False, 'message': 'Не удалось отправить код на почту. Попробуйте позже.'}), 503

    if code_type == 'registration':
        session['pending_registration_email'] = email
    elif code_type == 'password_reset':
        session['password_reset_email'] = email

    return jsonify({'success': True, 'message': 'Код отправлен повторно'})

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа через внешних провайдеров.

    POST оставлен как временный аварийный путь для существующих аккаунтов,
    но форма email/пароля больше не публикуется в интерфейсе.
    """
    
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    telegram_login_nonce = secrets.token_urlsafe(32)
    session['telegram_login_nonce'] = telegram_login_nonce
    session['telegram_oauth_next'] = _safe_next_url(request.args.get('next'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember_me', 'on') == 'on'
        
        if not email or not password:
            flash('Заполните все поля', 'error')
            return render_template(
                'auth/login.html',
                form_data=request.form,
                telegram_login_nonce=telegram_login_nonce,
            )
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            flash('Неверный email или пароль', 'error')
            return render_template(
                'auth/login.html',
                form_data=request.form,
                telegram_login_nonce=telegram_login_nonce,
            )
        
        if user.is_banned:
            flash(f'Ваш аккаунт заблокирован. Причина: {user.ban_reason}', 'error')
            return render_template(
                'auth/login.html',
                form_data=request.form,
                telegram_login_nonce=telegram_login_nonce,
            )

        session.permanent = True
        login_user(user, remember=remember)
        
        next_page = _safe_next_url(request.args.get('next'))
        if next_page:
            return redirect(next_page)
        
        return redirect(url_for('main.index'))
    
    return render_template(
        'auth/login.html',
        telegram_login_nonce=telegram_login_nonce,
    )


@bp.route('/telegram')
def telegram_login():
    """Fallback для браузеров, где Telegram Login Widget не загрузился."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if not current_app.config.get('TELEGRAM_OAUTH_ENABLED'):
        flash('Вход через Telegram пока не настроен', 'error')
        return redirect(url_for('auth.login'))

    session['telegram_oauth_next'] = _safe_next_url(request.args.get('next'))
    flash('Нажмите «Войти через Telegram» ещё раз', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/telegram/callback', methods=['GET', 'POST'])
def telegram_callback():
    """Проверяет ответ Telegram и выполняет вход."""
    if not current_app.config.get('TELEGRAM_OAUTH_ENABLED'):
        flash('Вход через Telegram пока не настроен', 'error')
        return redirect(url_for('auth.login'))

    if request.values.get('id_token'):
        userinfo = _telegram_id_token_userinfo(request.values.get('id_token'))
        if userinfo is None:
            current_app.logger.warning('Telegram Login ID token rejected')
            flash('Не удалось проверить вход через Telegram. Попробуйте ещё раз.', 'error')
            return redirect(url_for('auth.login'))
    else:
        # Оставляем совместимость с уже начатыми OIDC-сессиями.
        try:
            token = _get_telegram_client().authorize_access_token()
            userinfo = token.get('userinfo') or {}
        except OAuthError as exc:
            current_app.logger.warning('Telegram OAuth failed: %s', exc.error)
            flash('Не удалось войти через Telegram. Попробуйте ещё раз.', 'error')
            return redirect(url_for('auth.login'))
        except Exception:
            current_app.logger.exception('Unexpected Telegram OAuth error')
            flash('Не удалось войти через Telegram. Попробуйте ещё раз.', 'error')
            return redirect(url_for('auth.login'))

    return _finish_telegram_login(userinfo)


@bp.route('/google')
def google_login():
    """Начинает серверный OpenID Connect flow через Google."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if not current_app.config.get('GOOGLE_OAUTH_ENABLED'):
        flash('Вход через Google пока не настроен', 'error')
        return redirect(url_for('auth.login'))

    session['google_oauth_next'] = _safe_next_url(request.args.get('next'))
    return _get_google_client().authorize_redirect(_google_redirect_uri())


@bp.route('/google/callback')
def google_callback():
    """Проверяет ответ Google, связывает аккаунт и выполняет вход."""
    if not current_app.config.get('GOOGLE_OAUTH_ENABLED'):
        flash('Вход через Google пока не настроен', 'error')
        return redirect(url_for('auth.login'))

    try:
        token = _get_google_client().authorize_access_token()
        userinfo = token.get('userinfo') or {}
    except OAuthError as exc:
        current_app.logger.warning('Google OAuth failed: %s', exc.error)
        flash('Не удалось войти через Google. Попробуйте ещё раз.', 'error')
        return redirect(url_for('auth.login'))
    except Exception:
        current_app.logger.exception('Unexpected Google OAuth error')
        flash('Не удалось войти через Google. Попробуйте ещё раз.', 'error')
        return redirect(url_for('auth.login'))

    google_sub = str(userinfo.get('sub', '')).strip()
    email = str(userinfo.get('email', '')).strip().lower()
    email_verified = userinfo.get('email_verified') is True or str(
        userinfo.get('email_verified', '')
    ).lower() == 'true'

    if not google_sub or not email or not email_verified:
        flash('Google не подтвердил email этого аккаунта', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(google_sub=google_sub).first()
    if user is None:
        user = User.query.filter_by(email=email).first()
        if user and user.google_sub and user.google_sub != google_sub:
            flash('Этот email уже связан с другим Google-аккаунтом', 'error')
            return redirect(url_for('auth.login'))

        if user:
            user.google_sub = google_sub
        else:
            user = User(
                email=email,
                nickname=_build_google_nickname(userinfo),
                google_sub=google_sub,
            )
            # Поле пока обязательно для локальных аккаунтов; случайный пароль
            # не используется для Google-входа и не хранится в открытом виде.
            user.set_password(secrets.token_urlsafe(32))
            db.session.add(user)

    picture = str(userinfo.get('picture', '')).strip()
    if picture and not user.avatar_url:
        user.avatar_url = picture

    if user.is_banned:
        db.session.rollback()
        flash(f'Ваш аккаунт заблокирован. Причина: {user.ban_reason}', 'error')
        return redirect(url_for('auth.login'))

    db.session.commit()
    session.permanent = True
    login_user(user, remember=True)

    next_page = session.pop('google_oauth_next', None)
    return redirect(next_page or url_for('main.index'))

@bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Запрос на восстановление пароля"""

    payload = _get_json_payload()
    email = str(payload.get('email', '')).strip().lower()
    
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
            if not send_verification_code(email, existing_code.code, 'password_reset'):
                return jsonify({'success': False, 'message': 'Не удалось отправить код на почту. Попробуйте позже.'}), 503
            session['password_reset_email'] = email
            return jsonify({'success': True, 'message': 'Код отправлен на вашу почту'})
    
    # Создаем новый код
    verification = VerificationCode.create_code(email, 'password_reset')
    
    # Отправляем код на email
    if not send_verification_code(email, verification.code, 'password_reset'):
        return jsonify({'success': False, 'message': 'Не удалось отправить код на почту. Попробуйте позже.'}), 503
    
    # Сохраняем email в сессии
    session['password_reset_email'] = email
    
    return jsonify({'success': True, 'message': 'Код отправлен на вашу почту'})

@bp.route('/verify-reset-code', methods=['POST'])
def verify_reset_code():
    """Проверка кода восстановления пароля"""

    payload = _get_json_payload()
    email = _get_verification_email('password_reset_email')
    if not email:
        return jsonify({'success': False, 'message': 'Сессия истекла'}), 400

    code = str(payload.get('code', '')).strip()
    
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

    reset_token = _build_password_reset_token(email)

    # Сохраняем в сессии что код проверен
    session['password_reset_email'] = email
    session['password_reset_verified'] = True
    
    return jsonify({
        'success': True,
        'message': 'Код подтвержден',
        'redirect': url_for('auth.reset_password', token=reset_token)
    })

@bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Страница смены пароля"""

    token = request.args.get('token', '').strip()
    if request.method == 'POST':
        token = request.form.get('token', '').strip()

    email = None
    token_error = None

    if token:
        email, token_error = _load_password_reset_token(token)

    if not email:
        email = session.get('password_reset_email')
        verified = session.get('password_reset_verified')
        if not email or not verified:
            flash(token_error or 'Неверная ссылка для восстановления пароля', 'error')
            return redirect(url_for('auth.login'))

    if token_error:
        flash(token_error, 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST' and not token:
        flash('Неверная ссылка для восстановления пароля', 'error')
        return redirect(url_for('auth.login'))

    if not email:
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
    
    return render_template('auth/reset_password.html', token=token)

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

    form_data = {
        'nickname': current_user.nickname or '',
        'email': current_user.email or '',
        'strava_url': current_user.strava_url or '',
        'komoot_url': current_user.komoot_url or '',
        'telegram_url': current_user.telegram_url or '',
        'instagram_url': current_user.instagram_url or '',
    }
    
    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        email = request.form.get('email', '').strip()
        
        # Социальные сети
        strava_url = request.form.get('strava_url', '').strip()
        komoot_url = request.form.get('komoot_url', '').strip()
        telegram_url = request.form.get('telegram_url', '').strip()
        instagram_url = request.form.get('instagram_url', '').strip()

        form_data.update({
            'nickname': nickname,
            'email': email,
            'strava_url': strava_url,
            'komoot_url': komoot_url,
            'telegram_url': telegram_url,
            'instagram_url': instagram_url,
        })
        
        errors = []
        
        # Валидация никнейма
        if nickname != current_user.nickname:
            if not validate_nickname(nickname):
                errors.append('Некорректный никнейм')
            elif User.query.filter_by(nickname=nickname).first():
                errors.append('Никнейм уже занят')

        normalized_email = email.lower() if email else None
        if normalized_email and not validate_email(normalized_email):
            errors.append('Некорректный email')
        elif normalized_email and normalized_email != current_user.email:
            existing_email_user = User.query.filter_by(email=normalized_email).first()
            if existing_email_user and existing_email_user.id != current_user.id:
                errors.append('Пользователь с таким email уже существует')
        
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
            return render_template('auth/edit_profile.html', form_data=form_data)
        
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
                    filename = f"avatar_{timestamp}.jpg"
                    avatar_path = os.path.join(user_avatar_dir, filename)
                    
                    avatar_file.save(avatar_path)
                    if not FileHandler.compress_image_to_jpeg(
                        avatar_path,
                        max_size_kb=50,
                        max_width=512,
                        max_height=512
                    ):
                        os.remove(avatar_path)
                        flash('Не удалось обработать аватар', 'error')
                    else:
                        current_user.avatar_url = f"uploads/avatars/{current_user.id}/{filename}"
        # Обновляем данные
        current_user.nickname = nickname
        current_user.email = normalized_email
        current_user.strava_url = strava_url if strava_url else None
        current_user.komoot_url = komoot_url if komoot_url else None
        current_user.telegram_url = telegram_url if telegram_url else None
        current_user.instagram_url = instagram_url if instagram_url else None
        
        db.session.commit()
        
        flash('Профиль обновлен', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/edit_profile.html', form_data=form_data)
