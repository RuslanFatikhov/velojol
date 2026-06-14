from flask import current_app, flash, render_template, request
from flask_login import current_user

from app.models.city import City
from app.services.osm_import import (
    OsmImportError,
    import_osm_bikelanes,
    preview_osm_bikelanes,
)
from . import bp, admin_required


def _active_cities():
    return City.query.filter_by(status='active').order_by(City.name).all()


def _limit_from_form():
    try:
        return int(request.form.get('limit', 10))
    except (TypeError, ValueError):
        return 10


@bp.route('/osm-import')
@admin_required
def osm_import_page():
    return render_template(
        'admin/osm_import.html',
        cities=_active_cities(),
        selected_city_id=request.args.get('city_id', ''),
        limit=10,
        approve=False,
        preview_result=None,
        import_result=None,
    )


@bp.route('/osm-import/preview', methods=['POST'])
@admin_required
def osm_import_preview():
    city_id = request.form.get('city_id', '').strip()
    limit = _limit_from_form()
    approve = request.form.get('approve') == 'on'
    preview_result = None

    if not city_id:
        flash('Выберите город для проверки импорта.', 'error')
    else:
        try:
            preview_result = preview_osm_bikelanes(city_id, limit=limit)
        except OsmImportError as exc:
            current_app.logger.exception('Ошибка dry-run OSM импорта')
            flash(str(exc), 'error')
        except Exception:
            current_app.logger.exception('Неожиданная ошибка dry-run OSM импорта')
            flash('Не удалось проверить импорт. Подробности в логах сервера.', 'error')

    return render_template(
        'admin/osm_import.html',
        cities=_active_cities(),
        selected_city_id=city_id,
        limit=limit,
        approve=approve,
        preview_result=preview_result,
        import_result=None,
    )


@bp.route('/osm-import/run', methods=['POST'])
@admin_required
def osm_import_run():
    city_id = request.form.get('city_id', '').strip()
    limit = _limit_from_form()
    approve = request.form.get('approve') == 'on'
    import_result = None

    if not city_id:
        flash('Выберите город для запуска импорта.', 'error')
    else:
        try:
            import_result = import_osm_bikelanes(
                city_id,
                limit=limit,
                approve=approve,
                approved_by=current_user if approve else None,
            )
            flash('OSM импорт завершен.', 'success')
        except OsmImportError as exc:
            current_app.logger.exception('Ошибка запуска OSM импорта')
            flash(str(exc), 'error')
        except Exception:
            current_app.logger.exception('Неожиданная ошибка запуска OSM импорта')
            flash('Не удалось запустить импорт. Подробности в логах сервера.', 'error')

    return render_template(
        'admin/osm_import.html',
        cities=_active_cities(),
        selected_city_id=city_id,
        limit=limit,
        approve=approve,
        preview_result=None,
        import_result=import_result,
    )
