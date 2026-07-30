# app/routes/public.py

from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, jsonify, url_for, redirect, abort
from flask_login import current_user
from sqlalchemy import false, func
from app import db
from app.models.city import City
from app.models.bikelane import BikeLane
from app.models.infrastructure_point import InfrastructurePoint
from app.models.user import User

# Создаем Blueprint для публичных страниц
bp = Blueprint('public', __name__)


def _serialize_bikelane_for_viewer(bikelane):
    data = bikelane.to_dict()
    can_edit = current_user.is_authenticated and (
        bikelane.user_id == current_user.id or getattr(current_user, 'is_admin', False)
    )
    if can_edit:
        data['edit_url'] = url_for('main.edit_bikelane', bikelane_id=bikelane.id)
    elif not current_user.is_authenticated:
        data['edit_url'] = url_for('auth.login')
    else:
        data['edit_url'] = None

    data['can_edit'] = can_edit
    return data


def _serialize_infrastructure_for_viewer(point):
    data = point.to_dict()
    edit_endpoint = (
        'main.edit_parking'
        if point.infrastructure_type == InfrastructurePoint.TYPE_BICYCLE_PARKING
        else 'main.edit_repair'
    )
    data['edit_url'] = (
        url_for(edit_endpoint, infrastructure_id=point.id)
        if current_user.is_authenticated and getattr(current_user, 'is_admin', False)
        else None
    )
    return data


def _get_tournament_period(value):
    allowed_periods = {
        'week': 'Неделя',
        'month': 'Месяц',
        'all': 'Всё время',
    }
    period = value if value in allowed_periods else 'week'
    return period, allowed_periods


def _get_tournament_filters():
    countries = [
        country for (country,) in db.session.query(City.country)
        .filter_by(status='active')
        .distinct()
        .order_by(City.country)
        .all()
    ]

    selected_country_id = request.args.get('country_id', '').strip()
    if selected_country_id not in countries:
        selected_country_id = ''

    cities_query = City.query.filter_by(status='active')
    if selected_country_id:
        cities_query = cities_query.filter_by(country=selected_country_id)
    cities = cities_query.order_by(City.name).all()

    all_cities = City.query.filter_by(status='active').order_by(City.country, City.name).all()

    selected_city_id = request.args.get('city_id', '').strip()
    selected_city = None
    if selected_city_id.isdigit():
        selected_city = City.query.filter_by(id=int(selected_city_id), status='active').first()
        if selected_city and selected_country_id and selected_city.country != selected_country_id:
            selected_city = None

    if not selected_city:
        selected_city_id = ''

    return {
        'countries': countries,
        'cities': cities,
        'all_cities': all_cities,
        'selected_country_id': selected_country_id,
        'selected_city_id': selected_city_id,
        'selected_city': selected_city,
    }


def _apply_tournament_geo_filters(query, selected_country_id='', selected_city=None):
    if selected_city:
        return query.filter(
            db.or_(
                BikeLane.city_id == selected_city.id,
                BikeLane.city == selected_city.city_id
            )
        )

    if selected_country_id:
        country_cities = City.query.filter_by(
            country=selected_country_id,
            status='active'
        ).all()
        city_db_ids = [city.id for city in country_cities]
        city_slugs = [city.city_id for city in country_cities]

        if not city_db_ids and not city_slugs:
            return query.filter(false())

        return query.filter(
            db.or_(
                BikeLane.city_id.in_(city_db_ids),
                BikeLane.city.in_(city_slugs)
            )
        )

    return query


