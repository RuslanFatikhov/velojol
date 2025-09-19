# app/routes/admin/users.py

from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_login import current_user
from app import db
from app.models.user import User
from app.models.bikelane import BikeLane
from app.models.notification import Notification
from . import bp, admin_required

@bp.route('/users')
@admin_required
def users():
    """Страница управления пользователями"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    per_page = 20
    
    # Базовый запрос
    query = User.query
    
    # Применяем поиск
    if search:
        query = query.filter(
            db.or_(
                User.nickname.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    
    # Сортировка (админы в первую очередь)
    query = query.order_by(
        User.is_admin.desc(),
        User.created_at.desc()
    )
    
    # Пагинация
    users = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    # Статистика пользователей
    stats = {
        'total_users': User.query.count(),
        'admin_users': User.query.filter_by(is_admin=True).count(),
        'users_with_bikelanes': db.session.query(User.id).join(BikeLane).distinct().count(),
        'active_users_30d': User.query.filter(
            User.created_at >= db.func.date('now', '-30 days')
        ).count()
    }
    
    return render_template('admin/users.html', 
                         users=users,
                         search=search,
                         stats=stats)

@bp.route('/users/<int:user_id>')
@admin_required
def view_user(user_id):
    """Просмотр профиля пользователя"""
    user = User.query.get_or_404(user_id)
    
    # Статистика пользователя
    user_stats = {
        'bikelanes_total': user.get_bikelanes_count(),
        'bikelanes_pending': user.get_pending_bikelanes_count(),
        'bikelanes_approved': user.get_approved_bikelanes_count(),
        'total_score': user.get_total_score(),
        'notifications_unread': user.get_unread_notifications_count()
    }
    
    # Последние велодорожки пользователя
    recent_bikelanes = user.bikelanes.order_by(BikeLane.created_at.desc()).limit(10).all()
    
    # Последние уведомления пользователя
    recent_notifications = user.notifications.order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('admin/view_user.html',
                         user=user,
                         user_stats=user_stats,
                         recent_bikelanes=recent_bikelanes,
                         recent_notifications=recent_notifications)

@bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    """Переключение админских прав пользователя"""
    user = User.query.get_or_404(user_id)
    
    # Нельзя убрать права у себя
    if user.id == current_user.id:
        flash('Нельзя изменить свои собственные права администратора', 'error')
        return redirect(url_for('admin.view_user', user_id=user_id))
    
    try:
        user.is_admin = not user.is_admin
        db.session.commit()
        
        action = 'выданы' if user.is_admin else 'отозваны'
        flash(f'Права администратора {action} для пользователя {user.nickname}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Произошла ошибка при изменении прав', 'error')
    
    return redirect(url_for('admin.view_user', user_id=user_id))

@bp.route('/users/<int:user_id>/send-notification', methods=['POST'])
@admin_required
def send_notification(user_id):
    """Отправка уведомления пользователю"""
    user = User.query.get_or_404(user_id)
    
    title = request.form.get('title', '').strip()
    message = request.form.get('message', '').strip()
    
    if not title or not message:
        flash('Заголовок и сообщение обязательны', 'error')
        return redirect(url_for('admin.view_user', user_id=user_id))
    
    try:
        # Создаем уведомление
        notification = Notification(
            user_id=user.id,
            type='bikelane_pending',  # Используем существующий тип
            title=title,
            message=message
        )
        
        db.session.add(notification)
        db.session.commit()
        
        flash(f'Уведомление отправлено пользователю {user.nickname}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Произошла ошибка при отправке уведомления', 'error')
    
    return redirect(url_for('admin.view_user', user_id=user_id))

@bp.route('/api/users/search')
@admin_required
def api_search_users():
    """API для поиска пользователей (для автокомплита)"""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([])
    
    users = User.query.filter(
        db.or_(
            User.nickname.ilike(f'%{query}%'),
            User.email.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    results = []
    for user in users:
        results.append({
            'id': user.id,
            'nickname': user.nickname,
            'email': user.email,
            'is_admin': user.is_admin,
            'bikelanes_count': user.get_bikelanes_count()
        })
    
    return jsonify(results)