# app/routes/admin/dashboard.py

from flask import render_template, jsonify
from app import db
from app.models.bikelane import BikeLane
from app.models.user import User
from app.models.city import City
from app.models.notification import Notification
from . import bp, admin_required
from sqlalchemy import func
from datetime import datetime, timedelta

@bp.route('/')
@bp.route('/dashboard')
@admin_required
def dashboard():
    """Главная страница админки с статистикой"""
    
    # Общая статистика
    stats = {
        'total_users': User.query.count(),
        'total_bikelanes': BikeLane.query.count(),
        'pending_bikelanes': BikeLane.query.filter_by(status='pending').count(),
        'approved_bikelanes': BikeLane.query.filter_by(status='approved').count(),
        'rejected_bikelanes': BikeLane.query.filter_by(status='rejected').count(),
        'total_cities': City.query.count(),
        'unread_notifications': Notification.query.filter_by(is_read=False).count()
    }
    
    # Статистика за последние 30 дней
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    recent_stats = {
        'new_users': User.query.filter(User.created_at >= thirty_days_ago).count(),
        'new_bikelanes': BikeLane.query.filter(BikeLane.created_at >= thirty_days_ago).count(),
        'recent_pending': BikeLane.query.filter(
            BikeLane.created_at >= thirty_days_ago,
            BikeLane.status == 'pending'
        ).count()
    }
    
    # Топ городов по количеству велодорожек
    top_cities = db.session.query(
        City.name,
        func.count(BikeLane.id).label('bikelanes_count')
    ).join(BikeLane, City.id == BikeLane.city_id)\
     .group_by(City.id, City.name)\
     .order_by(func.count(BikeLane.id).desc())\
     .limit(5).all()
    
    # Последние велодорожки на модерации
    recent_pending_bikelanes = BikeLane.query\
        .filter_by(status='pending')\
        .order_by(BikeLane.created_at.desc())\
        .limit(10).all()
    
    # Активные пользователи (с велодорожками)
    active_users = db.session.query(
        User.nickname,
        func.count(BikeLane.id).label('bikelanes_count')
    ).join(BikeLane, User.id == BikeLane.user_id)\
     .group_by(User.id, User.nickname)\
     .order_by(func.count(BikeLane.id).desc())\
     .limit(5).all()
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_stats=recent_stats,
                         top_cities=top_cities,
                         recent_pending_bikelanes=recent_pending_bikelanes,
                         active_users=active_users)

@bp.route('/api/stats')
@admin_required
def api_stats():
    """API для получения статистики (для AJAX обновлений)"""
    
    # Статистика по дням за последние 30 дней
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    daily_stats = []
    for i in range(30):
        date = (datetime.utcnow() - timedelta(days=i)).date()
        
        users_count = User.query.filter(
            func.date(User.created_at) == date
        ).count()
        
        bikelanes_count = BikeLane.query.filter(
            func.date(BikeLane.created_at) == date
        ).count()
        
        daily_stats.append({
            'date': date.strftime('%Y-%m-%d'),
            'users': users_count,
            'bikelanes': bikelanes_count
        })
    
    return jsonify({
        'daily_stats': daily_stats[::-1]  # Обращаем для хронологического порядка
    })