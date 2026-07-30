from app.routes.main import _edit_infrastructure_point
from app.models.infrastructure_point import InfrastructurePoint
from . import admin_required, bp


@bp.route('/infrastructure/<int:infrastructure_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_infrastructure(infrastructure_id):
    point = InfrastructurePoint.query.get_or_404(infrastructure_id)
    return _edit_infrastructure_point(
        point.id,
        point.infrastructure_type,
    )
