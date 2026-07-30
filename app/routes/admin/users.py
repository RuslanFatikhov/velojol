# app/routes/admin/users.py

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from app import db
from app.models.user import User
from app.models.bikelane import BikeLane
from app.models.notification import Notification
from app.models.review import Review
from app.models.verification import VerificationCode
from . import bp, admin_required

@bp.route('/users')
@admin_required
def users():
    """Страница управления пользователями"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    per_page = 50
    
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


@bp.route('/users/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_users():
    """Удалить выбранных пользователей, сохранив созданные ими объекты."""
    selected_ids = []
    for raw_id in request.form.getlist('user_ids'):
        try:
            selected_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    selected_ids = list(dict.fromkeys(selected_ids))

    if not selected_ids:
        flash('Выберите хотя бы одного пользователя.', 'error')
        return redirect(url_for('admin.users'))

    protected_current_user = current_user.id in selected_ids
    selected_ids = [
        user_id for user_id in selected_ids
        if user_id != current_user.id
    ]
    selected_users = User.query.filter(User.id.in_(selected_ids)).all()

    if not selected_users:
        flash('Нельзя удалить текущего администратора.', 'error')
        return redirect(url_for('admin.users'))

    user_ids = [user.id for user in selected_users]
    user_emails = [user.email for user in selected_users if user.email]

    try:
        # Публичные объекты сохраняем, но отвязываем от удаляемых аккаунтов.
        BikeLane.query.filter(BikeLane.user_id.in_(user_ids)).update(
            {BikeLane.user_id: None},
            synchronize_session=False,
        )
        BikeLane.query.filter(BikeLane.moderated_by.in_(user_ids)).update(
            {BikeLane.moderated_by: None},
            synchronize_session=False,
        )
        User.query.filter(User.banned_by.in_(user_ids)).update(
            {User.banned_by: None},
            synchronize_session=False,
        )

        # Персональные данные аккаунта удаляем вместе с пользователем.
        Notification.query.filter(
            Notification.user_id.in_(user_ids)
        ).delete(synchronize_session=False)
        Review.query.filter(
            Review.user_id.in_(user_ids)
        ).delete(synchronize_session=False)
        if user_emails:
            VerificationCode.query.filter(
                VerificationCode.email.in_(user_emails)
            ).delete(synchronize_session=False)

        for user in selected_users:
            db.session.delete(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            'Не удалось удалить пользователей %s',
            user_ids,
        )
        flash('Не удалось удалить выбранных пользователей.', 'error')
        return redirect(url_for('admin.users'))

    message = f'Удалено пользователей: {len(selected_users)}.'
    if protected_current_user:
        message += ' Текущий администратор не был удалён.'
    flash(message, 'success')
    return redirect(url_for('admin.users'))


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
