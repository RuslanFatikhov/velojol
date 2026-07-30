from flask_login import current_user, login_required
# app/routes/main.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from app import db
from app.models.bikelane import BikeLane
from app.models.city import City
from app.models.city_request import CityRequest
from app.models.infrastructure_point import InfrastructurePoint
from app.services.infrastructure_edit import (
    apply_infrastructure_form,
    infrastructure_form_fields,
)
from app.utils.validators import BikeLaneValidator
from app.utils.file_handler import FileHandler
import json
import re
import unicodedata
import uuid

# Создаем Blueprint
bp = Blueprint('main', __name__)

def _get_active_cities_data():
    cities = City.query.filter_by(status='active').order_by(City.name).all()
    return {'cities': [city.to_dict() for city in cities]}


def _get_bikelane_reward_config():
    return BikeLane.get_reward_config()


def _extract_bikelane_form_data():
    return {
        'city': request.form.get('city', '').strip(),
        'title': request.form.get('title', '').strip(),
        'description': request.form.get('description', '').strip(),
        'track_type': request.form.get('track_type', ''),
        'quality': request.form.get('quality', ''),
        'has_parking': request.form.get('has_parking', 'false').lower() == 'true',
        'has_markings': request.form.get('has_markings', 'false').lower() == 'true',
        'has_signs': request.form.get('has_signs', 'false').lower() == 'true',
        'is_one_way': request.form.get('is_one_way', 'false').lower() == 'true',
        'overall_quality': request.form.get('overall_quality', ''),
        'geometry': request.form.get('geometry', ''),
        'distance': request.form.get('distance', ''),
        'video_url': request.form.get('video_url', '').strip(),
    }


def _validate_bikelane_form_data(form_data, min_description_length=20):
    errors = []
    is_bus_lane = form_data['track_type'] == 'bus_lane'

    if not form_data['city']:
        errors.append('Необходимо выбрать город')

    if len(form_data['title']) < 3:
        errors.append('Название должно содержать минимум 3 символа')

    if not is_bus_lane and len(form_data['description']) < min_description_length:
        errors.append(
            f'Описание должно содержать минимум {min_description_length} символов'
        )

    if not form_data['track_type']:
        errors.append('Необходимо выбрать тип дорожки')

    if not form_data['geometry']:
        errors.append('Необходимо нарисовать линию на карте')
    else:
        try:
            geometry_data = json.loads(form_data['geometry'])
            if not geometry_data.get('coordinates') or len(geometry_data.get('coordinates', [])) < 2:
                errors.append('Линия должна содержать минимум 2 точки')
        except (json.JSONDecodeError, TypeError):
            errors.append('Ошибка в данных геометрии')

    distance_value = None
    if form_data['distance']:
        try:
            distance_value = float(form_data['distance'])
            if distance_value < 10:
                errors.append('Велодорожка должна быть длиннее 10 метров')
            elif distance_value > 50000:
                errors.append('Велодорожка не может быть длиннее 50 километров')
        except (ValueError, TypeError):
            errors.append('Некорректное значение дистанции')

    allowed_track_types = ['lane', 'bollards', 'separated', 'shared', 'bus_lane']
    if form_data['track_type'] not in allowed_track_types:
        errors.append('Недопустимый тип дорожки')

    if form_data['quality']:
        try:
            quality_value = int(form_data['quality'])
            if quality_value < 1 or quality_value > 5:
                errors.append('Недопустимое качество покрытия')
        except (ValueError, TypeError):
            errors.append('Недопустимое качество покрытия')

    return errors, distance_value


def _build_bikelane_form_context(bikelane):
    videos = bikelane.get_videos_list()
    return {
        'city': bikelane.city,
        'title': bikelane.title,
        'description': bikelane.description,
        'track_type': bikelane.track_type,
        'quality': str(bikelane.quality) if bikelane.quality else '',
        'has_parking': bikelane.has_parking,
        'has_markings': bikelane.has_markings,
        'has_signs': bikelane.has_signs,
        'is_one_way': bikelane.is_one_way,
        'overall_quality': bikelane.overall_quality,
        'geometry': bikelane.geometry,
        'video_url': videos[0] if videos else '',
        'existing_photos': bikelane.get_photos_list(),
    }


