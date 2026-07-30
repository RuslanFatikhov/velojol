from flask import current_app, render_template, request, flash, redirect, url_for
from flask_login import current_user
from app import db
from app.models.bikelane import BikeLane
from app.models.city import City
from app.models.infrastructure_point import InfrastructurePoint
from app.services.bikelane_merge import merge_bikelanes
from app.routes.main import (
    _apply_bikelane_form_data,
    _build_bikelane_form_context,
    _extract_bikelane_form_data,
    _get_active_cities_data,
    _get_bikelane_reward_config,
    _save_bikelane_uploaded_photos,
    _validate_bikelane_form_data,
)
from . import bp, admin_required


DATA_TYPE_BIKELANES = 'bikelanes'
DATA_TYPE_BUS_LANES = 'bus_lanes'
DATA_TYPE_PARKING = InfrastructurePoint.TYPE_BICYCLE_PARKING
DATA_TYPE_REPAIR_STATIONS = InfrastructurePoint.TYPE_REPAIR_STATION
DATA_TYPE_OPTIONS = (
    (DATA_TYPE_BIKELANES, 'Велодорожки'),
    (DATA_TYPE_BUS_LANES, 'Автобусные полосы'),
    (DATA_TYPE_PARKING, 'Велопарковки'),
    (DATA_TYPE_REPAIR_STATIONS, 'Ремонтные станции'),
)
ALLOWED_DATA_TYPES = {value for value, _label in DATA_TYPE_OPTIONS}
LINE_DATA_TYPES = {DATA_TYPE_BIKELANES, DATA_TYPE_BUS_LANES}


@bp.route('/bikelanes')
@admin_required
def bikelanes():
    """Единая страница управления данными карты."""
    page = request.args.get('page', 1, type=int)
    data_type = request.args.get('data_type', DATA_TYPE_BIKELANES)
    if data_type not in ALLOWED_DATA_TYPES:
        data_type = DATA_TYPE_BIKELANES
    status_filter = request.args.get('status', 'pending')
    if status_filter not in {'pending', 'approved', 'rejected', 'all'}:
        status_filter = 'pending'

    bikelanes = []
    infrastructure_points = []
    cities_by_id = {}
    pagination = None

    if data_type in LINE_DATA_TYPES:
        query = BikeLane.query
        if data_type == DATA_TYPE_BUS_LANES:
            query = query.filter(BikeLane.track_type == 'bus_lane')
        else:
            query = query.filter(BikeLane.track_type != 'bus_lane')

        if status_filter != 'all':
            query = query.filter(BikeLane.status == status_filter)
        pagination = query.order_by(
            BikeLane.created_at.desc(),
            BikeLane.id.desc(),
        ).paginate(
            page=page,
            per_page=50,
            error_out=False,
        )
        bikelanes = pagination.items
    else:
        pagination = InfrastructurePoint.query.filter_by(
            infrastructure_type=data_type,
        ).order_by(
            InfrastructurePoint.created_at.desc(),
            InfrastructurePoint.id.desc(),
        ).paginate(
            page=page,
            per_page=50,
            error_out=False,
        )
        infrastructure_points = pagination.items
        city_ids = {point.city_id for point in infrastructure_points}
        if city_ids:
            cities_by_id = {
                city.id: city.name
                for city in City.query.filter(City.id.in_(city_ids)).all()
            }

    return render_template(
        'admin/bikelanes.html',
        bikelanes=bikelanes,
        infrastructure_points=infrastructure_points,
        cities_by_id=cities_by_id,
        data_type=data_type,
        data_type_options=DATA_TYPE_OPTIONS,
        is_line_data=data_type in LINE_DATA_TYPES,
        status_filter=status_filter,
        pagination=pagination,
    )


