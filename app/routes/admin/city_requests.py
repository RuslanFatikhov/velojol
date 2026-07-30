from flask import render_template, request
from sqlalchemy.orm import joinedload

from app.models.city_request import CityRequest
from . import admin_required, bp


@bp.route('/city-requests')
@admin_required
def city_requests():
    """Показать заявки посетителей на добавление городов."""
    page = request.args.get('page', 1, type=int)
    city_requests_page = CityRequest.query.options(
        joinedload(CityRequest.user),
    ).order_by(
        CityRequest.created_at.desc(),
        CityRequest.id.desc(),
    ).paginate(
        page=page,
        per_page=50,
        error_out=False,
    )

    return render_template(
        'admin/city_requests.html',
        city_requests=city_requests_page,
    )