def _apply_bikelane_form_data(bikelane, form_data, distance_value=None, reset_moderation=False):
    city_obj = City.query.filter_by(city_id=form_data['city']).first()
    if not city_obj:
        raise ValueError(f'Город {form_data["city"]} не найден в базе данных')

    bikelane.title = form_data['title']
    bikelane.description = form_data['description']
    bikelane.city = form_data['city']
    bikelane.city_id = city_obj.id
    bikelane.track_type = form_data['track_type']
    is_bus_lane = bikelane.track_type == 'bus_lane'
    bikelane.description = '' if is_bus_lane else form_data['description']
    bikelane.quality = 0 if is_bus_lane else (
        int(form_data['quality']) if form_data['quality'] else 0
    )
    bikelane.has_parking = False if is_bus_lane else form_data['has_parking']
    bikelane.has_markings = False if is_bus_lane else form_data['has_markings']
    bikelane.has_signs = False if is_bus_lane else form_data['has_signs']
    bikelane.is_one_way = False if is_bus_lane else form_data['is_one_way']
    bikelane.geometry = form_data['geometry']

    if distance_value is not None:
        bikelane.distance = distance_value
    else:
        bikelane.distance = bikelane.calculate_length() * 1000

    if is_bus_lane:
        bikelane.overall_quality = None
    else:
        # Итоговая оценка всегда рассчитывается на сервере из характеристик.
        # Скрытое поле формы используется только для мгновенного превью звёзд.
        bikelane.overall_quality = bikelane.calculate_overall_quality()
    bikelane.set_photos_list(bikelane.get_photos_list())

    if is_bus_lane:
        bikelane.set_videos_list([])
    elif form_data['video_url']:
        bikelane.set_videos_list([form_data['video_url']])
    else:
        bikelane.set_videos_list([])

    if reset_moderation:
        bikelane.status = 'pending'
        bikelane.admin_comment = None
        bikelane.moderated_at = None
        bikelane.moderated_by = None


def _save_bikelane_uploaded_photos(bikelane):
    existing_photos = bikelane.get_photos_list()
    uploaded_files = request.files.getlist('photos')

    if not uploaded_files or not uploaded_files[0].filename:
        return

    new_photos = FileHandler.save_uploaded_files(
        uploaded_files,
        current_user.id if current_user.is_authenticated else None,
        bikelane.id
    )
    if new_photos:
        existing_photos.extend(new_photos)
        bikelane.set_photos_list(existing_photos)


def _infrastructure_edit_endpoint(point):
    if point.infrastructure_type == InfrastructurePoint.TYPE_BICYCLE_PARKING:
        return 'main.edit_parking'
    return 'main.edit_repair'


def _save_infrastructure_uploaded_photos(point):
    existing_photos = point.get_photos_list()
    available_slots = max(
        0,
        current_app.config['MAX_PHOTOS_PER_BIKELANE'] - len(existing_photos),
    )
    uploaded_files = [
        file
        for file in request.files.getlist('photos')
        if file and file.filename
    ][:available_slots]
    if not uploaded_files:
        return

    existing_photos.extend(
        FileHandler.save_infrastructure_photos(uploaded_files, point.id)
    )
    point.set_photos_list(existing_photos)


def _infrastructure_type_from_add_type(add_type):
    return {
        'parking': InfrastructurePoint.TYPE_BICYCLE_PARKING,
        'repair': InfrastructurePoint.TYPE_REPAIR_STATION,
    }.get(add_type)


def _new_infrastructure_point(add_type, city=None):
    infrastructure_type = _infrastructure_type_from_add_type(add_type)
    if not infrastructure_type:
        raise ValueError('Недопустимый тип объекта инфраструктуры.')

    latitude = city.coords_lat if city else 43.238949
    longitude = city.coords_lng if city else 76.889709
    amenity = (
        'bicycle_parking'
        if infrastructure_type == InfrastructurePoint.TYPE_BICYCLE_PARKING
        else 'bicycle_repair_station'
    )
    return InfrastructurePoint(
        city_id=city.id if city else None,
        infrastructure_type=infrastructure_type,
        title='',
        description='',
        photos='[]',
        latitude=latitude,
        longitude=longitude,
        source='user',
        osm_type='node',
        osm_id=f'user-{uuid.uuid4().hex}',
        osm_tags=json.dumps({'amenity': amenity}),
    )


