import json
import math
from collections import defaultdict
from datetime import datetime


MAX_ENDPOINT_GAP_METERS = 25


def merge_bikelanes(bikelanes, admin_user):
    """Объединить выбранные линии, сохранив запись с наименьшим ID."""
    bikelanes = sorted(bikelanes, key=lambda item: item.id)
    if len(bikelanes) < 2:
        raise ValueError('Для объединения выберите минимум две линии.')

    city_slugs = {item.city for item in bikelanes}
    city_ids = {item.city_id for item in bikelanes if item.city_id is not None}
    if len(city_slugs) != 1 or len(city_ids) > 1:
        raise ValueError('Можно объединять только линии одного города.')

    track_types = {item.track_type for item in bikelanes}
    if len(track_types) != 1:
        raise ValueError('Можно объединять только линии одного типа.')

    primary = bikelanes[0]
    primary.set_geometry_dict({
        'type': 'LineString',
        'coordinates': _merge_line_coordinates(bikelanes),
    })
    primary.set_photos_list(_unique_media(
        item.get_photos_list()
        for item in bikelanes
    ))
    primary.set_videos_list(_unique_media(
        item.get_videos_list()
        for item in bikelanes
    ))
    primary.source_metadata = _merged_source_metadata(
        primary,
        bikelanes,
        admin_user,
    )
    if primary.status == 'approved':
        primary.score = primary.calculate_score()

    comment = f'Объединено с линией №{primary.id}'
    for item in bikelanes[1:]:
        item.reject(admin_user, comment)

    return primary


def _merge_line_coordinates(bikelanes):
    coordinates_by_id = {}
    endpoint_records = []

    for item in bikelanes:
        geometry = item.get_geometry_dict()
        coordinates = geometry.get('coordinates') or []
        if geometry.get('type') != 'LineString' or len(coordinates) < 2:
            raise ValueError(f'Линия №{item.id} содержит некорректную геометрию.')

        normalized = []
        for coordinate in coordinates:
            if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
                raise ValueError(f'Линия №{item.id} содержит некорректную геометрию.')
            try:
                point = [float(coordinate[0]), float(coordinate[1])]
            except (TypeError, ValueError):
                raise ValueError(
                    f'Линия №{item.id} содержит некорректную геометрию.'
                ) from None
            if not all(math.isfinite(value) for value in point):
                raise ValueError(f'Линия №{item.id} содержит некорректную геометрию.')
            normalized.append(point)

        start = tuple(normalized[0])
        end = tuple(normalized[-1])
        if start == end:
            raise ValueError(f'Линия №{item.id} замкнута сама на себя.')

        coordinates_by_id[item.id] = normalized
        endpoint_records.extend([
            {'line_id': item.id, 'coordinate': start},
            {'line_id': item.id, 'coordinate': end},
        ])

    endpoint_groups = _group_nearby_endpoints(endpoint_records)
    if any(len(group) > 2 for group in endpoint_groups):
        raise ValueError('Выбранные линии образуют развилку.')

    chain_ends = [group for group in endpoint_groups if len(group) == 1]
    if len(chain_ends) != 2:
        raise ValueError(
            'Выбранные линии не образуют одну непрерывную цепочку. '
            f'Допустимый зазор между концами — до {MAX_ENDPOINT_GAP_METERS} м.'
        )

    adjacency = defaultdict(list)
    connection = {}
    for group in endpoint_groups:
        if len(group) != 2:
            continue
        first, second = group
        if first['line_id'] == second['line_id']:
            raise ValueError('Выбранные линии образуют замкнутую петлю.')
        first_id = first['line_id']
        second_id = second['line_id']
        pair = tuple(sorted((first_id, second_id)))
        if pair in connection:
            raise ValueError('Выбранные линии образуют замкнутую петлю.')
        adjacency[first_id].append(second_id)
        adjacency[second_id].append(first_id)
        connection[pair] = {
            first_id: first['coordinate'],
            second_id: second['coordinate'],
        }

    start_id = chain_ends[0][0]['line_id']
    ordered_ids = []
    previous_id = None
    current_id = start_id
    while current_id is not None:
        ordered_ids.append(current_id)
        following = [
            item_id for item_id in adjacency[current_id]
            if item_id != previous_id
        ]
        previous_id, current_id = (
            current_id,
            following[0] if following else None,
        )

    if len(ordered_ids) != len(bikelanes):
        raise ValueError(
            'Между выбранными линиями есть разрыв более '
            f'{MAX_ENDPOINT_GAP_METERS} м.'
        )

    merged = list(coordinates_by_id[ordered_ids[0]])
    if len(ordered_ids) > 1:
        first_pair = tuple(sorted((ordered_ids[0], ordered_ids[1])))
        first_connection = connection[first_pair][ordered_ids[0]]
        if tuple(merged[-1]) != first_connection:
            merged.reverse()

    for previous_id, current_id in zip(ordered_ids, ordered_ids[1:]):
        pair = tuple(sorted((previous_id, current_id)))
        current_endpoint = connection[pair][current_id]
        next_coordinates = list(coordinates_by_id[current_id])
        if tuple(next_coordinates[0]) != current_endpoint:
            next_coordinates.reverse()
        if merged[-1] == next_coordinates[0]:
            merged.extend(next_coordinates[1:])
        else:
            merged.extend(next_coordinates)

    return merged


