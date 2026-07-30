from flask import Blueprint, abort, current_app, jsonify, request, url_for
from flask_login import current_user

from app import db
from app.models.bikelane import BikeLane
from app.models.infrastructure_point import InfrastructurePoint
from app.models.review import Review
from app.utils.file_handler import FileHandler


bp = Blueprint('reviews', __name__, url_prefix='/api/reviews')


def _target_or_404(target_type, target_id):
    if target_type == 'bikelane':
        target = BikeLane.query.get_or_404(target_id)
        if target.status != 'approved':
            abort(404)
        return target
    if target_type == 'infrastructure':
        return InfrastructurePoint.query.get_or_404(target_id)
    abort(404)


def _reviews_query(target_type, target_id):
    if target_type == 'bikelane':
        return Review.query.filter_by(bikelane_id=target_id)
    return Review.query.filter_by(infrastructure_point_id=target_id)


def _review_for_current_user(target_type, target_id):
    if not current_user.is_authenticated:
        return None
    return _reviews_query(target_type, target_id).filter_by(
        user_id=current_user.id,
    ).first()


def _reviews_response(target_type, target_id):
    reviews = _reviews_query(target_type, target_id).order_by(
        Review.updated_at.desc(),
        Review.id.desc(),
    ).all()
    count = len(reviews)
    average = (
        round(sum(review.rating for review in reviews) / count, 1)
        if count
        else None
    )
    own_review = _review_for_current_user(target_type, target_id)

    return {
        'success': True,
        'summary': {
            'average': average,
            'count': count,
        },
        'reviews': [review.to_dict() for review in reviews],
        'current_user_review': own_review.to_dict() if own_review else None,
        'authenticated': current_user.is_authenticated,
        'login_url': url_for('auth.login'),
        'max_photos': current_app.config.get('MAX_PHOTOS_PER_REVIEW', 5),
        'max_text_length': current_app.config.get('MAX_REVIEW_LENGTH', 2000),
    }


@bp.route('/<target_type>/<int:target_id>', methods=['GET', 'POST'])
def object_reviews(target_type, target_id):
    target = _target_or_404(target_type, target_id)

    if request.method == 'GET':
        return jsonify(_reviews_response(target_type, target_id))

    if not current_user.is_authenticated:
        return jsonify({
            'success': False,
            'error': 'Войдите, чтобы оставить отзыв.',
            'login_url': url_for('auth.login'),
        }), 401
    if getattr(current_user, 'is_banned', False):
        return jsonify({
            'success': False,
            'error': 'Ваш аккаунт заблокирован.',
        }), 403

    try:
        rating = int(request.form.get('rating', ''))
    except (TypeError, ValueError):
        rating = 0
    if rating < 1 or rating > 5:
        return jsonify({
            'success': False,
            'error': 'Выберите оценку от 1 до 5.',
        }), 400

    text = request.form.get('text', '').strip()
    max_text_length = current_app.config.get('MAX_REVIEW_LENGTH', 2000)
    if len(text) > max_text_length:
        return jsonify({
            'success': False,
            'error': f'Отзыв не должен превышать {max_text_length} символов.',
        }), 400

    review = _review_for_current_user(target_type, target_id)
    if review is None:
        review = Review(
            user_id=current_user.id,
            rating=rating,
            text=text,
        )
        if target_type == 'bikelane':
            review.bikelane = target
        else:
            review.infrastructure_point = target
        db.session.add(review)
    else:
        review.rating = rating
        review.text = text

    try:
        db.session.flush()
        existing_photos = review.get_photos_list()
        available_slots = max(
            0,
            current_app.config.get('MAX_PHOTOS_PER_REVIEW', 5)
            - len(existing_photos),
        )
        uploaded_files = [
            file
            for file in request.files.getlist('photos')
            if file and file.filename
        ][:available_slots]
        if uploaded_files:
            existing_photos.extend(
                FileHandler.save_review_photos(uploaded_files, review.id)
            )
            review.set_photos_list(existing_photos)

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            'Не удалось сохранить отзыв для %s/%s',
            target_type,
            target_id,
        )
        return jsonify({
            'success': False,
            'error': 'Не удалось сохранить отзыв.',
        }), 500

    response = _reviews_response(target_type, target_id)
    response['message'] = 'Отзыв сохранён.'
    return jsonify(response)
