# app/routes/public.py

from flask import Blueprint, render_template, request, jsonify
from app.models.city import City
from app.models.bikelane import BikeLane
from sqlalchemy import or_

# Создаем Blueprint для публичных страниц
bp = Blueprint('public', __name__)

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
    countries_sorted = sorted(cities_by_country.items())
    
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
    bikelanes_json = json.dumps([bl.to_dict() for bl in bikelanes])
    
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
    bikelanes_data = [bl.to_dict() for bl in bikelanes]
    
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
        'bikelane': bikelane.to_dict()
    })