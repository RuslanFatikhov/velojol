from flask import render_template, request
from sqlalchemy.orm import joinedload

from app.models.review import Review
from . import admin_required, bp


@bp.route('/reviews')
@admin_required
def reviews():
    """Показать все отзывы пользователей."""
    page = request.args.get('page', 1, type=int)
    reviews_page = Review.query.options(
        joinedload(Review.user),
        joinedload(Review.bikelane),
        joinedload(Review.infrastructure_point),
    ).order_by(
        Review.updated_at.desc(),
        Review.id.desc(),
    ).paginate(
        page=page,
        per_page=50,
        error_out=False,
    )

    return render_template(
        'admin/reviews.html',
        reviews=reviews_page,
    )