@bp.route('/bikelanes/bulk-action', methods=['POST'])
@admin_required
def bulk_bikelane_action():
    """Массовая модерация и удаление выбранных велодорожек."""
    action = request.form.get('action', '').strip()
    comment = request.form.get('comment', '').strip()
    status_filter = request.form.get('status_filter', 'pending').strip()
    data_type = request.form.get('data_type', DATA_TYPE_BIKELANES).strip()
    if data_type not in LINE_DATA_TYPES:
        data_type = DATA_TYPE_BIKELANES
    if status_filter not in {'pending', 'approved', 'rejected', 'all'}:
        status_filter = 'pending'

    selected_ids = []
    for raw_id in request.form.getlist('bikelane_ids'):
        try:
            selected_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    selected_ids = list(dict.fromkeys(selected_ids))

    if not selected_ids:
        flash('Выберите хотя бы одну строку.', 'error')
        return redirect(url_for(
            'admin.bikelanes',
            data_type=data_type,
            status=status_filter,
        ))
    if action not in {'approve', 'reject', 'delete', 'merge'}:
        flash('Неизвестное массовое действие.', 'error')
        return redirect(url_for(
            'admin.bikelanes',
            data_type=data_type,
            status=status_filter,
        ))
    if action == 'reject' and not comment:
        flash('Комментарий обязателен при отклонении.', 'error')
        return redirect(url_for(
            'admin.bikelanes',
            data_type=data_type,
            status=status_filter,
        ))
    if action == 'merge' and len(selected_ids) < 2:
        flash('Для объединения выберите минимум две линии.', 'error')
        return redirect(url_for(
            'admin.bikelanes',
            data_type=data_type,
            status=status_filter,
        ))

    selected_query = BikeLane.query.filter(BikeLane.id.in_(selected_ids))
    if data_type == DATA_TYPE_BUS_LANES:
        selected_query = selected_query.filter(BikeLane.track_type == 'bus_lane')
    else:
        selected_query = selected_query.filter(BikeLane.track_type != 'bus_lane')
    selected_bikelanes = selected_query.all()
    if not selected_bikelanes:
        flash('Выбранные велодорожки не найдены.', 'error')
        return redirect(url_for(
            'admin.bikelanes',
            data_type=data_type,
            status=status_filter,
        ))
    if action == 'merge' and len(selected_bikelanes) != len(selected_ids):
        flash('Некоторые выбранные линии не найдены или относятся к другому типу.', 'error')
        return redirect(url_for(
            'admin.bikelanes',
            data_type=data_type,
            status=status_filter,
        ))

    try:
        merged_bikelane = None
        if action == 'merge':
            merged_bikelane = merge_bikelanes(selected_bikelanes, current_user)
        else:
            for bikelane in selected_bikelanes:
                if action == 'approve':
                    bikelane.approve(current_user)
                elif action == 'reject':
                    bikelane.reject(current_user, comment)
                else:
                    db.session.delete(bikelane)
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        flash(str(error), 'error')
        return redirect(url_for(
            'admin.bikelanes',
            data_type=data_type,
            status=status_filter,
        ))
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            'Не удалось выполнить массовое действие %s для велодорожек %s',
            action,
            selected_ids,
        )
        flash('Не удалось выполнить массовое действие.', 'error')
        return redirect(url_for(
            'admin.bikelanes',
            data_type=data_type,
            status=status_filter,
        ))

    action_messages = {
        'approve': 'одобрено',
        'reject': 'отклонено',
        'delete': 'удалено',
        'merge': 'объединено',
    }
    if action == 'merge':
        flash(
            f'Объединено линий: {len(selected_bikelanes)}. '
            f'Основная линия: №{merged_bikelane.id}.',
            'success',
        )
        return redirect(url_for(
            'admin.view_bikelane',
            bikelane_id=merged_bikelane.id,
        ))
    flash(
        f'Выбрано объектов: {len(selected_bikelanes)}; '
        f'{action_messages[action]}.',
        'success' if action == 'approve' else 'info',
    )
    return redirect(url_for(
        'admin.bikelanes',
        data_type=data_type,
        status=status_filter,
    ))


