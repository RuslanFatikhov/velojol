# app/routes/admin/bikelanes.py

from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import current_user
from app import db
from app.models.bikelane import BikeLane
from app.models.user import User
from app.models.notification import Notification
from . import bp, admin_required

@bp.route('/bikelanes')
@admin_required
def bikelanes():
    """Страница модерации велодорожек"""
    # Получаем параметры фильтрации
    status_filter = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Базовый запрос
    query = BikeLane.query
    
    # Применяем фильтр по статусу
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    # Сортировка (pending в первую очередь)
    if status_filter == 'all' or status_filter == 'pending':
        query = query.order_by(
            db.case(
                (BikeLane.status == 'pending', 0),
                (BikeLane.status == 'approved', 1),
                (BikeLane.status == 'rejected', 2),
                else_=3
            ),
            BikeLane.created_at.desc()
        )
    else:
        query = query.order_by(BikeLane.created_at.desc())
    
    # Пагинация
    bikelanes = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    # Статистика для фильтров
    filter_stats = {
        'all': BikeLane.query.count(),
        'pending': BikeLane.query.filter_by(status='pending').count(),
        'approved': BikeLane.query.filter_by(status='approved').count(),
        'rejected': BikeLane.query.filter_by(status='rejected').count(),
    }
    
    return render_template('admin/bikelanes.html', 
                         bikelanes=bikelanes,
                         status_filter=status_filter,
                         filter_stats=filter_stats)
