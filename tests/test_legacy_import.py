import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from app import create_app, db
from app.models.bikelane import BikeLane
from app.models.city import City
from app.services.legacy_import import (
    LEGACY_SOURCE,
    apply_legacy_import_plan,
    build_legacy_import_plan,
    infer_legacy_track_type,
)
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class LegacyImportTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp_dir.name)
        self.legacy_root = self.temp_root / 'public_html'
        self.static_root = self.temp_root / 'new-static'
        self._write_json(
            self.legacy_root / 'static/data/cities.json',
            [{
                'id': 'almaty',
                'city': 'Алматы',
                'country': 'Казахстан',
                'coordinates': [76.9, 43.25],
                'zoom': 11,
                'coat': 'almaty.png',
                'cover': 'almaty.jpg',
            }],
        )
        city_assets = self.legacy_root / 'static/img/city'
        city_assets.mkdir(parents=True, exist_ok=True)
        (city_assets / 'almaty.png').write_bytes(b'coat')
        (city_assets / 'almaty_cover.jpg').write_bytes(b'cover')

        self.app = create_app(TestConfig)
        self.app.static_folder = str(self.static_root)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def _write_json(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding='utf-8',
        )

    def _write_lanes(self, rows):
        self._write_json(
            self.legacy_root / 'static/data/cities/almaty.json',
            rows,
        )

    def _photo(self, source_id, name='1.jpg', content=b'photo'):
        path = self.legacy_root / 'static/img/bikelanes/almaty' / source_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        color = (len(content) % 255, 40, 80)
        Image.new('RGB', (2, 2), color=color).save(path, 'JPEG')
        return path

    @staticmethod
    def _row(source_id='alm01', coordinates=None, **overrides):
        row = {
            'id': source_id,
            'name': 'Жибек Жолы',
            'description': 'Обособленная велодорожка с разметкой и знаками',
            'coordinates': coordinates or [[76.9, 43.25], [76.901, 43.251]],
            'distance': 150,
            'safetyLevel': 5,
            'source': 'Velojol',
            'date': '04.10.23',
        }
        row.update(overrides)
        return row

    def test_dry_run_collapses_exact_geometry_duplicates_without_writes(self):
        first = self._row('alm01')
        second = self._row(
            'alm02',
            coordinates=list(reversed(first['coordinates'])),
            name='Более полное название',
            description='Более подробное описание обособленной велодорожки с разметкой',
        )
        self._write_lanes([first, second])

        plan = build_legacy_import_plan(self.legacy_root)

        self.assertEqual(plan.summary['new'], 1)
        self.assertEqual(plan.summary['records'], 1)
        self.assertEqual(BikeLane.query.count(), 0)
        item = plan.items[0]
        self.assertEqual(len(item.record.raw_records), 2)
        self.assertIn('Объединено точных геометрических дублей', item.record.issues[0])

    def test_apply_creates_city_lane_assets_and_is_repeatable(self):
        self._write_lanes([self._row()])
        self._photo('alm01')

        first_plan = build_legacy_import_plan(self.legacy_root)
        first_result = apply_legacy_import_plan(first_plan)

        self.assertEqual(first_result['created'], 1)
        self.assertEqual(first_result['photos_copied'], 1)
        self.assertEqual(City.query.count(), 1)
        lane = BikeLane.query.one()
        self.assertEqual(lane.source, LEGACY_SOURCE)
        self.assertEqual(lane.status, 'approved')
        self.assertEqual(lane.track_type, 'separated')
        self.assertTrue(lane.external_id.startswith('almaty:alm01:'))
        self.assertEqual(len(lane.get_photos_list()), 1)
        photo = self.static_root / lane.get_photos_list()[0]
        self.assertTrue(photo.is_file())
        city = City.query.one()
        self.assertTrue(city.coat_of_arms.startswith('uploads/cities/legacy_almaty'))
        self.assertTrue(city.background_image.startswith('uploads/cities/legacy_almaty'))

        second_plan = build_legacy_import_plan(self.legacy_root)
        self.assertEqual(second_plan.summary['refresh_legacy'], 1)
        second_result = apply_legacy_import_plan(second_plan)

        self.assertEqual(second_result['created'], 0)
        self.assertEqual(second_result['refreshed'], 1)
        self.assertEqual(second_result['photos_copied'], 0)
        self.assertEqual(BikeLane.query.count(), 1)
        self.assertEqual(len(BikeLane.query.one().get_photos_list()), 1)

    def test_unique_osm_match_merges_content_but_preserves_osm_identity(self):
        row = self._row(
            name='Улица Достык',
            description='Обособленная велодорожка с яркой разметкой и знаками',
            safetyLevel=4,
        )
        self._write_lanes([row])
        self._photo('alm01')
        city = City(
            city_id='almaty',
            name='Алматы',
            country='Казахстан',
            coords_lat=43.25,
            coords_lng=76.9,
            zoom=11,
            status='active',
        )
        db.session.add(city)
        db.session.flush()
        geometry = json.dumps({
            'type': 'LineString',
            'coordinates': row['coordinates'],
        })
        osm = BikeLane(
            title='Велодорожка OSM way/100',
            description='Велодорожка',
            city_id=city.id,
            city='almaty',
            geometry=geometry,
            track_type='separated',
            quality=3,
            has_parking=False,
            has_markings=False,
            has_signs=False,
            status='pending',
            photos='[]',
            videos='[]',
            source='openstreetmap',
            osm_type='way',
            osm_id='100',
        )
        db.session.add(osm)
        db.session.commit()

        plan = build_legacy_import_plan(self.legacy_root)
        self.assertEqual(plan.summary['merge_osm'], 1)
        result = apply_legacy_import_plan(plan)

        self.assertEqual(result['merged_osm'], 1)
        db.session.refresh(osm)
        self.assertEqual(BikeLane.query.count(), 1)
        self.assertEqual(osm.source, 'openstreetmap')
        self.assertEqual(osm.osm_type, 'way')
        self.assertEqual(osm.osm_id, '100')
        self.assertEqual(osm.geometry, geometry)
        self.assertEqual(osm.status, 'pending')
        self.assertEqual(osm.title, 'Улица Достык')
        self.assertEqual(osm.quality, 4)
        self.assertTrue(osm.has_markings)
        self.assertTrue(osm.has_signs)
        self.assertEqual(len(osm.get_photos_list()), 1)
        metadata = json.loads(osm.source_metadata)
        self.assertTrue(metadata['legacy_velojol']['external_id'].startswith('almaty:alm01:'))

        second_plan = build_legacy_import_plan(self.legacy_root)
        self.assertEqual(second_plan.summary['merge_osm'], 1)
        second_result = apply_legacy_import_plan(second_plan)

        self.assertEqual(second_result['merged_osm'], 1)
        db.session.refresh(osm)
        self.assertEqual(BikeLane.query.count(), 1)
        self.assertEqual(osm.source, 'openstreetmap')
        self.assertEqual(osm.osm_id, '100')
        self.assertEqual(osm.geometry, geometry)
        self.assertEqual(osm.status, 'pending')

    def test_repeated_id_with_different_geometry_does_not_attach_ambiguous_photos(self):
        self._write_lanes([
            self._row('same'),
            self._row('same', coordinates=[[76.91, 43.25], [76.92, 43.26]]),
        ])
        self._photo('same')

        plan = build_legacy_import_plan(self.legacy_root)

        self.assertEqual(plan.summary['new'], 2)
        for item in plan.items:
            self.assertEqual(item.record.photo_files, [])
            self.assertTrue(any('Фото для повторяющегося ID' in issue for issue in item.record.issues))

    def test_invalid_geometry_is_reported_and_never_applied(self):
        self._write_lanes([self._row(coordinates=[[76.9, 43.25]])])

        plan = build_legacy_import_plan(self.legacy_root)
        result = apply_legacy_import_plan(plan)

        self.assertEqual(plan.summary['invalid'], 1)
        self.assertEqual(result['invalid'], 1)
        self.assertEqual(BikeLane.query.count(), 0)

    def test_track_type_inference_is_conservative(self):
        self.assertEqual(infer_legacy_track_type('Полоса с боллардами'), 'bollards')
        self.assertEqual(infer_legacy_track_type('Обычная велополоса'), 'lane')
        self.assertEqual(infer_legacy_track_type('Велопешеходная дорожка'), 'shared')
        self.assertEqual(infer_legacy_track_type('Обособленная дорожка'), 'separated')
        self.assertEqual(infer_legacy_track_type('Нет подробностей'), 'shared')


if __name__ == '__main__':
    unittest.main()