@bp.route('/infrastructure/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_infrastructure():
    """Удалить выбранные парковки или ремонтные станции."""
    data_type = request.form.get('data_type', DATA_TYPE_PARKING).strip()
    if data_type not in {DATA_TYPE_PARKING, DATA_TYPE_REPAIR_STATIONS}:
        data_type = DATA_TYPE_PARKING

    selected_ids = []
    for raw_id in request.form.getlist('infrastructure_ids'):
        try:
            selected_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    selected_ids = list(dict.fromkeys(selected_ids))

    if not selected_ids:
        flash('Выберите хотя бы одну строку.', 'error')
        return redirect(url_for('admin.bikelanes', data_type=data_type))

    selected_points = InfrastructurePoint.query.filter(
        InfrastructurePoint.id.in_(selected_ids),
        InfrastructurePoint.infrastructure_type == data_type,
    ).all()
    if not selected_points:
        flash('Выбранные объекты не найдены.', 'error')
        return redirect(url_for('admin.bikelanes', data_type=data_type))

    try:
        for point in selected_points:
            db.session.delete(point)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            'Не удалось удалить объекты инфраструктуры %s',
            selected_ids,
        )
        flash('Не удалось удалить выбранные объекты.', 'error')
        return redirect(url_for('admin.bikelanes', data_type=data_type))

    flash(f'Удалено объектов: {len(selected_points)}.', 'info')
    return redirect(url_for('admin.bikelanes', data_type=data_type))


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
    return redirect(url_for(
        'admin.bikelanes',
        data_type=request.form.get('return_data_type', DATA_TYPE_BIKELANES),
        status=request.form.get('return_status', 'pending'),
    ))

@bp.route('/bikelanes/<int:bikelane_id>/reject', methods=['POST'])
@admin_required
def reject_bikelane(bikelane_id):
    """Отклонение велодорожки"""
    bikelane = BikeLane.query.get_or_404(bikelane_id)
    comment = request.form.get('comment', '').strip()
    
    if not comment:
        flash('Комментарий обязателен при отклонении', 'error')
        return redirect(url_for(
            'admin.bikelanes',
            data_type=request.form.get('return_data_type', DATA_TYPE_BIKELANES),
            status=request.form.get('return_status', 'pending'),
        ))
    
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
    return redirect(url_for(
        'admin.bikelanes',
        data_type=request.form.get('return_data_type', DATA_TYPE_BIKELANES),
        status=request.form.get('return_status', 'pending'),
    ))

@bp.route('/bikelanes/<int:bikelane_id>')
@admin_required
def view_bikelane(bikelane_id):
    """Детальный просмотр велодорожки"""
    bikelane = BikeLane.query.get_or_404(bikelane_id)
    return render_template('admin/view_bikelane.html', bikelane=bikelane)

@bp.route('/bikelanes/<int:bikelane_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_bikelane(bikelane_id):
    """Редактирование велодорожки админом через общую форму."""
    bikelane = BikeLane.query.get_or_404(bikelane_id)

    if request.method == 'GET':
        return render_template(
            'add_bikelane.html',
            form_data=_build_bikelane_form_context(bikelane),
            is_edit_mode=True,
            is_admin_edit_mode=True,
            form_action=url_for('admin.edit_bikelane', bikelane_id=bikelane.id),
            return_url=url_for('admin.view_bikelane', bikelane_id=bikelane.id),
            cities_data=_get_active_cities_data(),
            reward_config=_get_bikelane_reward_config(),
            description_min_length=1,
        )

    try:
        form_data = _extract_bikelane_form_data()
        errors, distance_value = _validate_bikelane_form_data(
            form_data,
            min_description_length=1,
        )
        if errors:
            return {
                'success': False,
                'error': 'Ошибки валидации: ' + '; '.join(errors),
            }, 400

        _apply_bikelane_form_data(
            bikelane,
            form_data,
            distance_value=distance_value,
            reset_moderation=False,
        )
        _save_bikelane_uploaded_photos(bikelane)
        bikelane.approve(current_user)
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        return {'success': False, 'error': str(error)}, 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            'Не удалось обновить велодорожку id=%s',
            bikelane_id,
        )
        return {
            'success': False,
            'error': 'Не удалось сохранить изменения',
        }, 500

    detail_url = url_for('admin.view_bikelane', bikelane_id=bikelane.id)
    return {
        'success': True,
        'message': 'Изменения опубликованы',
        'modal_title': 'Изменения опубликованы',
        'modal_message': 'Изменения сохранены и сразу опубликованы.',
        'primary_action_label': 'К велодорожке',
        'close_action_label': 'Закрыть',
        'redirect_url': detail_url,
        'bikelane_id': bikelane.id,
    }

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