def _get_tournament_scores(period, selected_country_id='', selected_city=None):
    query = db.session.query(
        BikeLane.user_id,
        func.coalesce(func.sum(BikeLane.score), 0).label('points')
    ).filter(
        BikeLane.status == 'approved',
        BikeLane.user_id.isnot(None),
        BikeLane.score > 0
    )

    if period in ('week', 'month'):
        days = 7 if period == 'week' else 30
        since = datetime.utcnow() - timedelta(days=days)
        query = query.filter(
            db.or_(
                BikeLane.moderated_at >= since,
                db.and_(
                    BikeLane.moderated_at.is_(None),
                    BikeLane.created_at >= since
                )
            )
        )

    query = _apply_tournament_geo_filters(query, selected_country_id, selected_city)
    rows = query.group_by(BikeLane.user_id).all()
    scores = {user_id: int(points or 0) for user_id, points in rows}

    if period == 'all' and not selected_country_id and not selected_city:
        manual_users = User.query.filter(User.manual_score > 0).all()
        for user in manual_users:
            scores[user.id] = scores.get(user.id, 0) + int(user.manual_score or 0)

    return scores


def _build_tournament_leaderboard(scores):
    if not scores:
        return []

    users = User.query.filter(
        User.id.in_(scores.keys()),
        User.is_banned.is_(False)
    ).all()

    ranked_users = sorted(
        (
            (user, scores.get(user.id, 0))
            for user in users
            if scores.get(user.id, 0) > 0
        ),
        key=lambda item: (-item[1], item[0].nickname.casefold())
    )

    leaderboard = []
    for index, (user, points) in enumerate(ranked_users, start=1):
        leaderboard.append({
            'rank': index,
            'user_id': user.id,
            'display_name': user.nickname,
            'avatar_url': user.display_avatar,
            'points': points,
            'is_current_user': current_user.is_authenticated and current_user.id == user.id,
            'profile_url': url_for('main.user_profile', nickname=user.nickname),
        })

    return leaderboard

@bp.route('/cities')
def cities():
    """Редирект старой страницы городов на главную."""
    return redirect(url_for('main.index'), code=301)


@bp.route('/rating')
def rating():
    """Совместимость со старой ссылкой на рейтинг."""
    return redirect(url_for('public.tournament'), code=302)


@bp.route('/tournament')
def tournament():
    """Страница турнира пользователей по баллам."""
    period, periods = _get_tournament_period(request.args.get('period', 'week'))
    filters = _get_tournament_filters()
    scores = _get_tournament_scores(
        period,
        selected_country_id=filters['selected_country_id'],
        selected_city=filters['selected_city']
    )
    leaderboard = _build_tournament_leaderboard(scores)

    period_tabs = []
    for period_key, label in periods.items():
        params = {'period': period_key}
        if filters['selected_country_id']:
            params['country_id'] = filters['selected_country_id']
        if filters['selected_city_id']:
            params['city_id'] = filters['selected_city_id']

        period_tabs.append({
            'key': period_key,
            'label': label,
            'url': url_for('public.tournament', **params),
            'is_active': period == period_key,
        })

    reset_filter_url = url_for('public.tournament', period=period)

    return render_template(
        'public/tournament.html',
        leaderboard=leaderboard,
        period=period,
        period_tabs=period_tabs,
        selected_country_id=filters['selected_country_id'],
        selected_city_id=filters['selected_city_id'],
        countries=filters['countries'],
        cities=filters['cities'],
        all_cities=filters['all_cities'],
        reset_filter_url=reset_filter_url,
    )