def _render_add_infrastructure(add_type, preselected_city=''):
    city = City.query.filter_by(
        city_id=preselected_city,
        status='active',
    ).first()
    point = _new_infrastructure_point(add_type, city)
    return render_template(
        'admin/edit_infrastructure.html',
        point=point,
        city=city,
        cities_data=_get_active_cities_data(),
        selected_city_value=preselected_city if city else '',
        form_fields=infrastructure_form_fields(point),
        form_action=url_for('main.add_bikelane', type=add_type),
        is_create_mode=True,
        add_object_type=add_type,
    )


def _create_infrastructure_point(add_type):
    city_slug = request.form.get('city', '').strip()
    city = City.query.filter_by(city_id=city_slug, status='active').first()
    if not city:
        flash('Необходимо выбрать город.', 'error')
        return redirect(url_for(
            'main.add_bikelane',
            type=add_type,
            city=city_slug,
        ))

    point = _new_infrastructure_point(add_type, city)
    try:
        apply_infrastructure_form(point, request.form)
        db.session.add(point)
        db.session.flush()
        _save_infrastructure_uploaded_photos(point)
        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        flash(str(error), 'error')
        return redirect(url_for(
            'main.add_bikelane',
            type=add_type,
            city=city.city_id,
        ))
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            'Не удалось добавить объект инфраструктуры типа %s',
            point.infrastructure_type,
        )
        flash('Не удалось добавить объект инфраструктуры.', 'error')
        return redirect(url_for(
            'main.add_bikelane',
            type=add_type,
            city=city.city_id,
        ))

    flash(f'{point.type_display} добавлена.', 'success')
    return redirect(url_for('public.city', city_id=city.city_id))


def _edit_infrastructure_point(infrastructure_id, expected_type):
    point = InfrastructurePoint.query.filter_by(
        id=infrastructure_id,
        infrastructure_type=expected_type,
    ).first_or_404()
    endpoint = _infrastructure_edit_endpoint(point)

    if request.method == 'POST':
        try:
            apply_infrastructure_form(point, request.form)
            _save_infrastructure_uploaded_photos(point)
            db.session.commit()
        except ValueError as error:
            db.session.rollback()
            flash(str(error), 'error')
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                'Не удалось обновить объект инфраструктуры id=%s',
                point.id,
            )
            flash('Не удалось сохранить изменения.', 'error')
        else:
            flash(f'{point.type_display} обновлена и опубликована.', 'success')

        return redirect(url_for(endpoint, infrastructure_id=point.id))

    return render_template(
        'admin/edit_infrastructure.html',
        point=point,
        city=db.session.get(City, point.city_id),
        form_fields=infrastructure_form_fields(point),
        form_action=url_for(endpoint, infrastructure_id=point.id),
    )


def _country_sort_key(country_name):
    normalized = unicodedata.normalize(
        'NFKC',
        str(country_name or ''),
    ).casefold()
    first_letter_index = next(
        (
            index
            for index, character in enumerate(normalized)
            if character.isalnum()
        ),
        len(normalized),
    )
    return normalized[first_letter_index:].strip(), normalized


@bp.route('/')
def index():
    """Главная страница"""
    from collections import defaultdict
    
    # Получаем все активные города
    cities = City.query.filter_by(status='active').order_by(City.name).all()
    
    # Группируем города по странам
    cities_dict = defaultdict(list)
    for city in cities:
        cities_dict[city.country].append(city)
    
    # Преобразуем в список кортежей (страна, список городов)
    cities_by_country = sorted(
        cities_dict.items(),
        key=lambda item: _country_sort_key(item[0]),
    )
    
    return render_template('index.html', cities_by_country=cities_by_country)


