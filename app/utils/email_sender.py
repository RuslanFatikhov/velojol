from flask import render_template
from flask_mail import Message
from app import mail
from threading import Thread
from flask import current_app
import json
import socket
import urllib.error
import urllib.request

def send_async_email(app, msg):
    """Асинхронная отправка email"""
    with app.app_context():
        try:
            mail.send(msg)
        except Exception:
            app.logger.exception('Ошибка отправки email')

def _send_smtp_email(subject, recipient, text_body, html_body=None):
    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or current_app.config.get('MAIL_USERNAME')
    if not sender:
        raise RuntimeError('MAIL_DEFAULT_SENDER or MAIL_USERNAME is not configured')

    msg = Message(
        subject=subject,
        sender=sender,
        recipients=[recipient],
        body=text_body,
        html=html_body
    )

    if current_app.config.get('EMAIL_SEND_ASYNC'):
        Thread(
            target=send_async_email,
            args=(current_app._get_current_object(), msg)
        ).start()
        return True

    timeout = int(current_app.config.get('MAIL_TIMEOUT') or 10)
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        mail.send(msg)
    finally:
        socket.setdefaulttimeout(previous_timeout)
    return True

def _send_resend_email(subject, recipient, text_body, html_body=None):
    api_key = current_app.config.get('RESEND_API_KEY')
    sender = current_app.config.get('RESEND_FROM') or current_app.config.get('MAIL_DEFAULT_SENDER')

    if not api_key:
        raise RuntimeError('RESEND_API_KEY is not configured')
    if not sender:
        raise RuntimeError('RESEND_FROM or MAIL_DEFAULT_SENDER is not configured')

    payload = {
        'from': sender,
        'to': [recipient],
        'subject': subject,
        'text': text_body,
    }
    if html_body:
        payload['html'] = html_body

    request = urllib.request.Request(
        'https://api.resend.com/emails',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    timeout = int(current_app.config.get('MAIL_TIMEOUT') or 10)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status >= 400:
            raise RuntimeError(f'Resend API returned HTTP {response.status}')

    return True

def send_email(subject, recipient, text_body, html_body=None):
    """Отправка email"""
    provider = current_app.config.get('EMAIL_PROVIDER', 'smtp')

    try:
        if provider == 'resend':
            return _send_resend_email(subject, recipient, text_body, html_body)
        if provider == 'smtp':
            return _send_smtp_email(subject, recipient, text_body, html_body)
        raise RuntimeError(f'Unsupported EMAIL_PROVIDER: {provider}')
    except (urllib.error.URLError, TimeoutError):
        current_app.logger.exception('Ошибка отправки email: сетевой таймаут или недоступный провайдер')
        return False
    except Exception:
        current_app.logger.exception('Ошибка отправки email')
        return False

def send_verification_code(email, code, code_type):
    """Отправка кода верификации"""
    
    if code_type == 'registration':
        subject = 'Velojol - Код подтверждения регистрации'
        text_body = f'''
Добро пожаловать в Velojol!

Ваш код подтверждения: {code}

Код действителен в течение 15 минут.

Если вы не регистрировались на нашем сайте, проигнорируйте это письмо.

---
Команда Velojol
        '''
        html_body = f'''
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">Добро пожаловать в Velojol!</h2>
                    <p>Ваш код подтверждения регистрации:</p>
                    <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-radius: 5px; margin: 20px 0;">
                        <h1 style="color: #3498db; font-size: 32px; letter-spacing: 5px; margin: 0;">{code}</h1>
                    </div>
                    <p style="color: #7f8c8d; font-size: 14px;">Код действителен в течение 15 минут.</p>
                    <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 20px 0;">
                    <p style="color: #95a5a6; font-size: var(--spacer-sm);">
                        Если вы не регистрировались на нашем сайте, проигнорируйте это письмо.
                    </p>
                    <p style="color: #95a5a6; font-size: var(--spacer-sm);">
                        С уважением,<br>
                        Команда Velojol
                    </p>
                </div>
            </body>
        </html>
        '''
    
    elif code_type == 'password_reset':
        subject = 'Velojol - Код восстановления пароля'
        text_body = f'''
Восстановление пароля

Ваш код для восстановления пароля: {code}

Код действителен в течение 15 минут.

Если вы не запрашивали восстановление пароля, проигнорируйте это письмо.

---
Команда Velojol
        '''
        html_body = f'''
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c3e50;">Восстановление пароля</h2>
                    <p>Вы запросили восстановление пароля для вашей учетной записи Velojol.</p>
                    <p>Ваш код для восстановления пароля:</p>
                    <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-radius: 5px; margin: 20px 0;">
                        <h1 style="color: #e74c3c; font-size: 32px; letter-spacing: 5px; margin: 0;">{code}</h1>
                    </div>
                    <p style="color: #7f8c8d; font-size: 14px;">Код действителен в течение 15 минут.</p>
                    <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 20px 0;">
                    <p style="color: #95a5a6; font-size: var(--spacer-sm);">
                        Если вы не запрашивали восстановление пароля, проигнорируйте это письмо и ваш пароль останется без изменений.
                    </p>
                    <p style="color: #95a5a6; font-size: var(--spacer-sm);">
                        С уважением,<br>
                        Команда Velojol
                    </p>
                </div>
            </body>
        </html>
        '''
    
    return send_email(subject, email, text_body, html_body)
