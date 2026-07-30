import json
import math
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.bikelane import BikeLane
from app.models.city import City
from app.models.infrastructure_point import InfrastructurePoint


OSM_SOURCE = 'openstreetmap'
DEFAULT_OVERPASS_URL = 'https://overpass-api.de/api/interpreter'
DEFAULT_TIMEOUT = 25
DEFAULT_IMPORT_LIMIT = 100
MIN_LENGTH_METERS = 10
MAX_IMPORT_LIMIT = 1000
MAX_OVERPASS_RESULTS = 1000
EXCLUDED_CYCLEWAY_TAGS = (
    'cycleway',
    'cycleway:right',
    'cycleway:both',
    'cycleway:left',
)
EXCLUDED_CYCLEWAY_VALUES = {'no', 'separate'}

OSM_FILTERS = (
    ('highway', 'cycleway'),
    ('cycleway', 'lane'),
    ('cycleway', 'track'),
    ('cycleway:right', None),
    ('cycleway:left', None),
    ('bicycle', 'designated'),
    ('segregated', 'yes'),
)
OSM_BUS_LANE_FILTERS = (
    ('highway', 'busway'),
    ('lanes:bus', None),
    ('lanes:bus:forward', None),
    ('lanes:bus:backward', None),
    ('lanes:psv', None),
    ('lanes:psv:forward', None),
    ('lanes:psv:backward', None),
    ('bus:lanes', None),
    ('bus:lanes:forward', None),
    ('bus:lanes:backward', None),
    ('psv:lanes', None),
    ('psv:lanes:forward', None),
    ('psv:lanes:backward', None),
    ('busway', None),
    ('busway:left', None),
    ('busway:right', None),
)
OSM_INFRASTRUCTURE_AMENITIES = {
    'bicycle_parking': InfrastructurePoint.TYPE_BICYCLE_PARKING,
    'bicycle_repair_station': InfrastructurePoint.TYPE_REPAIR_STATION,
}

class OsmImportError(RuntimeError):
    """Ошибка импорта из OpenStreetMap."""


@dataclass
class OsmCandidate:
    osm_type: str
    osm_id: str
    tags: dict
    geometry: dict
    length_meters: float
    track_type: str
    member_keys: tuple = ()

    @property
    def key(self):
        return self.osm_type, self.osm_id

    @property
    def source_keys(self):
        return self.member_keys or (self.key,)


@dataclass
class OsmInfrastructureCandidate:
    osm_type: str
    osm_id: str
    infrastructure_type: str
    tags: dict
    latitude: float
    longitude: float

    @property
    def key(self):
        return self.osm_type, self.osm_id


def preview_osm_bikelanes(
    city_id,
    limit=DEFAULT_IMPORT_LIMIT,
    fetcher=None,
    include_bikelanes=True,
    include_bus_lanes=True,
):
    """Dry-run импорта без записи в базу."""
    city = _find_city(city_id)
    candidates, errors = _load_candidates(
        city,
        limit,
        fetcher=fetcher,
        include_bikelanes=include_bikelanes,
        include_bus_lanes=include_bus_lanes,
    )
    existing_keys = _existing_osm_keys(candidates)
    candidates = _merge_connected_candidates(candidates, existing_keys)
    importable = [
        candidate for candidate in candidates
        if not _candidate_exists(candidate, existing_keys)
    ]
    bus_candidates = [
        candidate for candidate in candidates
        if candidate.track_type == 'bus_lane'
    ]
    limited_importable = importable[:_normalize_limit(limit)]
    importable_bus_candidates = [
        candidate for candidate in limited_importable
        if candidate.track_type == 'bus_lane'
    ]

    return {
        'city': city,
        'found': len(candidates),
        'existing': len(candidates) - len(importable),
        'importable': len(limited_importable),
        'bus_lanes_found': len(bus_candidates),
        'bus_lanes_importable': len(importable_bus_candidates),
        'errors': errors,
        'candidates': candidates,
    }


