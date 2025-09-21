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
        'users_with_bikelanes': db.session.query(User.id).join(BikeLane, User.id == BikeLane.user_id).distinct().count(),
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
        'notifications_unread': 0  # TODO: реализовать подсчет уведомлений
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
@bp.route('/users/<int:user_id>/ban', methods=['POST'])
@admin_required
def ban_user(user_id):
    """Заблокировать пользователя"""
    user = User.query.get_or_404(user_id)
    ban_reason = request.form.get('ban_reason', '').strip()
    
    if user.id == current_user.id:
        flash('Нельзя заблокировать самого себя', 'error')
        return redirect(url_for('admin.view_user', user_id=user_id))
    
    if not ban_reason:
        flash('Причина блокировки обязательна', 'error')
        return redirect(url_for('admin.view_user', user_id=user_id))
    
    try:
        from datetime import datetime
        user.is_banned = True
        user.ban_reason = ban_reason
        user.banned_at = datetime.utcnow()
        user.banned_by = current_user.id
        
        db.session.commit()
        flash(f'Пользователь {user.nickname} заблокирован', 'info')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при блокировке пользователя', 'error')
    
    return redirect(url_for('admin.view_user', user_id=user_id))

@bp.route('/users/<int:user_id>/unban', methods=['POST'])
@admin_required  
def unban_user(user_id):
    """Разблокировать пользователя"""
    user = User.query.get_or_404(user_id)
    
    try:
        user.is_banned = False
        user.ban_reason = None
        user.banned_at = None
        user.banned_by = None
        
        db.session.commit()
        flash(f'Пользователь {user.nickname} разблокирован', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при разблокировке пользователя', 'error')
    
    return redirect(url_for('admin.view_user', user_id=user_id))

@bp.route('/users/<int:user_id>/edit-score', methods=['POST'])
@admin_required
def edit_user_score(user_id):
    """Изменить баллы пользователя"""
    user = User.query.get_or_404(user_id)
    
    try:
        manual_score = int(request.form.get('manual_score', 0))
        user.manual_score = manual_score
        
        db.session.commit()
        flash(f'Баллы пользователя {user.nickname} обновлены', 'success')
    except (ValueError, TypeError):
        flash('Некорректное значение баллов', 'error')
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при обновлении баллов', 'error')
    
    return redirect(url_for('admin.view_user', user_id=user_id))