@bp.route('/city-requests', methods=['POST'])
def create_city_request():
    """Сохранить заявку посетителя на добавление города."""
    city_name = request.form.get('city_name', '').strip()
    if not city_name:
        flash('Напишите название города', 'error')
        return redirect(url_for('main.index'))
    if len(city_name) > 120:
        flash('Название города должно быть короче 120 символов', 'error')
        return redirect(url_for('main.index'))

    city_request = CityRequest(
        city_name=city_name,
        user_id=current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(city_request)
    db.session.commit()

    flash('Спасибо! Заявка отправлена.', 'success')
    return redirect(url_for('main.index'))


def _normalize_location_city_name(value):
    normalized = unicodedata.normalize('NFKC', str(value or '')).casefold()
    normalized = re.sub(r'[^\w]+', ' ', normalized, flags=re.UNICODE).strip()
    if normalized.startswith('город '):
        normalized = normalized[6:].strip()
    return normalized


def _find_location_city(city_names):
    normalized_names = {
        _normalize_location_city_name(name)
        for name in city_names
        if _normalize_location_city_name(name)
    }
    if not normalized_names:
        return None

    for city in City.query.filter_by(status='active').all():
        aliases = {
            _normalize_location_city_name(city.name),
            _normalize_location_city_name(city.city_id),
        }
        if normalized_names & aliases:
            return city
    return None


@bp.route('/api/location/city', methods=['POST'])
def resolve_location_city():
    """Сопоставить геолокацию с городом и сохранить неудачную локацию."""
    payload = request.get_json(silent=True) or {}
    try:
        latitude = float(payload.get('latitude'))
        longitude = float(payload.get('longitude'))
    except (TypeError, ValueError):
        return jsonify({
            'success': False,
            'message': 'Не удалось получить координаты.',
        }), 400

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return jsonify({
            'success': False,
            'message': 'Получены некорректные координаты.',
        }), 400

    raw_city_names = payload.get('city_names') or []
    if isinstance(raw_city_names, str):
        raw_city_names = [raw_city_names]
    if not isinstance(raw_city_names, list):
        raw_city_names = []

    city_names = []
    for value in raw_city_names:
        city_name = str(value or '').strip()
        if city_name and city_name not in city_names:
            city_names.append(city_name[:120])

    city = _find_location_city(city_names)
    if city:
        return jsonify({
            'success': True,
            'available': True,
            'city': {
                'id': city.city_id,
                'name': city.name,
            },
            'redirect_url': url_for('public.city', city_id=city.city_id),
        })

    detected_city_name = city_names[0] if city_names else 'Неизвестный город'
    city_request = CityRequest(
        city_name=detected_city_name,
        user_id=current_user.id if current_user.is_authenticated else None,
        location_fail=True,
        latitude=latitude,
        longitude=longitude,
    )
    db.session.add(city_request)
    db.session.commit()

    return jsonify({
        'success': True,
        'available': False,
        'city_name': detected_city_name,
        'message': 'Этого города пока нет на сайте.',
    })


@bp.route('/healthz')
def healthz():
    """Простой health-check для nginx/systemd/deploy."""
    return jsonify({
        'status': 'ok',
        'app_env': current_app.config.get('APP_ENV', 'development'),
        'version': current_app.config.get('APP_VERSION'),
    }), 200

@bp.route('/add-bikelane', methods=['GET', 'POST'])
def add_bikelane():
    """Страница добавления велодорожки"""
    add_type = request.args.get('type', 'bikelane').strip().lower()
    if add_type not in ('bikelane', 'parking', 'repair'):
        add_type = 'bikelane'

    if request.method == 'GET':
        preselected_city = request.args.get('city', '').strip()
        if add_type in ('parking', 'repair'):
            return _render_add_infrastructure(add_type, preselected_city)

        is_admin_create_mode = (
            current_user.is_authenticated
            and getattr(current_user, 'is_admin', False)
        )
        return render_template(
            'add_bikelane.html',
            preselected_city=preselected_city,
            is_admin_create_mode=is_admin_create_mode,
            cities_data=_get_active_cities_data(),
            reward_config=_get_bikelane_reward_config(),
            description_min_length=20,
            add_object_type='bikelane',
        )

    submitted_object_type = request.form.get('object_type', '').strip().lower()
    if submitted_object_type in ('parking', 'repair'):
        return _create_infrastructure_point(submitted_object_type)

    try:
        if not request.form and not request.files:
            current_app.logger.warning(
                'Пустой POST на /add-bikelane: content_type=%s, content_length=%s',
                request.content_type,
                request.content_length
            )
            return jsonify({
                'success': False,
                'error': 'Пустой запрос. Форма не была передана на сервер.'
            }), 400

        form_data = _extract_bikelane_form_data()
        errors, distance_value = _validate_bikelane_form_data(form_data)

        if errors:
            return jsonify({
                'success': False,
                'error': 'Ошибки валидации: ' + '; '.join(errors)
            })

        bikelane = BikeLane(
            status='pending',
            user_id=current_user.id if current_user.is_authenticated else None
        )
        _apply_bikelane_form_data(bikelane, form_data, distance_value=distance_value)
        db.session.add(bikelane)
        db.session.flush()
        _save_bikelane_uploaded_photos(bikelane)
        is_admin_submission = (
            current_user.is_authenticated
            and getattr(current_user, 'is_admin', False)
        )
        if is_admin_submission:
            bikelane.approve(current_user)
        db.session.commit()

        current_app.logger.info(
            f'Велодорожка создана: ID={bikelane.id}, title={bikelane.title}, distance={getattr(bikelane, "distance", None)}м'
        )

        return jsonify({
            'success': True,
            'message': (
                'Велодорожка опубликована!'
                if is_admin_submission
                else 'Велодорожка успешно добавлена!'
            ),
            'bikelane_id': bikelane.id,
            'title': form_data['title'],
            'city': form_data['city'],
            'distance': f'{bikelane.distance:.1f} м' if getattr(bikelane, 'distance', None) else None
        })
    except ValueError as error:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(error)
        })
    except Exception as error:
        db.session.rollback()
        current_app.logger.error(f'Ошибка при сохранении велодорожки: {error}')
        return jsonify({
            'success': False,
            'error': f'Ошибка сервера: {str(error)}'
        })


