import json
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.bikelane import BikeLane
from app.models.city import City


OSM_SOURCE = 'openstreetmap'
DEFAULT_OVERPASS_URL = 'https://overpass-api.de/api/interpreter'
DEFAULT_TIMEOUT = 25
DEFAULT_RADIUS_KM = 8
MIN_LENGTH_METERS = 30
MAX_IMPORT_LIMIT = 50

OSM_FILTERS = (
    ('highway', 'cycleway'),
    ('cycleway', 'lane'),
    ('cycleway', 'track'),
    ('cycleway:right', None),
    ('cycleway:left', None),
    ('bicycle', 'designated'),
    ('segregated', 'yes'),
)

TAG_KEYS_FOR_DESCRIPTION = (
    'name',
    'highway',
    'cycleway',
    'cycleway:right',
    'cycleway:left',
    'bicycle',
    'foot',
    'segregated',
    'surface',
)


class OsmImportError(RuntimeError):
    """Ошибка импорта из OpenStreetMap."""


@dataclass
class OsmCandidate:
    osm_type: str
    osm_id: str
    tags: dict
    geometry: dict
    length_meters: float

    @property
    def key(self):
        return self.osm_type, self.osm_id


def preview_osm_bikelanes(city_id, limit=10, fetcher=None):
    """Dry-run импорта без записи в базу."""
    city = _find_city(city_id)
    candidates, errors = _load_candidates(city, limit, fetcher=fetcher)
    existing_keys = _existing_osm_keys(candidates)
    importable = [candidate for candidate in candidates if candidate.key not in existing_keys]

    return {
        'city': city,
        'found': len(candidates),
        'existing': len(candidates) - len(importable),
        'importable': len(importable),
        'errors': errors,
        'candidates': candidates,
    }


def import_osm_bikelanes(city_id, limit=10, approve=False, approved_by=None, fetcher=None):
    """Импортировать OSM-велодорожки в базу, по одному объекту за раз."""
    city = _find_city(city_id)
    candidates, errors = _load_candidates(city, limit, fetcher=fetcher)
    existing_keys = _existing_osm_keys(candidates)

    imported = 0
    duplicates = 0
    imported_bikelanes = []

    for candidate in candidates:
        if imported >= _normalize_limit(limit):
            break

        if candidate.key in existing_keys:
            duplicates += 1
            continue

        bikelane = _build_bikelane(candidate, city, approve=approve, approved_by=approved_by)
        db.session.add(bikelane)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            duplicates += 1
            existing_keys.add(candidate.key)
            continue
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception(
                'Не удалось импортировать OSM %s/%s',
                candidate.osm_type,
                candidate.osm_id
            )
            errors.append(f'{candidate.osm_type}/{candidate.osm_id}: {exc}')
            continue

        imported += 1
        imported_bikelanes.append(bikelane)
        existing_keys.add(candidate.key)

    return {
        'city': city,
        'found': len(candidates),
        'imported': imported,
        'duplicates': duplicates,
        'errors': errors,
        'bikelanes': imported_bikelanes,
    }


def map_osm_tags_to_track_type(tags):
    """Классификация тегов OSM в тип дорожки Velojol."""
    if tags.get('highway') == 'cycleway' or tags.get('cycleway') == 'track':
        return 'separated'
    if tags.get('cycleway') == 'lane':
        return 'lane'
    if tags.get('segregated') == 'yes':
        return 'shared'
    if tags.get('foot') == 'designated' and tags.get('bicycle') == 'designated':
        return 'shared'
    return 'shared'


def _find_city(city_id):
    city = None
    if isinstance(city_id, int) or str(city_id).isdigit():
        city = City.query.get(int(city_id))
    if city is None:
        city = City.query.filter_by(city_id=str(city_id)).first()
    if city is None:
        raise OsmImportError('Город не найден')
    return city


def _load_candidates(city, limit, fetcher=None):
    limit = _normalize_limit(limit)
    errors = []

    try:
        payload = _fetch_overpass(city, limit, fetcher=fetcher)
    except OsmImportError:
        raise
    except Exception as exc:
        current_app.logger.exception('Не удалось получить данные Overpass для city_id=%s', city.city_id)
        raise OsmImportError(f'Overpass недоступен: {exc}') from exc

    candidates = []
    seen = set()
    for element in payload.get('elements', []):
        if len(candidates) >= limit:
            break

        candidate, error = _candidate_from_element(element)
        if error:
            errors.append(error)
            continue
        if candidate.key in seen:
            continue
        seen.add(candidate.key)
        candidates.append(candidate)

    return candidates, errors


def _fetch_overpass(city, limit, fetcher=None):
    bbox = _bbox_for_city(city)
    timeout = current_app.config.get('OSM_OVERPASS_TIMEOUT', DEFAULT_TIMEOUT)
    query = _build_overpass_query(bbox, limit, timeout=timeout)

    if fetcher is not None:
        return fetcher(query)

    overpass_url = current_app.config.get('OSM_OVERPASS_URL', DEFAULT_OVERPASS_URL)
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    request = urllib.request.Request(
        overpass_url,
        data=data,
        headers={'User-Agent': 'Velojol OSM importer MVP'}
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        current_app.logger.exception('Overpass API недоступен')
        raise OsmImportError(f'Overpass недоступен: {exc}') from exc


def _build_overpass_query(bbox, limit, timeout=DEFAULT_TIMEOUT):
    south, west, north, east = bbox
    bbox_text = f'{south:.6f},{west:.6f},{north:.6f},{east:.6f}'
    selectors = []

    for osm_type in ('way', 'relation'):
        for key, value in OSM_FILTERS:
            if value is None:
                selectors.append(f'{osm_type}["{key}"]({bbox_text});')
            else:
                selectors.append(f'{osm_type}["{key}"="{value}"]({bbox_text});')

    overpass_limit = min(MAX_IMPORT_LIMIT * 5, max(limit * 5, limit))
    return (
        f'[out:json][timeout:{int(timeout)}];\n'
        '(\n'
        + '\n'.join(selectors)
        + '\n);\n'
        f'out geom {overpass_limit};'
    )


def _bbox_for_city(city):
    radius_km = current_app.config.get('OSM_IMPORT_RADIUS_KM', DEFAULT_RADIUS_KM)
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * max(math.cos(math.radians(city.coords_lat)), 0.2))
    return (
        city.coords_lat - lat_delta,
        city.coords_lng - lng_delta,
        city.coords_lat + lat_delta,
        city.coords_lng + lng_delta,
    )