def import_osm_bikelanes(
    city_id,
    limit=DEFAULT_IMPORT_LIMIT,
    approve=False,
    approved_by=None,
    fetcher=None,
    include_bikelanes=True,
    include_bus_lanes=True,
):
    """Импортировать OSM-велодорожки в базу, по одному объекту за раз."""
    city = _find_city(city_id)
    candidates, errors = _load_candidates(
        city,
        limit,
        fetcher=fetcher,
        include_bikelanes=include_bikelanes,
        include_bus_lanes=include_bus_lanes,
    )
    existing_keys = _existing_osm_keys(candidates)
    candidates = _merge_connected_candidates(candidates, existing_keys)

    imported = 0
    duplicates = 0
    imported_bikelanes = []

    for candidate in candidates:
        if imported >= _normalize_limit(limit):
            break

        if _candidate_exists(candidate, existing_keys):
            duplicates += 1
            continue

        bikelane = _build_bikelane(candidate, city, approve=approve, approved_by=approved_by)
        db.session.add(bikelane)

        try:
            db.session.flush()
            if not _clean_tag_value(candidate.tags.get('name')):
                if candidate.track_type == 'bus_lane':
                    bikelane.title = f'Автобусная полоса №{bikelane.id}'[:200]
                else:
                    bikelane.title = f'Велодорожка №{bikelane.id}'[:200]
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            duplicates += 1
            existing_keys.update(candidate.source_keys)
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
        existing_keys.update(candidate.source_keys)

    return {
        'city': city,
        'found': len(candidates),
        'imported': imported,
        'duplicates': duplicates,
        'errors': errors,
        'bikelanes': imported_bikelanes,
        'bus_lanes': [
            bikelane for bikelane in imported_bikelanes
            if bikelane.track_type == 'bus_lane'
        ],
    }


def preview_osm_infrastructure(
    city_id,
    limit=DEFAULT_IMPORT_LIMIT,
    fetcher=None,
    infrastructure_types=None,
):
    """Dry-run импорта велопарковок и ремонтных стоек без записи в базу."""
    city = _find_city(city_id)
    candidates, errors = _load_infrastructure_candidates(
        city,
        limit,
        fetcher=fetcher,
        infrastructure_types=infrastructure_types,
    )
    existing_keys = _existing_infrastructure_keys(candidates)
    importable = [candidate for candidate in candidates if candidate.key not in existing_keys]

    return {
        'city': city,
        'found': len(candidates),
        'existing': len(candidates) - len(importable),
        'importable': min(len(importable), _normalize_limit(limit)),
        'errors': errors,
        'candidates': candidates,
    }


def import_osm_infrastructure(
    city_id,
    limit=DEFAULT_IMPORT_LIMIT,
    fetcher=None,
    infrastructure_types=None,
):
    """Импортировать велопарковки и ремонтные стойки из OpenStreetMap."""
    city = _find_city(city_id)
    candidates, errors = _load_infrastructure_candidates(
        city,
        limit,
        fetcher=fetcher,
        infrastructure_types=infrastructure_types,
    )
    existing_keys = _existing_infrastructure_keys(candidates)

    imported = 0
    duplicates = 0
    imported_points = []

    for candidate in candidates:
        if imported >= _normalize_limit(limit):
            break

        if candidate.key in existing_keys:
            duplicates += 1
            continue

        point = _build_infrastructure_point(candidate, city)
        db.session.add(point)

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
                'Не удалось импортировать объект инфраструктуры OSM %s/%s',
                candidate.osm_type,
                candidate.osm_id,
            )
            errors.append(f'{candidate.osm_type}/{candidate.osm_id}: {exc}')
            continue

        imported += 1
        imported_points.append(point)
        existing_keys.add(candidate.key)

    return {
        'city': city,
        'found': len(candidates),
        'imported': imported,
        'duplicates': duplicates,
        'errors': errors,
        'points': imported_points,
    }


def map_osm_tags_to_track_type(tags):
    """Классификация тегов OSM в тип дорожки Velojol."""
    tags = _normalized_tags(tags)
    if _is_bus_lane(tags):
        return 'bus_lane'
    if tags.get('cycleway:right') == 'lane' or tags.get('cycleway:left') == 'lane':
        return 'lane'
    if tags.get('cycleway') == 'lane':
        return 'lane'
    if tags.get('highway') == 'cycleway' or tags.get('cycleway') == 'track':
        return 'separated'
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