@bp.route('/edit-bikelane/<int:bikelane_id>', methods=['GET', 'POST'])
@login_required
def edit_bikelane(bikelane_id):
    """Редактирование велодорожки пользователем"""
    bikelane = BikeLane.query.get_or_404(bikelane_id)

    if bikelane.user_id != current_user.id and not getattr(current_user, 'is_admin', False):
        if request.method == 'GET':
            flash('У вас нет доступа к редактированию этой велодорожки', 'error')
            return redirect(url_for('auth.my_bikelanes'))
        return jsonify({
            'success': False,
            'error': 'У вас нет доступа к редактированию этой велодорожки'
        }), 403

    if request.method == 'GET':
        is_admin_edit = getattr(current_user, 'is_admin', False)
        return render_template(
            'add_bikelane.html',
            form_data=_build_bikelane_form_context(bikelane),
            is_edit_mode=True,
            is_admin_edit_mode=is_admin_edit,
            form_action=url_for('main.edit_bikelane', bikelane_id=bikelane.id),
            admin_delete_url=(
                url_for('admin.delete_bikelane', bikelane_id=bikelane.id)
                if getattr(current_user, 'is_admin', False)
                else None
            ),
            cities_data=_get_active_cities_data(),
            reward_config=_get_bikelane_reward_config(),
            description_min_length=20,
        )

    try:
        is_admin_edit = getattr(current_user, 'is_admin', False)
        form_data = _extract_bikelane_form_data()
        errors, distance_value = _validate_bikelane_form_data(form_data)

        if errors:
            return jsonify({
                'success': False,
                'error': 'Ошибки валидации: ' + '; '.join(errors)
            })

        _apply_bikelane_form_data(
            bikelane,
            form_data,
            distance_value=distance_value,
            reset_moderation=not is_admin_edit,
        )
        _save_bikelane_uploaded_photos(bikelane)
        if is_admin_edit:
            bikelane.approve(current_user)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': (
                'Изменения опубликованы'
                if is_admin_edit
                else 'Изменения отправлены на модерацию'
            ),
            'modal_title': (
                'Изменения опубликованы'
                if is_admin_edit
                else 'Изменения отправлены'
            ),
            'modal_message': (
                'Изменения сохранены и сразу опубликованы.'
                if is_admin_edit
                else 'Обновленная велодорожка отправлена в админку и будет повторно проверена модераторами.'
            ),
            'primary_action_label': (
                'К велодорожке'
                if is_admin_edit
                else 'К моим велодорожкам'
            ),
            'close_action_label': 'Закрыть',
            'redirect_url': (
                url_for('admin.view_bikelane', bikelane_id=bikelane.id)
                if is_admin_edit
                else url_for('auth.my_bikelanes')
            ),
            'bikelane_id': bikelane.id
        })
    except ValueError as error:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(error)
        })
    except Exception as error:
        db.session.rollback()
        current_app.logger.error(f'Ошибка при обновлении велодорожки {bikelane_id}: {error}')
        return jsonify({
            'success': False,
            'error': f'Ошибка сервера: {str(error)}'
        })


