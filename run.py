# run.py

import os
from app import create_app, db
from app.models import User, BikeLane, City, Notification
from flask_migrate import upgrade

app = create_app()

# Контекст для работы с базой данных
@app.shell_context_processor
def make_shell_context():
    return {
        'db': db, 
        'User': User, 
        'BikeLane': BikeLane, 
        'City': City, 
        'Notification': Notification
    }

@app.cli.command()
def deploy():
    """Команда для деплоя приложения"""
    # Создание таблиц базы данных
    upgrade()
    
    # Создание администратора если его нет
    admin = User.query.filter_by(email='admin@velojol.com').first()
    if not admin:
        admin = User(
            email='admin@velojol.com',
            nickname='admin',
            is_admin=True
        )
        admin.set_password('admin123')  # Поменяйте пароль в продакшене!
        db.session.add(admin)
        db.session.commit()
        print('Администратор создан: admin@velojol.com / admin123')

@app.cli.command()
def init_db():
    """Инициализация базы данных"""
    db.create_all()
    print('База данных инициализирована!')

@app.cli.command()
def create_admin():
    """Создание администратора"""
    email = input('Email администратора: ')
    nickname = input('Никнейм администратора: ')
    password = input('Пароль администратора: ')
    
    if User.query.filter_by(email=email).first():
        print('Пользователь с таким email уже существует!')
        return
    
    admin = User(
        email=email,
        nickname=nickname,
        is_admin=True
    )
    admin.set_password(password)
    
    db.session.add(admin)
    db.session.commit()
    
    print(f'Администратор {nickname} создан!')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5500)