def _load_candidates(
    city,
    limit,
    fetcher=None,
    include_bikelanes=True,
    include_bus_lanes=True,
):
    limit = _normalize_limit(limit)
    errors = []

    try:
        payload = _fetch_overpass(
            city,
            limit,
            fetcher=fetcher,
            include_bikelanes=include_bikelanes,
            include_bus_lanes=include_bus_lanes,
        )
    except OsmImportError:
        raise
    except Exception as exc:
        current_app.logger.exception('Не удалось получить данные Overpass для city_id=%s', city.city_id)
        raise OsmImportError(f'Overpass недоступен: {exc}') from exc

    candidates = []
    seen = set()
    for element in payload.get('elements', []):
        if element.get('type') == 'count':
            continue
        candidate, error = _candidate_from_element(element)
        if error:
            errors.append(error)
            continue
        if candidate.track_type == 'bus_lane' and not include_bus_lanes:
            continue
        if candidate.track_type != 'bus_lane' and not include_bikelanes:
            continue
        if candidate.key in seen:
            continue
        seen.add(candidate.key)
        candidates.append(candidate)

    return candidates, errors


def _load_infrastructure_candidates(
    city,
    limit,
    fetcher=None,
    infrastructure_types=None,
):
    limit = _normalize_limit(limit)
    errors = []
    selected_types = _normalize_infrastructure_types(infrastructure_types)

    try:
        payload = _fetch_overpass_infrastructure(
            city,
            limit,
            fetcher=fetcher,
            infrastructure_types=selected_types,
        )
    except OsmImportError:
        raise
    except Exception as exc:
        current_app.logger.exception(
            'Не удалось получить велоинфраструктуру Overpass для city_id=%s',
            city.city_id,
        )
        raise OsmImportError(f'Overpass недоступен: {exc}') from exc

    candidates = []
    seen = set()
    for element in payload.get('elements', []):
        if element.get('type') == 'count':
            continue
        candidate, error = _infrastructure_candidate_from_element(element)
        if error:
            errors.append(error)
            continue
        if candidate.infrastructure_type not in selected_types:
            continue
        if candidate.key in seen:
            continue
        seen.add(candidate.key)
        candidates.append(candidate)

    return candidates, errors


