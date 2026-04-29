# app/routes/public.py

from flask import Blueprint, render_template, request, jsonify, url_for
from flask_login import current_user
from app.models.city import City
from app.models.bikelane import BikeLane
from sqlalchemy import or_

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

@bp.route('/')
@bp.route('/cities')
def cities():
    """Страница со списком всех городов"""
    # Получаем параметр поиска
    search_query = request.args.get('search', '').strip()
    
    # Базовый запрос - только активные города
    query = City.query.filter_by(status='active')
    
    # Применяем поиск если есть
    if search_query:
        query = query.filter(
            or_(
                City.name.ilike(f'%{search_query}%'),
                City.country.ilike(f'%{search_query}%')
            )
        )
    
    # Получаем города, сортируем по названию
    cities_list = query.order_by(City.name).all()
    
    # Группируем города по странам
    cities_by_country = {}
    for city in cities_list:
        country = city.country
        if country not in cities_by_country:
            cities_by_country[country] = []
        cities_by_country[country].append(city)
    
    # Сортируем страны
    countries_sorted = sorted(cities_by_country.items(), key=lambda item: item[0].casefold())
    
    return render_template('public/cities.html', 
                         cities_by_country=countries_sorted,
                         search_query=search_query,
                         total_cities=len(cities_list))

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
    
    # Статистика города
    city_stats = {
        'total_bikelanes': city.get_bikelanes_count(),
        'total_distance': city.get_total_distance(),
        'average_rating': city.get_average_rating()
    }
    
    return render_template('public/city.html',
                         city=city,
                         bikelanes=bikelanes,
                         bikelanes_json=bikelanes_json,
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
    
    return jsonify({
        'success': True,
        'city': city.to_dict(),
        'bikelanes': bikelanes_data,
        'count': len(bikelanes_data)
    })

@bp.route('/api/bikelane/<int:bikelane_id>')
def api_bikelane(bikelane_id):
    """API endpoint для получения полной информации о велодорожке"""
    # Находим велодорожку (только одобренные)
    bikelane = BikeLane.query.filter_by(id=bikelane_id, status='approved').first_or_404()
    
    return jsonify({
        'success': True,
        'bikelane': _serialize_bikelane_for_viewer(bikelane)
    })