def _candidate_from_element(element):
    osm_type = element.get('type')
    osm_id = element.get('id')
    tags = element.get('tags') or {}

    if osm_type not in {'way', 'relation'} or osm_id is None:
        return None, 'OSM-элемент без type/id пропущен'

    coordinates = _extract_line_coordinates(element)
    if len(coordinates) < 2:
        return None, f'{osm_type}/{osm_id}: нет валидной линии'

    length_meters = _line_length_meters(coordinates)
    if length_meters < MIN_LENGTH_METERS:
        return None, f'{osm_type}/{osm_id}: линия короче {MIN_LENGTH_METERS} м'

    return OsmCandidate(
        osm_type=osm_type,
        osm_id=str(osm_id),
        tags=tags,
        geometry={
            'type': 'LineString',
            'coordinates': coordinates,
        },
        length_meters=length_meters,
    ), None


def _extract_line_coordinates(element):
    if element.get('type') == 'way':
        return _geometry_to_coordinates(element.get('geometry') or [])

    member_lines = []
    for member in element.get('members') or []:
        if member.get('type') != 'way':
            continue
        line = _geometry_to_coordinates(member.get('geometry') or [])
        if len(line) >= 2:
            member_lines.append(line)

    if not member_lines:
        return []
    return max(member_lines, key=_line_length_meters)


def _geometry_to_coordinates(points):
    coordinates = []
    previous = None

    for point in points:
        try:
            lat = float(point['lat'])
            lon = float(point['lon'])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(lat) or not math.isfinite(lon):
            continue

        coordinate = [lon, lat]
        if coordinate != previous:
            coordinates.append(coordinate)
            previous = coordinate

    return coordinates


def _line_length_meters(coordinates):
    total = 0
    for start, end in zip(coordinates, coordinates[1:]):
        total += _haversine_meters(start[1], start[0], end[1], end[0])
    return total


def _haversine_meters(lat1, lon1, lat2, lon2):
    radius = 6371000
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _existing_osm_keys(candidates):
    keys = {(candidate.osm_type, candidate.osm_id) for candidate in candidates}
    if not keys:
        return set()

    existing = BikeLane.query.filter(
        BikeLane.source == OSM_SOURCE,
        BikeLane.osm_type.in_([key[0] for key in keys]),
        BikeLane.osm_id.in_([key[1] for key in keys]),
    ).all()
    return {(item.osm_type, item.osm_id) for item in existing}


def _build_bikelane(candidate, city, approve=False, approved_by=None):
    now = datetime.utcnow()
    title = candidate.tags.get('name') or f'Велодорожка OSM {candidate.osm_type}/{candidate.osm_id}'
    bikelane = BikeLane(
        title=title[:200],
        description=_build_description(candidate),
        city_id=city.id,
        city=city.city_id,
        geometry=json.dumps(candidate.geometry, ensure_ascii=False),
        track_type=map_osm_tags_to_track_type(candidate.tags),
        quality=_map_quality(candidate.tags),
        has_parking=False,
        has_markings=_truthy_tag(candidate.tags.get('cycleway:marking')),
        has_signs=False,
        photos='[]',
        videos='[]',
        status='approved' if approve else 'pending',
        source=OSM_SOURCE,
        osm_type=candidate.osm_type,
        osm_id=candidate.osm_id,
        osm_tags=json.dumps(candidate.tags, ensure_ascii=False, sort_keys=True),
        imported_at=now,
        created_at=now,
        updated_at=now,
    )
    bikelane.overall_quality = bikelane.calculate_overall_quality()

    if approve and approved_by is not None:
        bikelane.moderated_at = now
        bikelane.moderated_by = approved_by.id
        bikelane.score = bikelane.calculate_score()

    return bikelane


def _build_description(candidate):
    tag_parts = [
        f'{key}={candidate.tags[key]}'
        for key in TAG_KEYS_FOR_DESCRIPTION
        if candidate.tags.get(key)
    ]
    tags_text = ', '.join(tag_parts[:8]) if tag_parts else 'ключевые теги отсутствуют'
    return (
        'Объект импортирован из OpenStreetMap. '
        f'OSM: {candidate.osm_type}/{candidate.osm_id}. '
        f'Теги: {tags_text}. '
        'Атрибуция: © OpenStreetMap contributors.'
    )


def _map_quality(tags):
    surface = (tags.get('surface') or '').lower()
    if surface in {'asphalt', 'concrete', 'paved'}:
        return 4
    if surface in {'paving_stones', 'sett', 'compacted'}:
        return 3
    if surface in {'gravel', 'fine_gravel', 'ground', 'dirt', 'earth', 'unpaved'}:
        return 2
    return 3


def _truthy_tag(value):
    return str(value).lower() in {'yes', 'true', '1'}


def _normalize_limit(limit):
    try:
        normalized = int(limit)
    except (TypeError, ValueError):
        normalized = 10
    return max(1, min(MAX_IMPORT_LIMIT, normalized))
