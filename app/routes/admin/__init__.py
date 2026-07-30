# app/routes/admin/__init__.py

from flask import Blueprint, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps

# Создаем Blueprint для админки
bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Декоратор для проверки прав администратора"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

# Импортируем все роуты админки
from . import (
    bikelanes,
    cities,
    city_requests,
    dashboard,
    infrastructure,
    osm_import,
    reviews,
    users,
)