@bp.route('/edit-parking/<int:infrastructure_id>', methods=['GET', 'POST'])
@login_required
def edit_parking(infrastructure_id):
    if not getattr(current_user, 'is_admin', False):
        return redirect(url_for('main.index'))
    return _edit_infrastructure_point(
        infrastructure_id,
        InfrastructurePoint.TYPE_BICYCLE_PARKING,
    )


@bp.route('/edit-repair/<int:infrastructure_id>', methods=['GET', 'POST'])
@login_required
def edit_repair(infrastructure_id):
    if not getattr(current_user, 'is_admin', False):
        return redirect(url_for('main.index'))
    return _edit_infrastructure_point(
        infrastructure_id,
        InfrastructurePoint.TYPE_REPAIR_STATION,
    )

@bp.route('/api/validate-geometry', methods=['POST'])
def validate_geometry():
    """API для валидации геометрии"""
    try:
        data = request.get_json()
        geometry = data.get('geometry', '')
        
        # Используем BikeLaneValidator если он есть
        if hasattr(BikeLaneValidator, 'validate_geometry'):
            errors = BikeLaneValidator.validate_geometry(geometry)
        else:
            # Простая валидация геометрии
            errors = []
            if not geometry:
                errors.append('Геометрия не может быть пустой')
            else:
                try:
                    geometry_data = json.loads(geometry)
                    if geometry_data.get('type') != 'LineString':
                        errors.append('Геометрия должна быть типа LineString')
                    elif (not geometry_data.get('coordinates') or 
                          len(geometry_data.get('coordinates', [])) < 2):
                        errors.append('Линия должна содержать минимум 2 точки')
                    else:
                        # Проверяем дистанцию
                        coordinates = geometry_data.get('coordinates', [])
                        # Простой расчет дистанции для валидации
                        if len(coordinates) >= 2:
                            try:
                                # Создаем временный объект для расчета дистанции

                                temp_bikelane = BikeLane()
                                temp_bikelane.geometry = geometry
                                distance = temp_bikelane.calculate_distance()
                                
                                if distance and distance < 10:
                                    errors.append('Велодорожка должна быть длиннее 10 метров')
                                elif distance and distance > 50000:
                                    errors.append('Велодорожка не может быть длиннее 50 километров')
                            except Exception:
                                # Если не удалось рассчитать дистанцию, пропускаем проверку
                                pass
                                
                except (json.JSONDecodeError, TypeError):
                    errors.append('Некорректный формат геометрии')
        
        return jsonify({
            'valid': len(errors) == 0,
            'errors': errors
        })
        
    except Exception as e:
        current_app.logger.error(f"Ошибка валидации геометрии: {e}")
        return jsonify({
            'valid': False,
            'errors': ['Ошибка при валидации геометрии']
        }), 400

@bp.route('/@<nickname>')
def user_profile(nickname):
    """Профиль пользователя по никнейму"""
    from app.models.user import User
    from app.models.bikelane import BikeLane
    from flask_login import current_user
    
    user = User.query.filter_by(nickname=nickname).first_or_404()
    
    # Получаем велодорожки пользователя
    bikelanes = BikeLane.query.filter_by(user_id=user.id).order_by(BikeLane.created_at.desc()).all()
    
    # Статистика
    total_bikelanes = len(bikelanes)
    pending_count = sum(1 for bl in bikelanes if bl.status == 'pending')
    approved_count = sum(1 for bl in bikelanes if bl.status == 'approved')
    rejected_count = sum(1 for bl in bikelanes if bl.status == 'rejected')
    
    stats = {
        'total': total_bikelanes,
        'pending': pending_count,
        'approved': approved_count,
        'rejected': rejected_count,
        'score': user.get_total_score()
    }
    
    # Проверяем, это свой профиль или чужой
    is_own_profile = current_user.is_authenticated and current_user.id == user.id
    
    return render_template('auth/profile.html', 
                         user=user,
                         bikelanes=bikelanes,
                         stats=stats,
                         is_own_profile=is_own_profile)
