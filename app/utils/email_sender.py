from flask import render_template
from flask_mail import Message
from app import mail
from threading import Thread
from flask import current_app

def send_async_email(app, msg):
    """Асинхронная отправка email"""
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"Ошибка отправки email: {str(e)}")

def send_email(subject, recipient, text_body, html_body=None):
    """Отправка email"""
    msg = Message(
        subject=subject,
        recipients=[recipient],
        body=text_body,
        html=html_body
    )
    
    # Асинхронная отправка в отдельном потоке
    Thread(
        target=send_async_email,
        args=(current_app._get_current_object(), msg)
    ).start()

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
                    <p style="color: #95a5a6; font-size: 12px;">
                        Если вы не регистрировались на нашем сайте, проигнорируйте это письмо.
                    </p>
                    <p style="color: #95a5a6; font-size: 12px;">
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
                    <p style="color: #95a5a6; font-size: 12px;">
                        Если вы не запрашивали восстановление пароля, проигнорируйте это письмо и ваш пароль останется без изменений.
                    </p>
                    <p style="color: #95a5a6; font-size: 12px;">
                        С уважением,<br>
                        Команда Velojol
                    </p>
                </div>
            </body>
        </html>
        '''
    
    send_email(subject, email, text_body, html_body)