def _group_nearby_endpoints(endpoint_records):
    """Сгруппировать концы линий, расположенные в пределах допуска."""
    parents = list(range(len(endpoint_records)))

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(first_index, second_index):
        first_root = find(first_index)
        second_root = find(second_index)
        if first_root != second_root:
            parents[second_root] = first_root

    for first_index, first in enumerate(endpoint_records):
        for second_index in range(first_index + 1, len(endpoint_records)):
            second = endpoint_records[second_index]
            if first['line_id'] == second['line_id']:
                continue
            if _distance_meters(
                first['coordinate'],
                second['coordinate'],
            ) <= MAX_ENDPOINT_GAP_METERS:
                union(first_index, second_index)

    groups = defaultdict(list)
    for index, endpoint in enumerate(endpoint_records):
        groups[find(index)].append(endpoint)
    return list(groups.values())


def _distance_meters(first, second):
    """Расстояние между координатами GeoJSON [долгота, широта]."""
    lon1, lat1 = map(math.radians, first)
    lon2, lat2 = map(math.radians, second)
    latitude_delta = lat2 - lat1
    longitude_delta = lon2 - lon1
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(longitude_delta / 2) ** 2
    )
    return 6371000 * 2 * math.atan2(
        math.sqrt(haversine),
        math.sqrt(1 - haversine),
    )


def _unique_media(media_lists):
    result = []
    seen = set()
    for media_list in media_lists:
        for value in media_list:
            key = str(value)
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
    return result


def _merged_source_metadata(primary, bikelanes, admin_user):
    metadata = _load_metadata(primary.source_metadata)
    merged_ids = set()
    for item_id in metadata.get('admin_merge', {}).get('merged_bikelane_ids', []):
        try:
            merged_ids.add(int(item_id))
        except (TypeError, ValueError):
            continue
    merged_ids.update(item.id for item in bikelanes if item.id != primary.id)
    metadata['admin_merge'] = {
        'merged_bikelane_ids': sorted(merged_ids),
        'merged_at': datetime.utcnow().isoformat(),
        'merged_by': admin_user.id,
    }

    osm_member_keys = []
    seen_keys = set()
    for item in bikelanes:
        item_metadata = _load_metadata(item.source_metadata)
        stored_keys = item_metadata.get('osm_import', {}).get('member_keys', [])
        if item.source == 'openstreetmap' and item.osm_type and item.osm_id:
            stored_keys = [
                {'type': item.osm_type, 'id': item.osm_id},
                *stored_keys,
            ]
        for member in stored_keys:
            try:
                key = (str(member['type']), str(member['id']))
            except (KeyError, TypeError):
                continue
            if key in seen_keys:
                continue
            seen_keys.add(key)
            osm_member_keys.append({'type': key[0], 'id': key[1]})

    if osm_member_keys:
        metadata['osm_import'] = {'member_keys': osm_member_keys}

    return json.dumps(metadata, ensure_ascii=False, sort_keys=True)


def _load_metadata(value):
    try:
        metadata = json.loads(value or '{}')
        return metadata if isinstance(metadata, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}
