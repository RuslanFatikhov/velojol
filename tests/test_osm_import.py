import json
import unittest

from app import create_app, db
from app.models.bikelane import BikeLane
from app.models.city import City
from app.services.osm_import import (
    import_osm_bikelanes,
    map_osm_tags_to_track_type,
    preview_osm_bikelanes,
)
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


def overpass_payload(osm_id=1001, tags=None):
    return {
        'elements': [
            {
                'type': 'way',
                'id': osm_id,
                'tags': tags or {'highway': 'cycleway', 'surface': 'asphalt'},
                'geometry': [
                    {'lat': 43.2500, 'lon': 76.9000},
                    {'lat': 43.2510, 'lon': 76.9010},
                ],
            }
        ]
    }


class OsmImportTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.city = City(
            city_id='almaty',
            name='Алматы',
            country='Kazakhstan',
            coords_lat=43.25,
            coords_lng=76.9,
            zoom=12,
            status='active',
        )
        db.session.add(self.city)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_maps_osm_tags_to_track_type(self):
        self.assertEqual(map_osm_tags_to_track_type({'highway': 'cycleway'}), 'separated')
        self.assertEqual(map_osm_tags_to_track_type({'cycleway': 'track'}), 'separated')
        self.assertEqual(map_osm_tags_to_track_type({'cycleway': 'lane'}), 'lane')
        self.assertEqual(map_osm_tags_to_track_type({'segregated': 'yes'}), 'shared')
        self.assertEqual(
            map_osm_tags_to_track_type({'foot': 'designated', 'bicycle': 'designated'}),
            'shared'
        )

    def test_preview_does_not_write_to_database(self):
        result = preview_osm_bikelanes(
            'almaty',
            limit=10,
            fetcher=lambda query: overpass_payload(),
        )

        self.assertEqual(result['found'], 1)
        self.assertEqual(result['importable'], 1)
        self.assertEqual(BikeLane.query.count(), 0)

    def test_import_deduplicates_by_osm_type_and_id(self):
        import_osm_bikelanes('almaty', limit=10, fetcher=lambda query: overpass_payload(1001))
        second_result = import_osm_bikelanes(
            'almaty',
            limit=10,
            fetcher=lambda query: overpass_payload(1001),
        )

        self.assertEqual(BikeLane.query.count(), 1)
        self.assertEqual(second_result['imported'], 0)
        self.assertEqual(second_result['duplicates'], 1)

    def test_import_creates_bikelane_with_geojson_linestring(self):
        result = import_osm_bikelanes(
            'almaty',
            limit=10,
            fetcher=lambda query: overpass_payload(
                2002,
                {'cycleway': 'lane', 'name': 'Test lane'},
            ),
        )

        self.assertEqual(result['imported'], 1)
        bikelane = BikeLane.query.one()
        geometry = json.loads(bikelane.geometry)
        self.assertEqual(geometry['type'], 'LineString')
        self.assertGreaterEqual(len(geometry['coordinates']), 2)
        self.assertEqual(bikelane.source, 'openstreetmap')
        self.assertEqual(bikelane.osm_type, 'way')
        self.assertEqual(bikelane.osm_id, '2002')
        self.assertEqual(bikelane.track_type, 'lane')


if __name__ == '__main__':
    unittest.main()