def _fetch_overpass(
    city,
    limit,
    fetcher=None,
    include_bikelanes=True,
    include_bus_lanes=True,
):
    timeout = current_app.config.get('OSM_OVERPASS_TIMEOUT', DEFAULT_TIMEOUT)
    query = _build_overpass_query(
        city,
        limit,
        timeout=timeout,
        include_bikelanes=include_bikelanes,
        include_bus_lanes=include_bus_lanes,
    )

    if fetcher is not None:
        payload = fetcher(query)
        _ensure_admin_area_found(payload, city)
        return payload

    overpass_url = current_app.config.get('OSM_OVERPASS_URL', DEFAULT_OVERPASS_URL)
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    request = urllib.request.Request(
        overpass_url,
        data=data,
        headers={'User-Agent': 'Velojol OSM importer MVP'}
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
            _ensure_admin_area_found(payload, city)
            return payload
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        current_app.logger.exception('Overpass API недоступен')
        raise OsmImportError(f'Overpass недоступен: {exc}') from exc


def _fetch_overpass_infrastructure(
    city,
    limit,
    fetcher=None,
    infrastructure_types=None,
):
    timeout = current_app.config.get('OSM_OVERPASS_TIMEOUT', DEFAULT_TIMEOUT)
    query = _build_infrastructure_overpass_query(
        city,
        timeout=timeout,
        infrastructure_types=infrastructure_types,
    )

    if fetcher is not None:
        payload = fetcher(query)
        _ensure_admin_area_found(payload, city)
        return payload

    overpass_url = current_app.config.get('OSM_OVERPASS_URL', DEFAULT_OVERPASS_URL)
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    request = urllib.request.Request(
        overpass_url,
        data=data,
        headers={'User-Agent': 'Velojol OSM infrastructure importer'},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
            _ensure_admin_area_found(payload, city)
            return payload
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        current_app.logger.exception('Overpass API недоступен')
        raise OsmImportError(f'Overpass недоступен: {exc}') from exc


def _build_overpass_query(
    city,
    limit,
    timeout=DEFAULT_TIMEOUT,
    include_bikelanes=True,
    include_bus_lanes=True,
):
    selectors = []
    filters = ()
    if include_bikelanes:
        filters += OSM_FILTERS
    if include_bus_lanes:
        filters += OSM_BUS_LANE_FILTERS

    for osm_type in ('way', 'relation'):
        for key, value in filters:
            if value is None:
                selectors.append(f'{osm_type}["{key}"](area.searchArea);')
            else:
                selectors.append(
                    f'{osm_type}["{key}"="{value}"](area.searchArea);'
                )

    # Запрашиваем запас кандидатов: уже импортированные объекты не должны
    # занимать пользовательский лимит новых велодорожек. Лимит импорта ниже
    # применяется после проверки дубликатов в базе.
    overpass_limit = MAX_OVERPASS_RESULTS
    return (
        f'[out:json][timeout:{int(timeout)}];\n'
        + _city_area_query(city)
        + '(\n'
        + '\n'.join(selectors)
        + '\n)->.candidates;\n'
        f'.candidates out geom {overpass_limit};\n'
        '.searchArea out count;'
    )


def _build_infrastructure_overpass_query(
    city,
    timeout=DEFAULT_TIMEOUT,
    infrastructure_types=None,
):
    selected_types = _normalize_infrastructure_types(infrastructure_types)
    selectors = [
        f'{osm_type}["amenity"="{amenity}"](area.searchArea);'
        for osm_type in ('node', 'way', 'relation')
        for amenity, infrastructure_type in OSM_INFRASTRUCTURE_AMENITIES.items()
        if infrastructure_type in selected_types
    ]
    return (
        f'[out:json][timeout:{int(timeout)}];\n'
        + _city_area_query(city)
        + '(\n'
        + '\n'.join(selectors)
        + '\n)->.candidates;\n'
        f'.candidates out center {MAX_OVERPASS_RESULTS};\n'
        '.searchArea out count;'
    )


def _normalize_infrastructure_types(infrastructure_types):
    allowed_types = set(OSM_INFRASTRUCTURE_AMENITIES.values())
    if infrastructure_types is None:
        return allowed_types
    return set(infrastructure_types) & allowed_types


def _city_area_query(city):
    city_name = json.dumps(str(city.name), ensure_ascii=False)
    name_selectors = '\n'.join(
        f'area.containingAreas["boundary"="administrative"]'
        f'["{name_tag}"={city_name}];'
        for name_tag in ('name', 'name:ru', 'name:kk', 'name:en')
    )
    return (
        f'is_in({city.coords_lat:.6f},{city.coords_lng:.6f})'
        '->.containingAreas;\n'
        '(\n'
        f'{name_selectors}\n'
        'area.containingAreas["boundary"="administrative"]'
        '["place"~"^(city|town)$"];\n'
        ')->.searchArea;\n'
    )


def _ensure_admin_area_found(payload, city):
    area_counts = [
        element.get('tags', {}).get('areas')
        for element in payload.get('elements', [])
        if element.get('type') == 'count'
    ]
    if area_counts and all(str(count) == '0' for count in area_counts):
        raise OsmImportError(
            f'Административная граница города «{city.name}» не найдена в OSM'
        )


def _candidate_from_element(element):
    osm_type = element.get('type')
    osm_id = element.get('id')
    tags = element.get('tags') or {}

    if osm_type not in {'way', 'relation'} or osm_id is None:
        return None, 'OSM-элемент без type/id пропущен'

    track_type = map_osm_tags_to_track_type(tags)
    is_bus_lane = track_type == 'bus_lane'

    if not is_bus_lane and _clean_tag_value(tags.get('bicycle')) == 'no':
        return None, f'{osm_type}/{osm_id}: bicycle=no'

    excluded_cycleway_tags = [
        key
        for key in EXCLUDED_CYCLEWAY_TAGS
        if _clean_tag_value(tags.get(key)) in EXCLUDED_CYCLEWAY_VALUES
    ]
    if not is_bus_lane and excluded_cycleway_tags:
        reason = ', '.join(
            f'{key}={_clean_tag_value(tags.get(key))}'
            for key in excluded_cycleway_tags
        )
        return None, f'{osm_type}/{osm_id}: {reason}'

    if not is_bus_lane and not _matches_cycle_filter(tags):
        return None, f'{osm_type}/{osm_id}: нет поддерживаемых тегов полосы'

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
        track_type=track_type,
    ), None


def _candidate_exists(candidate, existing_keys):
    return any(key in existing_keys for key in candidate.source_keys)


def _merge_connected_candidates(candidates, existing_keys=None):
    """Объединить совместимые OSM ways в непрерывные линии без развилок."""
    if len(candidates) < 2:
        return candidates

    existing_keys = existing_keys or set()
    endpoints = defaultdict(list)
    signatures = {}

    for index, candidate in enumerate(candidates):
        if candidate.osm_type != 'way':
            continue
        coordinates = candidate.geometry.get('coordinates') or []
        if len(coordinates) < 2:
            continue

        start = tuple(coordinates[0])
        end = tuple(coordinates[-1])
        if start == end:
            continue

        endpoints[start].append(index)
        endpoints[end].append(index)
        signatures[index] = (
            candidate.track_type,
            json.dumps(
                _normalized_tags(candidate.tags),
                ensure_ascii=False,
                sort_keys=True,
                separators=(',', ':'),
            ),
            candidate.key in existing_keys,
        )

    pair_endpoints = defaultdict(list)
    for endpoint, indexes in endpoints.items():
        unique_indexes = list(dict.fromkeys(indexes))
        if len(unique_indexes) != 2:
            continue
        first, second = unique_indexes
        if signatures.get(first) != signatures.get(second):
            continue
        pair_endpoints[tuple(sorted((first, second)))].append(endpoint)

    adjacency = defaultdict(set)
    connections = {}
    for pair, shared_endpoints in pair_endpoints.items():
        # Две линии, имеющие оба общих конца, образуют петлю/дубликат,
        # а не однозначную последовательную цепочку.
        if len(shared_endpoints) != 1:
            continue
        first, second = pair
        adjacency[first].add(second)
        adjacency[second].add(first)
        connections[pair] = shared_endpoints[0]

    replacements = {}
    suppressed = set()
    visited = set()

    for index in range(len(candidates)):
        if index in visited or not adjacency.get(index):
            continue

        component = []
        stack = [index]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            stack.extend(adjacency[current] - visited)

        if len(component) < 2:
            continue
        starts = [item for item in component if len(adjacency[item]) == 1]
        if len(starts) != 2:
            # Замкнутые циклы не имеют однозначного начала и не объединяются.
            continue

        ordered = []
        previous = None
        current = min(starts)
        while current is not None:
            ordered.append(current)
            following = [
                item for item in adjacency[current]
                if item != previous and item not in ordered
            ]
            previous, current = current, (following[0] if following else None)

        if len(ordered) != len(component):
            continue

        merged = _merge_ordered_candidates(candidates, ordered, connections)
        replacements[min(component)] = merged
        suppressed.update(component)
        suppressed.remove(min(component))

    return [
        replacements.get(index, candidate)
        for index, candidate in enumerate(candidates)
        if index not in suppressed
    ]


def _merge_ordered_candidates(candidates, ordered, connections):
    first = candidates[ordered[0]]
    coordinates = list(first.geometry['coordinates'])

    if len(ordered) > 1:
        first_pair = tuple(sorted((ordered[0], ordered[1])))
        first_connection = connections[first_pair]
        if tuple(coordinates[-1]) != first_connection:
            coordinates.reverse()

    member_keys = list(first.source_keys)
    for previous_index, current_index in zip(ordered, ordered[1:]):
        pair = tuple(sorted((previous_index, current_index)))
        connection = connections[pair]
        next_coordinates = list(candidates[current_index].geometry['coordinates'])
        if tuple(next_coordinates[0]) != connection:
            next_coordinates.reverse()
        coordinates.extend(next_coordinates[1:])
        member_keys.extend(candidates[current_index].source_keys)

    return OsmCandidate(
        osm_type=first.osm_type,
        osm_id=first.osm_id,
        tags=first.tags,
        geometry={
            'type': 'LineString',
            'coordinates': coordinates,
        },
        length_meters=_line_length_meters(coordinates),
        track_type=first.track_type,
        member_keys=tuple(member_keys),
    )


def _infrastructure_candidate_from_element(element):
    osm_type = element.get('type')
    osm_id = element.get('id')
    tags = element.get('tags') or {}
    amenity = _clean_tag_value(tags.get('amenity'))
    infrastructure_type = OSM_INFRASTRUCTURE_AMENITIES.get(amenity)

    if osm_type not in {'node', 'way', 'relation'} or osm_id is None:
        return None, 'OSM-объект инфраструктуры без type/id пропущен'
    if infrastructure_type is None:
        return None, f'{osm_type}/{osm_id}: неподдерживаемый amenity'

    location = element if osm_type == 'node' else element.get('center') or {}
    try:
        latitude = float(location['lat'])
        longitude = float(location['lon'])
    except (KeyError, TypeError, ValueError):
        return None, f'{osm_type}/{osm_id}: нет координат или центра'

    if not math.isfinite(latitude) or not math.isfinite(longitude):
        return None, f'{osm_type}/{osm_id}: некорректные координаты'

    return OsmInfrastructureCandidate(
        osm_type=osm_type,
        osm_id=str(osm_id),
        infrastructure_type=infrastructure_type,
        tags=tags,
        latitude=latitude,
        longitude=longitude,
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
    keys = {
        key
        for candidate in candidates
        for key in candidate.source_keys
    }
    if not keys:
        return set()

    existing = BikeLane.query.filter(
        BikeLane.source == OSM_SOURCE,
        BikeLane.osm_type.in_([key[0] for key in keys]),
        BikeLane.osm_id.in_([key[1] for key in keys]),
    ).all()
    existing_keys = {(item.osm_type, item.osm_id) for item in existing}

    merged = BikeLane.query.filter(
        BikeLane.source == OSM_SOURCE,
        BikeLane.source_metadata.isnot(None),
    ).all()
    for item in merged:
        try:
            metadata = json.loads(item.source_metadata)
            member_keys = metadata.get('osm_import', {}).get('member_keys', [])
        except (AttributeError, json.JSONDecodeError, TypeError):
            continue
        for member in member_keys:
            try:
                existing_keys.add((str(member['type']), str(member['id'])))
            except (KeyError, TypeError):
                continue

    return existing_keys


def _existing_infrastructure_keys(candidates):
    keys = {(candidate.osm_type, candidate.osm_id) for candidate in candidates}
    if not keys:
        return set()

    existing = InfrastructurePoint.query.filter(
        InfrastructurePoint.source == OSM_SOURCE,
        InfrastructurePoint.osm_type.in_([key[0] for key in keys]),
        InfrastructurePoint.osm_id.in_([key[1] for key in keys]),
    ).all()
    return {(item.osm_type, item.osm_id) for item in existing}


def _build_bikelane(candidate, city, approve=False, approved_by=None):
    now = datetime.utcnow()
    is_bus_lane = candidate.track_type == 'bus_lane'
    default_title = 'Автобусная полоса' if is_bus_lane else 'Велодорожка'
    title = str(candidate.tags.get('name') or '').strip() or default_title
    bikelane = BikeLane(
        title=title[:200],
        description='' if is_bus_lane else _build_description(candidate),
        city_id=city.id,
        city=city.city_id,
        geometry=json.dumps(candidate.geometry, ensure_ascii=False),
        track_type=candidate.track_type,
        quality=0 if is_bus_lane else _map_quality(candidate.tags),
        has_parking=False,
        has_markings=False if is_bus_lane else _truthy_tag(
            candidate.tags.get('cycleway:marking')
        ),
        has_signs=False,
        is_one_way=False if is_bus_lane else _clean_tag_value(
            candidate.tags.get('oneway:bicycle', candidate.tags.get('oneway'))
        ) in {'yes', 'true', '1', '-1'},
        photos='[]',
        videos='[]',
        status='approved' if approve else 'pending',
        source=OSM_SOURCE,
        source_metadata=_build_source_metadata(candidate),
        osm_type=candidate.osm_type,
        osm_id=candidate.osm_id,
        osm_tags=json.dumps(candidate.tags, ensure_ascii=False, sort_keys=True),
        imported_at=now,
        created_at=now,
        updated_at=now,
    )
    bikelane.overall_quality = (
        None if is_bus_lane else bikelane.calculate_overall_quality()
    )

    if approve and approved_by is not None:
        bikelane.moderated_at = now
        bikelane.moderated_by = approved_by.id
        bikelane.score = bikelane.calculate_score()

    return bikelane


def _build_source_metadata(candidate):
    if len(candidate.source_keys) < 2:
        return None
    return json.dumps(
        {
            'osm_import': {
                'member_keys': [
                    {'type': osm_type, 'id': osm_id}
                    for osm_type, osm_id in candidate.source_keys
                ],
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _build_infrastructure_point(candidate, city):
    tags = candidate.tags or {}
    default_title = {
        InfrastructurePoint.TYPE_BICYCLE_PARKING: 'Велопарковка',
        InfrastructurePoint.TYPE_REPAIR_STATION: 'Стойка для ремонта велосипедов',
    }[candidate.infrastructure_type]
    title = str(tags.get('name') or '').strip() or default_title
    now = datetime.utcnow()

    return InfrastructurePoint(
        city_id=city.id,
        infrastructure_type=candidate.infrastructure_type,
        title=title[:200],
        description=str(tags.get('description') or '').strip(),
        photos='[]',
        latitude=candidate.latitude,
        longitude=candidate.longitude,
        source=OSM_SOURCE,
        osm_type=candidate.osm_type,
        osm_id=candidate.osm_id,
        osm_tags=json.dumps(tags, ensure_ascii=False, sort_keys=True),
        imported_at=now,
        created_at=now,
        updated_at=now,
    )


def build_osm_description(tags):
    """Краткое публичное описание без технических OSM-метаданных."""
    tags = _normalized_tags(tags)
    right_lane = tags.get('cycleway:right') == 'lane'
    left_lane = tags.get('cycleway:left') == 'lane'

    if right_lane and left_lane:
        return 'Велополосы с обеих сторон улицы'
    if right_lane:
        return 'Велополоса с правой стороны улицы'
    if left_lane:
        return 'Велополоса с левой стороны улицы'
    if tags.get('highway') == 'footway' and tags.get('bicycle') == 'designated':
        return 'Велопешеходная дорожка'
    if tags.get('highway') == 'cycleway' or tags.get('cycleway') == 'track':
        return 'Обособленная велодорожка'
    if tags.get('cycleway') == 'lane':
        return 'Велополоса'
    if (
        tags.get('foot') == 'designated'
        and tags.get('bicycle') == 'designated'
    ) or tags.get('segregated') == 'yes':
        return 'Велопешеходная дорожка'
    return 'Велодорожка'


def _build_description(candidate):
    return build_osm_description(candidate.tags)


def _clean_tag_value(value):
    return str(value or '').strip().casefold()


def _normalized_tags(tags):
    return {
        str(key).strip().casefold(): _clean_tag_value(value)
        for key, value in (tags or {}).items()
    }


def _matches_cycle_filter(tags):
    normalized = _normalized_tags(tags)
    return any(
        (
            key in normalized
            if value is None
            else normalized.get(key) == value
        )
        for key, value in OSM_FILTERS
    )


def _is_bus_lane(tags):
    normalized = _normalized_tags(tags)
    if normalized.get('highway') == 'busway':
        return True

    for key in (
        'lanes:bus',
        'lanes:bus:forward',
        'lanes:bus:backward',
        'lanes:psv',
        'lanes:psv:forward',
        'lanes:psv:backward',
    ):
        try:
            if int(normalized.get(key, '0')) > 0:
                return True
        except ValueError:
            continue

    for key in (
        'bus:lanes',
        'bus:lanes:forward',
        'bus:lanes:backward',
        'psv:lanes',
        'psv:lanes:forward',
        'psv:lanes:backward',
    ):
        if 'designated' in normalized.get(key, '').split('|'):
            return True

    return any(
        normalized.get(key) in {'lane', 'opposite_lane', 'designated'}
        for key in ('busway', 'busway:left', 'busway:right')
    )


def _map_quality(tags):
    surface = _clean_tag_value(tags.get('surface'))
    if surface in {'asphalt', 'concrete', 'paved'}:
        return 4
    if surface in {'paving_stones', 'sett', 'compacted'}:
        return 3
    if surface in {'gravel', 'fine_gravel', 'ground', 'dirt', 'earth', 'unpaved'}:
        return 2
    return 3


def _truthy_tag(value):
    return _clean_tag_value(value) in {'yes', 'true', '1'}


def _normalize_limit(limit):
    try:
        normalized = int(limit)
    except (TypeError, ValueError):
        normalized = DEFAULT_IMPORT_LIMIT
    return max(1, min(MAX_IMPORT_LIMIT, normalized))
