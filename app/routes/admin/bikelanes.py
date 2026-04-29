from flask import current_app, render_template, request, flash, redirect, url_for
from flask_login import current_user
from app import db
from app.models.bikelane import BikeLane
from . import bp, admin_required

@bp.route('/bikelanes')
@admin_required
def bikelanes():
    """Страница модерации велодорожек"""
    status_filter = request.args.get('status', 'pending')
    
    if status_filter == 'all':
        bikelanes = BikeLane.query.order_by(BikeLane.created_at.desc()).all()
    else:
        bikelanes = BikeLane.query.filter_by(status=status_filter).order_by(BikeLane.created_at.desc()).all()
    
    return render_template('admin/bikelanes.html', bikelanes=bikelanes, status_filter=status_filter)

@bp.route('/bikelanes/<int:bikelane_id>/approve', methods=['POST'])
@admin_required
def approve_bikelane(bikelane_id):
    """Одобрение велодорожки"""
    bikelane = BikeLane.query.get_or_404(bikelane_id)
    comment = request.form.get('comment', '').strip()

    try:
        bikelane.approve(current_user, comment)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            'Не удалось одобрить велодорожку id=%s', bikelane_id
        )
        flash('Не удалось одобрить велодорожку. Подробности в логах сервера.', 'error')
        return redirect(url_for('admin.view_bikelane', bikelane_id=bikelane_id))

    flash(f'Велодорожка "{bikelane.title}" одобрена!', 'success')
    return redirect(url_for('admin.bikelanes'))

@bp.route('/bikelanes/<int:bikelane_id>/reject', methods=['POST'])
@admin_required
def reject_bikelane(bikelane_id):
    """Отклонение велодорожки"""
    bikelane = BikeLane.query.get_or_404(bikelane_id)
    comment = request.form.get('comment', '').strip()
    
    if not comment:
        flash('Комментарий обязателен при отклонении', 'error')
        return redirect(url_for('admin.bikelanes'))
    
    try:
        bikelane.reject(current_user, comment)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            'Не удалось отклонить велодорожку id=%s', bikelane_id
        )
        flash('Не удалось отклонить велодорожку. Подробности в логах сервера.', 'error')
        return redirect(url_for('admin.view_bikelane', bikelane_id=bikelane_id))

    flash(f'Велодорожка "{bikelane.title}" отклонена', 'info')
    return redirect(url_for('admin.bikelanes'))

@bp.route('/bikelanes/<int:bikelane_id>')
@admin_required
def view_bikelane(bikelane_id):
    """Детальный просмотр велодорожки"""
    bikelane = BikeLane.query.get_or_404(bikelane_id)
    return render_template('admin/view_bikelane.html', bikelane=bikelane)

@bp.route('/bikelanes/<int:bikelane_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_bikelane(bikelane_id):
    """Редактирование велодорожки"""
    bikelane = BikeLane.query.get_or_404(bikelane_id)
    
    if request.method == 'POST':
        bikelane.title = request.form.get('title', '').strip()
        bikelane.description = request.form.get('description', '').strip()
        bikelane.track_type = request.form.get('track_type', '')
        bikelane.quality = int(request.form.get('quality', 3))
        bikelane.admin_comment = request.form.get('admin_comment', '').strip()
        geometry = request.form.get("geometry", "").strip()
        if geometry:
            bikelane.geometry = geometry
        
        # Обновляем геометрию если изменена
        geometry = request.form.get("geometry", "").strip()
        if geometry:
            bikelane.geometry = geometry
        
        # Обновляем геометрию если изменена
        geometry = request.form.get("geometry", "").strip()
        if geometry:
            bikelane.geometry = geometry
        
        # Обновляем геометрию если изменена
        geometry = request.form.get("geometry", "").strip()
        if geometry:
            bikelane.geometry = geometry
        
        db.session.commit()
        flash('Велодорожка обновлена!', 'success')
        return redirect(url_for('admin.view_bikelane', bikelane_id=bikelane_id))
    
    return render_template('admin/edit_bikelane.html', bikelane=bikelane)

@bp.route('/bikelanes/<int:bikelane_id>/delete', methods=['POST'])
@admin_required
def delete_bikelane(bikelane_id):
    """Удаление велодорожки"""
    bikelane = BikeLane.query.get_or_404(bikelane_id)
    title = bikelane.title
    
    db.session.delete(bikelane)
    db.session.commit()
    
    flash(f'Велодорожка "{title}" удалена', 'info')
    return redirect(url_for('admin.bikelanes'))
