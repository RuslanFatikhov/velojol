from flask_login import current_user, login_required
# app/routes/main.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from sqlalchemy.exc import IntegrityError
from app import db
from app.models.bikelane import BikeLane
from app.models.banner_response import BannerResponse
from app.models.city import City
from app.utils.validators import BikeLaneValidator
from app.utils.file_handler import FileHandler
import json
import uuid

# Создаем Blueprint
bp = Blueprint('main', __name__)

BANNER_BUS_LANES_KEY = 'bus_lanes'
BANNER_COOKIE_NAME = 'velojol_banner_id'
BANNER_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
BANNER_ALLOWED_ANSWERS = {'yes', 'no'}


def _get_active_cities_data():
    cities = City.query.filter_by(status='active').order_by(City.name).all()
    return {'cities': [city.to_dict() for city in cities]}


def _get_bikelane_reward_config():
    return BikeLane.get_reward_config()


def _get_banner_cookie_id():
    return request.cookies.get(BANNER_COOKIE_NAME, '').strip()


def _build_banner_cookie_id():
    return uuid.uuid4().hex


def _find_banner_response(banner_key, cookie_id=None):
    query = BannerResponse.query.filter_by(banner_key=banner_key)

    if current_user.is_authenticated:
        return query.filter_by(user_id=current_user.id).first()

    if cookie_id:
        return query.filter_by(cookie_id=cookie_id).first()

    return None


def _set_banner_cookie(response, cookie_id):
    response.set_cookie(
        BANNER_COOKIE_NAME,
        cookie_id,
        max_age=BANNER_COOKIE_MAX_AGE,
        httponly=True,
        samesite='Lax',
        secure=current_app.config.get('SESSION_COOKIE_SECURE', False)
    )
    return response


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
        'overall_quality': request.form.get('overall_quality', ''),
        'geometry': request.form.get('geometry', ''),
        'distance': request.form.get('distance', ''),
        'video_url': request.form.get('video_url', '').strip(),
    }


def _validate_bikelane_form_data(form_data):
    errors = []

    if not form_data['city']:
        errors.append('Необходимо выбрать город')

    if len(form_data['title']) < 3:
        errors.append('Название должно содержать минимум 3 символа')

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

    allowed_track_types = ['lane', 'bollards', 'separated', 'shared']
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
    bikelane.quality = int(form_data['quality']) if form_data['quality'] else 0
    bikelane.has_parking = form_data['has_parking']
    bikelane.has_markings = form_data['has_markings']
    bikelane.has_signs = form_data['has_signs']
    bikelane.geometry = form_data['geometry']

    if distance_value is not None:
        bikelane.distance = distance_value
    else:
        bikelane.distance = bikelane.calculate_length() * 1000

    if form_data['overall_quality']:
        try:
            bikelane.overall_quality = int(form_data['overall_quality'])
        except (ValueError, TypeError):
            bikelane.overall_quality = bikelane.calculate_overall_quality()
    else:
        bikelane.overall_quality = bikelane.calculate_overall_quality()
    bikelane.set_photos_list(bikelane.get_photos_list())

    if form_data['video_url']:
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
    cities_by_country = sorted(cities_dict.items(), key=lambda item: item[0].casefold())
    
    return render_template('index.html', cities_by_country=cities_by_country)


@bp.route('/api/banner/bus-lanes', methods=['GET'])
def get_bus_lanes_banner():
    """Проверить, нужно ли показывать баннер про автобусные полосы."""
    cookie_id = _get_banner_cookie_id()
    response = _find_banner_response(BANNER_BUS_LANES_KEY, cookie_id=cookie_id)
    return jsonify({'show': response is None})


@bp.route('/api/banner/bus-lanes', methods=['POST'])
def submit_bus_lanes_banner():
    """Сохранить ответ на баннер про автобусные полосы."""
    payload = request.get_json(silent=True) or {}
    answer = payload.get('answer')

    if answer not in BANNER_ALLOWED_ANSWERS:
        return jsonify({'ok': False, 'error': 'Недопустимый ответ'}), 400

    cookie_id = _get_banner_cookie_id()
    if not current_user.is_authenticated and not cookie_id:
        cookie_id = _build_banner_cookie_id()

    existing_response = _find_banner_response(BANNER_BUS_LANES_KEY, cookie_id=cookie_id)
    api_response = jsonify({'ok': True})

    if existing_response:
        if not current_user.is_authenticated and cookie_id:
            _set_banner_cookie(api_response, cookie_id)
        return api_response

    banner_response = BannerResponse(
        banner_key=BANNER_BUS_LANES_KEY,
        user_id=current_user.id if current_user.is_authenticated else None,
        cookie_id=None if current_user.is_authenticated else cookie_id,
        answer=answer
    )

    db.session.add(banner_response)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()

    if not current_user.is_authenticated and cookie_id:
        _set_banner_cookie(api_response, cookie_id)

    return api_response


@bp.route('/healthz')
def healthz():
    """Простой health-check для nginx/systemd/deploy."""
    return jsonify({
        'status': 'ok',
        'app_env': current_app.config.get('APP_ENV', 'development')
    }), 200

@bp.route('/add-bikelane', methods=['GET', 'POST'])
def add_bikelane():
    """Страница добавления велодорожки"""
    if request.method == 'GET':
        preselected_city = request.args.get('city', '').strip()
        return render_template(
            'add_bikelane.html',
            preselected_city=preselected_city,
            cities_data=_get_active_cities_data(),
            reward_config=_get_bikelane_reward_config()
        )

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
        db.session.commit()

        current_app.logger.info(
            f'Велодорожка создана: ID={bikelane.id}, title={bikelane.title}, distance={getattr(bikelane, "distance", None)}м'
        )

        return jsonify({
            'success': True,
            'message': 'Велодорожка успешно добавлена!',
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
        return render_template(
            'add_bikelane.html',
            form_data=_build_bikelane_form_context(bikelane),
            is_edit_mode=True,
            form_action=url_for('main.edit_bikelane', bikelane_id=bikelane.id),
            cities_data=_get_active_cities_data(),
            reward_config=_get_bikelane_reward_config()
        )

    try:
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
            reset_moderation=True
        )
        _save_bikelane_uploaded_photos(bikelane)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Изменения отправлены на модерацию',
            'modal_title': 'Изменения отправлены',
            'modal_message': 'Обновленная велодорожка отправлена в админку и будет повторно проверена модераторами.',
            'primary_action_label': 'К моим велодорожкам',
            'close_action_label': 'Закрыть',
            'redirect_url': url_for('auth.my_bikelanes'),
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
