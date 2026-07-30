from flask import current_app, flash, render_template, request
from flask_login import current_user

from app.models.city import City
from app.services.osm_import import (
    DEFAULT_IMPORT_LIMIT,
    OsmImportError,
    import_osm_bikelanes,
    import_osm_infrastructure,
    preview_osm_bikelanes,
    preview_osm_infrastructure,
)
from . import bp, admin_required


IMPORT_TYPE_BIKELANES = 'bikelanes'
IMPORT_TYPE_BUS_LANES = 'bus_lanes'
IMPORT_TYPE_PARKING = 'bicycle_parking'
IMPORT_TYPE_REPAIR_STATIONS = 'bicycle_repair_station'
IMPORT_TYPE_OPTIONS = (
    (IMPORT_TYPE_BIKELANES, 'Велодорожки'),
    (IMPORT_TYPE_BUS_LANES, 'Автобусные полосы'),
    (IMPORT_TYPE_PARKING, 'Парковки'),
    (IMPORT_TYPE_REPAIR_STATIONS, 'Велостанции'),
)
ALLOWED_IMPORT_TYPES = {value for value, _label in IMPORT_TYPE_OPTIONS}
DEFAULT_IMPORT_TYPES = tuple(value for value, _label in IMPORT_TYPE_OPTIONS)
IMPORT_LIMIT_OPTIONS = (100, 500, 1000)


def _active_cities():
    return City.query.filter_by(status='active').order_by(City.name).all()


def _limit_from_form():
    try:
        return int(request.form.get('limit', DEFAULT_IMPORT_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_IMPORT_LIMIT


def _import_types_from_form():
    return {
        value
        for value in request.form.getlist('import_types')
        if value in ALLOWED_IMPORT_TYPES
    }


def _template_context(**kwargs):
    return {
        'cities': _active_cities(),
        'import_type_options': IMPORT_TYPE_OPTIONS,
        'import_limit_options': IMPORT_LIMIT_OPTIONS,
        **kwargs,
    }


@bp.route('/osm-import')
@admin_required
def osm_import_page():
    return render_template(
        'admin/osm_import.html',
        **_template_context(
            selected_city_id=request.args.get('city_id', ''),
            selected_import_types=set(DEFAULT_IMPORT_TYPES),
            limit=DEFAULT_IMPORT_LIMIT,
            approve=False,
            preview_result=None,
            infrastructure_preview_result=None,
            import_result=None,
            infrastructure_import_result=None,
        ),
    )


@bp.route('/osm-import/preview', methods=['POST'])
@admin_required
def osm_import_preview():
    city_id = request.form.get('city_id', '').strip()
    limit = _limit_from_form()
    approve = request.form.get('approve') == 'on'
    selected_import_types = _import_types_from_form()
    preview_result = None
    infrastructure_preview_result = None

    if not city_id:
        flash('Выберите город для проверки импорта.', 'error')
    elif not selected_import_types:
        flash('Выберите хотя бы один тип объектов для импорта.', 'error')
    else:
        try:
            if selected_import_types & {IMPORT_TYPE_BIKELANES, IMPORT_TYPE_BUS_LANES}:
                preview_result = preview_osm_bikelanes(
                    city_id,
                    limit=limit,
                    include_bikelanes=IMPORT_TYPE_BIKELANES in selected_import_types,
                    include_bus_lanes=IMPORT_TYPE_BUS_LANES in selected_import_types,
                )
            infrastructure_types = selected_import_types & {
                IMPORT_TYPE_PARKING,
                IMPORT_TYPE_REPAIR_STATIONS,
            }
            if infrastructure_types:
                infrastructure_preview_result = preview_osm_infrastructure(
                    city_id,
                    limit=limit,
                    infrastructure_types=infrastructure_types,
                )
        except OsmImportError as exc:
            current_app.logger.exception('Ошибка dry-run OSM импорта')
            flash(str(exc), 'error')
        except Exception:
            current_app.logger.exception('Неожиданная ошибка dry-run OSM импорта')
            flash('Не удалось проверить импорт. Подробности в логах сервера.', 'error')

    return render_template(
        'admin/osm_import.html',
        **_template_context(
            selected_city_id=city_id,
            selected_import_types=selected_import_types,
            limit=limit,
            approve=approve,
            preview_result=preview_result,
            infrastructure_preview_result=infrastructure_preview_result,
            import_result=None,
            infrastructure_import_result=None,
        ),
    )


@bp.route('/osm-import/run', methods=['POST'])
@admin_required
def osm_import_run():
    city_id = request.form.get('city_id', '').strip()
    limit = _limit_from_form()
    approve = request.form.get('approve') == 'on'
    selected_import_types = _import_types_from_form()
    import_result = None
    infrastructure_import_result = None

    if not city_id:
        flash('Выберите город для запуска импорта.', 'error')
    elif not selected_import_types:
        flash('Выберите хотя бы один тип объектов для импорта.', 'error')
    else:
        try:
            if selected_import_types & {IMPORT_TYPE_BIKELANES, IMPORT_TYPE_BUS_LANES}:
                import_result = import_osm_bikelanes(
                    city_id,
                    limit=limit,
                    approve=approve,
                    approved_by=current_user if approve else None,
                    include_bikelanes=IMPORT_TYPE_BIKELANES in selected_import_types,
                    include_bus_lanes=IMPORT_TYPE_BUS_LANES in selected_import_types,
                )
            infrastructure_types = selected_import_types & {
                IMPORT_TYPE_PARKING,
                IMPORT_TYPE_REPAIR_STATIONS,
            }
            if infrastructure_types:
                infrastructure_import_result = import_osm_infrastructure(
                    city_id,
                    limit=limit,
                    infrastructure_types=infrastructure_types,
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
        **_template_context(
            selected_city_id=city_id,
            selected_import_types=selected_import_types,
            limit=limit,
            approve=approve,
            preview_result=None,
            infrastructure_preview_result=None,
            import_result=import_result,
            infrastructure_import_result=infrastructure_import_result,
        ),
    )