@bp.route('/city/<city_id>')
def city(city_id):
    """Страница конкретного города с картой велодорожек"""
    import json
    
    # Находим город по city_id
    city = City.query.filter_by(city_id=city_id, status='active').first_or_404()
    
    # Получаем параметры фильтров и поиска
    search_query = request.args.get('search', '').strip()
    track_type_filter = request.args.get('track_type', '').strip()
    quality_filter = request.args.get('quality', '').strip()
    
    # Базовый запрос - только одобренные велодорожки этого города
    query = BikeLane.query.filter_by(city=city_id, status='approved')
    
    # Применяем поиск
    if search_query:
        query = query.filter(BikeLane.title.ilike(f'%{search_query}%'))
    
    # Применяем фильтр по типу
    if track_type_filter:
        query = query.filter(BikeLane.track_type == track_type_filter)
    
    # Применяем фильтр по качеству
    if quality_filter:
        try:
            quality_int = int(quality_filter)
            query = query.filter(BikeLane.quality == quality_int)
        except ValueError:
            pass
    
    # Получаем велодорожки
    bikelanes = query.order_by(BikeLane.created_at.desc()).all()
    
    # Конвертируем велодорожки в JSON для JavaScript
    bikelanes_json = json.dumps([_serialize_bikelane_for_viewer(bl) for bl in bikelanes])
    infrastructure_points = InfrastructurePoint.query.filter_by(city_id=city.id).all()
    infrastructure_json = json.dumps([
        _serialize_infrastructure_for_viewer(point)
        for point in infrastructure_points
    ])
    
    # Статистика города
    distance_breakdown = city.get_distance_breakdown()
    city_stats = {
        'total_bikelanes': city.get_bikelanes_count(),
        'total_distance': distance_breakdown['total'],
        'bikelanes_distance': distance_breakdown['bikelanes'],
        'bus_lanes_distance': distance_breakdown['bus_lanes'],
        'average_rating': city.get_average_rating()
    }
    
    return render_template('public/city.html',
                         city=city,
                         bikelanes=bikelanes,
                         bikelanes_json=bikelanes_json,
                         infrastructure_json=infrastructure_json,
                         city_stats=city_stats,
                         search_query=search_query,
                         track_type_filter=track_type_filter,
                         quality_filter=quality_filter)

@bp.route('/api/city/<city_id>/bikelanes')
def api_city_bikelanes(city_id):
    """API endpoint для получения велодорожек города в формате JSON"""
    # Находим город
    city = City.query.filter_by(city_id=city_id, status='active').first_or_404()
    
    # Получаем параметры фильтров
    search_query = request.args.get('search', '').strip()
    track_type_filter = request.args.get('track_type', '').strip()
    quality_filter = request.args.get('quality', '').strip()
    
    # Базовый запрос
    query = BikeLane.query.filter_by(city=city_id, status='approved')
    
    # Применяем фильтры
    if search_query:
        query = query.filter(BikeLane.title.ilike(f'%{search_query}%'))
    
    if track_type_filter:
        query = query.filter(BikeLane.track_type == track_type_filter)
    
    if quality_filter:
        try:
            quality_int = int(quality_filter)
            query = query.filter(BikeLane.quality == quality_int)
        except ValueError:
            pass
    
    # Получаем велодорожки
    bikelanes = query.all()
    
    # Конвертируем в JSON
    bikelanes_data = [_serialize_bikelane_for_viewer(bl) for bl in bikelanes]
    infrastructure_data = [
        _serialize_infrastructure_for_viewer(point)
        for point in InfrastructurePoint.query.filter_by(city_id=city.id).all()
    ]
    
    return jsonify({
        'success': True,
        'city': city.to_dict(),
        'bikelanes': bikelanes_data,
        'infrastructure': infrastructure_data,
        'count': len(bikelanes_data),
        'infrastructure_count': len(infrastructure_data),
    })


@bp.route('/api/infrastructure/<int:infrastructure_id>')
def api_infrastructure(infrastructure_id):
    """Полная информация о велопарковке или ремонтной стойке."""
    point = InfrastructurePoint.query.get_or_404(infrastructure_id)
    return jsonify({
        'success': True,
        'infrastructure': _serialize_infrastructure_for_viewer(point),
    })


@bp.route('/api/bikelane/<int:bikelane_id>')
def api_bikelane(bikelane_id):
    """API endpoint для получения полной информации о велодорожке"""
    bikelane = BikeLane.query.get_or_404(bikelane_id)
    can_view_private = current_user.is_authenticated and (
        bikelane.user_id == current_user.id or getattr(current_user, 'is_admin', False)
    )

    if bikelane.status != 'approved' and not can_view_private:
        abort(404)
    
    return jsonify({
        'success': True,
        'bikelane': _serialize_bikelane_for_viewer(bikelane)
    })
