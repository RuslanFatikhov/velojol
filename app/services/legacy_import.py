"""Import the original velojol.kz JSON and photo archive.

The importer is deliberately split into planning and application phases.  A
plan never mutates the database or filesystem, which makes it suitable for a
production dry-run before an explicitly requested import.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import shutil

from flask import current_app
from PIL import Image

from app import db
from app.models.bikelane import BikeLane
from app.models.city import City


LEGACY_SOURCE = 'legacy_velojol'
SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
GENERIC_DESCRIPTIONS = {
    '',
    'велодорожка',
    'велополоса',
    'велопешеходная дорожка',
    'обособленная велодорожка',
}


class LegacyImportError(RuntimeError):
    """The legacy archive is missing required files or contains invalid JSON."""


@dataclass
class LegacyRecord:
    city_id: str
    source_id: str
    external_id: str
    title: str
    description: str
    geometry: dict
    geometry_fingerprint: str
    quality: int
    track_type: str
    has_parking: bool
    has_markings: bool
    has_signs: bool
    created_at: datetime | None
    photo_files: list[Path]
    raw_records: list[dict]
    issues: list[str] = field(default_factory=list)

    @property
    def metadata(self):
        return {
            'legacy_velojol': {
                'external_id': self.external_id,
                'city_id': self.city_id,
                'legacy_ids': [str(item.get('id')) for item in self.raw_records],
                'geometry_fingerprint': self.geometry_fingerprint,
                'records_merged': len(self.raw_records),
                'original': [
                    {
                        'id': item.get('id'),
                        'date': item.get('date'),
                        'distance': item.get('distance'),
                        'safetyLevel': item.get('safetyLevel'),
                        'source': item.get('source'),
                    }
                    for item in self.raw_records
                ],
                'issues': self.issues,
            }
        }


@dataclass
class PlanItem:
    action: str
    city_id: str
    external_id: str | None
    title: str
    reason: str
    record: LegacyRecord | None = None
    target_id: int | None = None
    target_source: str | None = None
    match_score: float | None = None

    def to_dict(self):
        return {
            'action': self.action,
            'city_id': self.city_id,
            'external_id': self.external_id,
            'title': self.title,
            'reason': self.reason,
            'target_id': self.target_id,
            'target_source': self.target_source,
            'match_score': round(self.match_score, 4) if self.match_score is not None else None,
            'legacy_ids': (
                [str(row.get('id')) for row in self.record.raw_records]
                if self.record else []
            ),
            'photos': len(self.record.photo_files) if self.record else 0,
            'issues': list(self.record.issues) if self.record else [],
        }


@dataclass
class LegacyImportPlan:
    source_root: Path
    cities: list[dict]
    items: list[PlanItem]
    archive_issues: list[str]
    archive_photo_files: int = 0

    @property
    def summary(self):
        counts = Counter(item.action for item in self.items)
        planned_photo_paths = {
            str(path)
            for item in self.items
            if item.record is not None
            for path in item.record.photo_files
        }
        return {
            'cities': len(self.cities),
            'records': len(self.items),
            'new': counts['new'],
            'merge_osm': counts['merge_osm'],
            'refresh_legacy': counts['refresh_legacy'],
            'review': counts['review'],
            'invalid': counts['invalid'],
            'photo_files': len(planned_photo_paths),
            'archive_photo_files': self.archive_photo_files,
            'unassigned_photo_files': max(
                0,
                self.archive_photo_files - len(planned_photo_paths),
            ),
            'archive_issues': len(self.archive_issues),
        }

    def to_dict(self):
        return {
            'source_root': str(self.source_root),
            'summary': self.summary,
            'archive_issues': self.archive_issues,
            'items': [item.to_dict() for item in self.items],
        }


def build_legacy_import_plan(source_root, spatial_tolerance_meters=20):
    """Build a read-only import plan for the legacy archive."""
    source_root = Path(source_root).expanduser().resolve()
    cities, raw_by_city, archive_issues, archive_photo_files = _load_archive(source_root)
    records, invalid_items = _normalize_records(source_root, raw_by_city)
    existing = BikeLane.query.all()

    items = []
    unresolved = []
    external_targets = _existing_external_targets(existing)

    for record in records:
        target = external_targets.get(record.external_id)
        if target is not None:
            if target.source == 'openstreetmap':
                action = 'merge_osm'
                reason = 'OSM-запись уже связана с этим legacy-источником'
            else:
                action = 'refresh_legacy'
                reason = 'Запись этого legacy-источника уже импортирована'
            items.append(PlanItem(
                action=action,
                city_id=record.city_id,
                external_id=record.external_id,
                title=record.title,
                reason=reason,
                record=record,
                target_id=target.id,
                target_source=target.source,
            ))
            continue
        unresolved.append(record)

    spatial_candidates = _spatial_candidates(
        unresolved,
        existing,
        tolerance_meters=spatial_tolerance_meters,
    )
    target_claims = Counter()
    for candidates in spatial_candidates.values():
        strong = [candidate for candidate in candidates if candidate['kind'] == 'strong']
        if len(strong) == 1:
            target_claims[strong[0]['target'].id] += 1

    for record in unresolved:
        candidates = spatial_candidates.get(record.external_id, [])
        strong = [candidate for candidate in candidates if candidate['kind'] == 'strong']
        partial = [candidate for candidate in candidates if candidate['kind'] == 'partial']

        if len(strong) == 1 and target_claims[strong[0]['target'].id] == 1:
            match = strong[0]
            target = match['target']
            if target.source == 'openstreetmap':
                action = 'merge_osm'
                reason = 'Уникальное взаимное геометрическое совпадение с OSM'
            elif target.source == LEGACY_SOURCE:
                action = 'refresh_legacy'
                reason = 'Legacy-запись найдена по геометрии'
            else:
                action = 'review'
                reason = 'Совпадение с ручной записью требует подтверждения'
            items.append(PlanItem(
                action=action,
                city_id=record.city_id,
                external_id=record.external_id,
                title=record.title,
                reason=reason,
                record=record,
                target_id=target.id,
                target_source=target.source,
                match_score=match['score'],
            ))
        elif strong:
            items.append(PlanItem(
                action='review',
                city_id=record.city_id,
                external_id=record.external_id,
                title=record.title,
                reason='Геометрия совпала с несколькими записями',
                record=record,
                match_score=max(item['score'] for item in strong),
            ))
        elif partial:
            best = partial[0]
            items.append(PlanItem(
                action='review',
                city_id=record.city_id,
                external_id=record.external_id,
                title=record.title,
                reason='Найдено частичное геометрическое пересечение',
                record=record,
                target_id=best['target'].id,
                target_source=best['target'].source,
                match_score=best['score'],
            ))
        else:
            items.append(PlanItem(
                action='new',
                city_id=record.city_id,
                external_id=record.external_id,
                title=record.title,
                reason='Совпадений не найдено',
                record=record,
            ))

    items.extend(invalid_items)
    items.sort(key=lambda item: (item.city_id, item.external_id or '', item.action))
    return LegacyImportPlan(
        source_root,
        cities,
        items,
        archive_issues,
        archive_photo_files=archive_photo_files,
    )


def apply_legacy_import_plan(plan, merge_osm=True, copy_photos=True):
    """Apply safe actions from a previously generated plan.

    Review and invalid items are never written.  Existing OSM rows retain their
    source identifiers, geometry, moderation state, owner and OSM metadata.
    """
    city_map = _apply_cities(plan.source_root, plan.cities, copy_assets=copy_photos)
    result = Counter()
    failures = []

    for item in plan.items:
        if item.action in {'review', 'invalid'}:
            result[item.action] += 1
            continue
        if item.action == 'merge_osm' and not merge_osm:
            result['review'] += 1
            continue

        try:
            target = db.session.get(BikeLane, item.target_id) if item.target_id else None
            if item.action == 'new':
                target = _create_legacy_bikelane(item.record, city_map[item.city_id])
                db.session.add(target)
                db.session.flush()
                result['created'] += 1
            elif item.action == 'merge_osm':
                if target is None:
                    raise LegacyImportError(f'Целевая OSM-запись {item.target_id} не найдена')
                _merge_into_osm(target, item.record)
                result['merged_osm'] += 1
            elif item.action == 'refresh_legacy':
                if target is None:
                    raise LegacyImportError(f'Целевая legacy-запись {item.target_id} не найдена')
                _refresh_legacy_bikelane(target, item.record, city_map[item.city_id])
                result['refreshed'] += 1

            if copy_photos and target is not None:
                copied = _copy_record_photos(plan.source_root, item.record, target)
                result['photos_copied'] += copied
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            failures.append({
                'external_id': item.external_id,
                'action': item.action,
                'error': str(exc),
            })

    return {
        'created': result['created'],
        'merged_osm': result['merged_osm'],
        'refreshed': result['refreshed'],
        'review': result['review'],
        'invalid': result['invalid'],
        'photos_copied': result['photos_copied'],
        'failures': failures,
    }


def infer_legacy_track_type(description):
    """Infer the closest supported track type without inventing details."""
    text = _normalized_text(description)
    if 'боллард' in text:
        return 'bollards'
    if 'велополос' in text:
        return 'lane'
    if any(token in text for token in ('велопешеход', 'вело-пешеход', 'пешеходн')):
        return 'shared'
    if any(token in text for token in ('обособлен', 'отделен', 'отделён')):
        return 'separated'
    return 'shared'


def _load_archive(source_root):
    cities_path = source_root / 'static' / 'data' / 'cities.json'
    lanes_dir = source_root / 'static' / 'data' / 'cities'
    if not cities_path.is_file():
        raise LegacyImportError(f'Не найден файл городов: {cities_path}')
    if not lanes_dir.is_dir():
        raise LegacyImportError(f'Не найдена папка велодорожек: {lanes_dir}')

    try:
        cities = json.loads(cities_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise LegacyImportError(f'Не удалось прочитать {cities_path}: {exc}') from exc
    if not isinstance(cities, list):
        raise LegacyImportError('static/data/cities.json должен содержать массив')

    raw_by_city = {}
    issues = []
    listed_ids = {str(city.get('id', '')).strip() for city in cities}
    for city in cities:
        city_id = str(city.get('id', '')).strip()
        if not city_id:
            issues.append('Город без id пропущен')
            continue
        data_path = lanes_dir / f'{city_id}.json'
        if not data_path.is_file():
            issues.append(f'{city_id}: отсутствует файл велодорожек')
            raw_by_city[city_id] = []
            continue
        try:
            rows = json.loads(data_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise LegacyImportError(f'Не удалось прочитать {data_path}: {exc}') from exc
        if not isinstance(rows, list):
            raise LegacyImportError(f'{data_path} должен содержать массив')
        raw_by_city[city_id] = rows

    for path in sorted(lanes_dir.glob('*.json')):
        if path.stem not in listed_ids:
            issues.append(f'{path.stem}: JSON не связан с публичным городом и не импортируется')
    archive_photo_files, photo_issues = _inspect_archive_photos(source_root, raw_by_city)
    issues.extend(photo_issues)
    return cities, raw_by_city, issues, archive_photo_files


def _inspect_archive_photos(source_root, raw_by_city):
    photos_root = source_root / 'static' / 'img' / 'bikelanes'
    if not photos_root.is_dir():
        return 0, ['Папка фотографий велодорожек отсутствует']

    total_files = 0
    invalid_files = 0
    issues = []
    for city_dir in sorted(path for path in photos_root.iterdir() if path.is_dir()):
        image_files = [
            path
            for path in city_dir.rglob('*')
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        ]
        total_files += len(image_files)
        invalid_files += sum(not _is_valid_image(path) for path in image_files)
        if city_dir.name not in raw_by_city:
            if image_files:
                issues.append(
                    f'{city_dir.name}: {len(image_files)} фото не связаны с публичным городом'
                )
            continue

        known_ids = {str(row.get('id')) for row in raw_by_city[city_dir.name]}
        orphan_dirs = []
        orphan_files = 0
        for lane_dir in (path for path in city_dir.iterdir() if path.is_dir()):
            if lane_dir.name in known_ids:
                continue
            files = [
                path
                for path in lane_dir.rglob('*')
                if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
            ]
            if files:
                orphan_dirs.append(lane_dir.name)
                orphan_files += len(files)
        if orphan_dirs:
            issues.append(
                f'{city_dir.name}: {len(orphan_dirs)} папок и {orphan_files} фото '
                'не связаны с актуальными ID'
            )
    if invalid_files:
        issues.append(f'Повреждённых или пустых изображений: {invalid_files}')
    return total_files, issues


def _normalize_records(source_root, raw_by_city):
    records = []
    invalid_items = []

    for city_id, rows in raw_by_city.items():
        id_counts = Counter(str(row.get('id')) for row in rows)
        valid = []
        for index, row in enumerate(rows):
            source_id = str(row.get('id', '')).strip()
            coordinates, error = _normalize_coordinates(row.get('coordinates'))
            if not source_id or error:
                invalid_items.append(PlanItem(
                    action='invalid',
                    city_id=city_id,
                    external_id=None,
                    title=_clean_text(row.get('name')) or f'Запись #{index + 1}',
                    reason=error or 'Отсутствует legacy ID',
                ))
                continue
            fingerprint = _geometry_fingerprint(coordinates)
            valid.append((row, source_id, coordinates, fingerprint, id_counts[source_id]))

        by_geometry = defaultdict(list)
        for normalized in valid:
            by_geometry[normalized[3]].append(normalized)

        for fingerprint, group in by_geometry.items():
            canonical = max(group, key=lambda item: _record_richness(item[0]))
            row, source_id, coordinates, _, duplicate_id_count = canonical
            raw_records = [item[0] for item in group]
            issues = []
            if len(group) > 1:
                issues.append(f'Объединено точных геометрических дублей: {len(group)}')
            if duplicate_id_count > 1:
                issues.append('Legacy ID повторяется у разных геометрий')

            description = max(
                (_clean_text(item.get('description')) for item in raw_records),
                key=len,
                default='',
            )
            title = max(
                (_clean_text(item.get('name')) for item in raw_records),
                key=len,
                default='',
            ) or 'Велодорожка'
            quality_values = [
                _quality(item.get('safetyLevel'))
                for item in raw_records
                if _quality(item.get('safetyLevel')) > 0
            ]
            quality = max(quality_values, default=0)
            if not description:
                issues.append('Описание отсутствует; использован нейтральный fallback')
                description = 'Велодорожка'
            if quality == 0:
                issues.append('Оценка качества отсутствует')

            photo_files = []
            ambiguous_ids = {
                item_source_id
                for _, item_source_id, _, _, count in group
                if count > 1
            }
            for _, item_source_id, _, _, _ in group:
                if item_source_id in ambiguous_ids:
                    issues.append(
                        f'Фото для повторяющегося ID {item_source_id} требуют проверки'
                    )
                    continue
                photo_files.extend(_legacy_photo_files(source_root, city_id, item_source_id))
            photo_files = sorted(set(photo_files))

            external_id = f'{city_id}:{source_id}:{fingerprint[:16]}'
            record = LegacyRecord(
                city_id=city_id,
                source_id=source_id,
                external_id=external_id,
                title=title[:200],
                description=description,
                geometry={'type': 'LineString', 'coordinates': coordinates},
                geometry_fingerprint=fingerprint,
                quality=quality,
                track_type=infer_legacy_track_type(description),
                has_parking=_mentions_parking(description),
                has_markings='разметк' in _normalized_text(description),
                has_signs='знак' in _normalized_text(description),
                created_at=_parse_legacy_date(row.get('date')),
                photo_files=photo_files,
                raw_records=raw_records,
                issues=list(dict.fromkeys(issues)),
            )
            records.append(record)
    return records, invalid_items


def _existing_external_targets(existing):
    targets = {}
    for target in existing:
        if target.external_id:
            targets[target.external_id] = target
        metadata = _load_metadata(target.source_metadata)
        external_id = (
            metadata.get('legacy_velojol', {}).get('external_id')
            if isinstance(metadata.get('legacy_velojol'), dict)
            else None
        )
        if external_id:
            targets[external_id] = target
    return targets


def _spatial_candidates(records, existing, tolerance_meters):
    result = defaultdict(list)
    existing_samples = {}
    for target in existing:
        coordinates = target.get_geometry_dict().get('coordinates') or []
        if len(coordinates) >= 2:
            existing_samples[target.id] = _sample_line(coordinates)

    for record in records:
        source_samples = _sample_line(record.geometry['coordinates'])
        for target in existing:
            if target.city != record.city_id or target.id not in existing_samples:
                continue
            target_samples = existing_samples[target.id]
            source_coverage = _line_coverage(source_samples, target_samples, tolerance_meters)
            target_coverage = _line_coverage(target_samples, source_samples, tolerance_meters)
            mutual = min(source_coverage, target_coverage)
            maximum = max(source_coverage, target_coverage)
            if mutual >= 0.85 and maximum >= 0.90:
                kind = 'strong'
                score = mutual
            elif maximum >= 0.80:
                kind = 'partial'
                score = maximum
            else:
                continue
            result[record.external_id].append({
                'target': target,
                'kind': kind,
                'score': score,
                'source_coverage': source_coverage,
                'target_coverage': target_coverage,
            })
        result[record.external_id].sort(key=lambda item: item['score'], reverse=True)
    return result


def _apply_cities(source_root, cities, copy_assets):
    result = {}
    for raw in cities:
        city_id = str(raw.get('id', '')).strip()
        if not city_id:
            continue
        coordinates = raw.get('coordinates') or []
        if len(coordinates) < 2:
            raise LegacyImportError(f'{city_id}: координаты города отсутствуют')

        city = City.query.filter_by(city_id=city_id).first()
        if city is None:
            city = City(
                city_id=city_id,
                name=_clean_text(raw.get('city')) or city_id,
                country=_clean_text(raw.get('country')) or 'Не указано',
                coords_lat=float(coordinates[1]),
                coords_lng=float(coordinates[0]),
                zoom=int(raw.get('zoom') or 12),
                status='active',
            )
            db.session.add(city)
            db.session.flush()
        else:
            if not city.name:
                city.name = _clean_text(raw.get('city')) or city_id
            if not city.country:
                city.country = _clean_text(raw.get('country')) or 'Не указано'

        if copy_assets:
            coat = _copy_city_asset(source_root, city_id, raw.get('coat'), 'coat')
            background = _copy_city_asset(source_root, city_id, raw.get('cover'), 'bg')
            if coat and not city.coat_of_arms:
                city.coat_of_arms = coat
            if background and not city.background_image:
                city.background_image = background
        result[city_id] = city
    db.session.commit()
    return result


def _create_legacy_bikelane(record, city):
    bikelane = BikeLane(
        title=record.title,
        description=record.description,
        city_id=city.id,
        city=city.city_id,
        geometry=json.dumps(record.geometry, ensure_ascii=False, separators=(',', ':')),
        track_type=record.track_type,
        quality=record.quality,
        has_parking=record.has_parking,
        has_markings=record.has_markings,
        has_signs=record.has_signs,
        overall_quality=record.quality or None,
        photos='[]',
        videos='[]',
        status='approved',
        score=0,
        source=LEGACY_SOURCE,
        external_id=record.external_id,
        source_metadata=json.dumps(record.metadata, ensure_ascii=False, sort_keys=True),
        imported_at=datetime.utcnow(),
        created_at=record.created_at or datetime.utcnow(),
        user_id=None,
    )
    return bikelane


def _refresh_legacy_bikelane(target, record, city):
    target.title = record.title
    target.description = record.description
    target.city_id = city.id
    target.city = city.city_id
    target.geometry = json.dumps(record.geometry, ensure_ascii=False, separators=(',', ':'))
    target.track_type = record.track_type
    target.quality = record.quality
    target.has_parking = record.has_parking
    target.has_markings = record.has_markings
    target.has_signs = record.has_signs
    target.overall_quality = record.quality or None
    target.source = LEGACY_SOURCE
    target.external_id = record.external_id
    target.source_metadata = json.dumps(record.metadata, ensure_ascii=False, sort_keys=True)
    target.imported_at = target.imported_at or datetime.utcnow()


def _merge_into_osm(target, record):
    if _is_generated_title(target.title):
        target.title = record.title
    if _description_is_better(record.description, target.description):
        target.description = record.description
    if record.quality:
        target.quality = record.quality
        target.overall_quality = record.quality
    target.has_parking = target.has_parking or record.has_parking
    target.has_markings = target.has_markings or record.has_markings
    target.has_signs = target.has_signs or record.has_signs

    metadata = _load_metadata(target.source_metadata)
    metadata['legacy_velojol'] = record.metadata['legacy_velojol']
    target.source_metadata = json.dumps(metadata, ensure_ascii=False, sort_keys=True)


def _copy_record_photos(source_root, record, target):
    del source_root  # Paths were validated and resolved while the plan was built.
    if not record.photo_files:
        return 0
    destination = (
        Path(current_app.static_folder)
        / 'uploads'
        / 'bikelanes'
        / LEGACY_SOURCE
        / str(target.id)
    )
    destination.mkdir(parents=True, exist_ok=True)
    photos = target.get_photos_list()
    copied = 0
    prefix = f'uploads/bikelanes/{LEGACY_SOURCE}/{target.id}/'
    expected = set()

    for source in record.photo_files:
        if (
            not source.is_file()
            or source.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS
            or not _is_valid_image(source)
        ):
            continue
        digest = _file_digest(source)
        filename = f'{digest[:20]}{source.suffix.lower()}'
        destination_file = destination / filename
        relative = f'{prefix}{filename}'
        expected.add(relative)
        if not destination_file.exists():
            shutil.copy2(source, destination_file)
            copied += 1
        if relative not in photos:
            photos.append(relative)
    photos = [
        photo
        for photo in photos
        if not photo.startswith(prefix) or photo in expected
    ]
    target.set_photos_list(photos)
    return copied


def _copy_city_asset(source_root, city_id, legacy_name, kind):
    if not legacy_name:
        return None
    source_dir = source_root / 'static' / 'img' / 'city'
    legacy_path = Path(str(legacy_name))
    candidates = []
    if kind == 'bg':
        candidates.append(source_dir / f'{legacy_path.stem}_cover{legacy_path.suffix}')
    candidates.append(source_dir / legacy_path.name)
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        return None

    destination_dir = Path(current_app.static_folder) / 'uploads' / 'cities'
    destination_dir.mkdir(parents=True, exist_ok=True)
    filename = f'legacy_{city_id}_{kind}{source.suffix.lower()}'
    destination = destination_dir / filename
    if not destination.exists() or _file_digest(destination) != _file_digest(source):
        shutil.copy2(source, destination)
    return f'uploads/cities/{filename}'


def _legacy_photo_files(source_root, city_id, source_id):
    folder = source_root / 'static' / 'img' / 'bikelanes' / city_id / source_id
    if not folder.is_dir():
        return []
    return [
        path.resolve()
        for path in folder.iterdir()
        if (
            path.is_file()
            and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
            and _is_valid_image(path)
        )
    ]


def _normalize_coordinates(value):
    if not isinstance(value, list) or len(value) < 2:
        return None, 'Линия должна содержать минимум две координаты'
    normalized = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return None, 'Некорректная точка геометрии'
        try:
            lon = float(point[0])
            lat = float(point[1])
        except (TypeError, ValueError):
            return None, 'Координаты должны быть числами'
        if not math.isfinite(lon) or not math.isfinite(lat):
            return None, 'Координаты должны быть конечными числами'
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            return None, 'Координаты находятся вне допустимого диапазона'
        coordinate = [round(lon, 7), round(lat, 7)]
        if not normalized or coordinate != normalized[-1]:
            normalized.append(coordinate)
    if len(normalized) < 2:
        return None, 'Линия содержит меньше двух уникальных точек'
    return normalized, None


def _geometry_fingerprint(coordinates):
    forward = json.dumps(coordinates, separators=(',', ':'))
    backward = json.dumps(list(reversed(coordinates)), separators=(',', ':'))
    canonical = min(forward, backward)
    return sha256(canonical.encode('utf-8')).hexdigest()


def _record_richness(row):
    return (
        len(_clean_text(row.get('description'))) * 10
        + len(_clean_text(row.get('name')))
        + (_quality(row.get('safetyLevel')) * 100)
    )


def _quality(value):
    try:
        quality = int(value)
    except (TypeError, ValueError):
        return 0
    return quality if 1 <= quality <= 5 else 0


def _parse_legacy_date(value):
    text = _clean_text(value)
    if not text:
        return None
    for pattern in ('%d.%m.%y', '%d.%m.%Y'):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


def _clean_text(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _normalized_text(value):
    return _clean_text(value).casefold()


def _mentions_parking(description):
    text = _normalized_text(description)
    return any(
        token in text
        for token in ('паркуют', 'паркуются', 'парковк', 'припаркован')
    )


def _is_generated_title(value):
    text = _normalized_text(value)
    return (
        not text
        or text.startswith('велодорожка osm ')
        or text.startswith('велодорожка №')
    )


def _description_is_better(candidate, current):
    candidate_text = _clean_text(candidate)
    current_text = _clean_text(current)
    if not candidate_text:
        return False
    if _normalized_text(current_text) in GENERIC_DESCRIPTIONS:
        return len(candidate_text) > len(current_text)
    return len(candidate_text) >= len(current_text) + 20


def _load_metadata(value):
    if not value:
        return {}
    try:
        result = json.loads(value)
        return result if isinstance(result, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _file_digest(path):
    digest = sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _is_valid_image(path):
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError):
        return False


def _sample_line(coordinates, step_meters=20):
    lat0 = sum(float(point[1]) for point in coordinates) / len(coordinates)
    points = [_to_xy(point, lat0) for point in coordinates]
    samples = [points[0]]
    for start, end in zip(points, points[1:]):
        distance = math.hypot(end[0] - start[0], end[1] - start[1])
        steps = max(1, math.ceil(distance / step_meters))
        samples.extend([
            (
                start[0] + (end[0] - start[0]) * index / steps,
                start[1] + (end[1] - start[1]) * index / steps,
            )
            for index in range(1, steps + 1)
        ])
    return samples


def _to_xy(point, latitude):
    return (
        float(point[0]) * 111_320 * math.cos(math.radians(latitude)),
        float(point[1]) * 110_540,
    )


def _line_coverage(source_samples, target_samples, tolerance_meters):
    segments = list(zip(target_samples, target_samples[1:]))
    if not source_samples or not segments:
        return 0.0
    covered = sum(
        min(_point_segment_distance(point, start, end) for start, end in segments)
        <= tolerance_meters
        for point in source_samples
    )
    return covered / len(source_samples)


def _point_segment_distance(point, start, end):
    vector_x = end[0] - start[0]
    vector_y = end[1] - start[1]
    offset_x = point[0] - start[0]
    offset_y = point[1] - start[1]
    denominator = vector_x * vector_x + vector_y * vector_y
    ratio = 0.0 if denominator == 0 else (
        (offset_x * vector_x + offset_y * vector_y) / denominator
    )
    ratio = max(0.0, min(1.0, ratio))
    projection = (
        start[0] + ratio * vector_x,
        start[1] + ratio * vector_y,
    )
    return math.hypot(point[0] - projection[0], point[1] - projection[1])
