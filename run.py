import json
import os
import random

import click
from app import create_app, db
from app.models import User, BikeLane, City, Notification, InfrastructurePoint
from flask_migrate import upgrade

app = create_app()


def _seed_cities_from_json():
    """Заполняет таблицу cities из static/data/cities.json, если городов еще нет."""
    if City.query.first():
        print('Города уже есть в базе, импорт пропущен.')
        return

    cities_path = os.path.join(app.static_folder, 'data', 'cities.json')
    with open(cities_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    cities = payload.get('cities', [])
    for item in cities:
        city = City.from_json_data(item)
        city.coat_of_arms = item.get('coat_of_arms')
        city.background_image = item.get('background_image')
        city.status = 'active'
        db.session.add(city)

    db.session.commit()
    print(f'Загружено городов: {len(cities)}')


def _ensure_local_admin(email='admin@velojol.com', nickname='admin', password='admin123'):
    """Создает локального администратора, если его еще нет."""
    admin = User.query.filter_by(email=email).first()
    if admin:
        if not admin.is_admin:
            admin.is_admin = True
            db.session.commit()
            print(f'Пользователь {email} повышен до администратора.')
        else:
            print(f'Администратор уже существует: {email}')
        return admin

    admin = User(
        email=email,
        nickname=nickname,
        is_admin=True
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f'Администратор создан: {email} / {password}')
    return admin


def _seed_tournament_users(count=20, password='test12345', min_score=5, max_score=250):
    """Создает или обновляет тестовых пользователей для турнирной таблицы."""
    created = 0
    updated = 0

    for index in range(1, count + 1):
        email = f'testuser{index:02d}@velojol.local'
        nickname = f'testuser{index:02d}'
        manual_score = random.randint(min_score, max_score)

        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(
                email=email,
                nickname=nickname,
                manual_score=manual_score
            )
            user.set_password(password)
            db.session.add(user)
            created += 1
        else:
            user.nickname = nickname
            user.manual_score = manual_score
            if user.is_admin:
                user.is_admin = False
            updated += 1

    db.session.commit()
    print(
        f'Тестовые пользователи турнира готовы: создано {created}, '
        f'обновлено {updated}. Пароль для всех: {password}'
    )

# Контекст для работы с базой данных
@app.shell_context_processor
def make_shell_context():
    return {
        'db': db, 
        'User': User, 
        'BikeLane': BikeLane, 
        'City': City, 
        'Notification': Notification,
        'InfrastructurePoint': InfrastructurePoint,
    }

@app.cli.command()
def deploy():
    """Команда для деплоя приложения"""
    # Создание таблиц базы данных
    upgrade()
    
    # Создание администратора если его нет
    _ensure_local_admin()

@app.cli.command()
def init_db():
    """Инициализация базы данных"""
    db.create_all()
    print('База данных инициализирована!')


@app.cli.command()
def seed_cities():
    """Загрузка стартовых городов из JSON в базу данных"""
    _seed_cities_from_json()


@app.cli.command()
def setup_local():
    """Подготовка локальной базы данных для разработки"""
    db.create_all()
    print('База данных инициализирована!')
    _seed_cities_from_json()

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


@app.cli.command('setup-test-data')
@click.option('--count', default=20, show_default=True, type=int, help='Количество тестовых пользователей.')
@click.option('--password', default='test12345', show_default=True, help='Общий пароль для тестовых пользователей.')
@click.option('--min-score', default=5, show_default=True, type=int, help='Минимальное количество очков.')
@click.option('--max-score', default=250, show_default=True, type=int, help='Максимальное количество очков.')
def setup_test_data(count, password, min_score, max_score):
    """Подготавливает локальные тестовые данные для админки и турнирной таблицы."""
    if count < 1:
        raise click.BadParameter('count должен быть больше 0')
    if min_score < 0 or max_score < 0:
        raise click.BadParameter('Очки не могут быть отрицательными')
    if min_score > max_score:
        raise click.BadParameter('min-score не может быть больше max-score')

    db.create_all()
    print('База данных инициализирована!')
    _seed_cities_from_json()
    _ensure_local_admin()
    _seed_tournament_users(
        count=count,
        password=password,
        min_score=min_score,
        max_score=max_score
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5500)
