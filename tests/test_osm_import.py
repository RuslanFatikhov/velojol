import json
import unittest

from app import create_app, db
from app.models.bikelane import BikeLane
from app.models.city import City
from app.models.infrastructure_point import InfrastructurePoint
from app.services.osm_import import (
    OsmImportError,
    build_osm_description,
    import_osm_bikelanes,
    import_osm_infrastructure,
    map_osm_tags_to_track_type,
    preview_osm_bikelanes,
    preview_osm_infrastructure,
)
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


def overpass_payload(osm_id=1001, tags=None, geometry=None):
    return {
        'elements': [
            {
                'type': 'way',
                'id': osm_id,
                'tags': tags or {'highway': 'cycleway', 'surface': 'asphalt'},
                'geometry': geometry or [
                    {'lat': 43.2500, 'lon': 76.9000},
                    {'lat': 43.2510, 'lon': 76.9010},
                ],
            }
        ]
    }


def combined_overpass_payload(*payloads):
    return {
        'elements': [
            element
            for payload in payloads
            for element in payload['elements']
        ]
    }


def infrastructure_payload():
    return {
        'elements': [
            {
                'type': 'node',
                'id': 3001,
                'lat': 43.2505,
                'lon': 76.9005,
                'tags': {
                    'amenity': 'bicycle_parking',
                    'capacity': '12',
                    'covered': 'yes',
                    'bicycle_parking': 'stands',
                    'operator': 'Алматы паркинг',
                    'cargo_bike': 'designated',
                    'capacity:cargo_bike': '2',
                    'maxstay': '24 hours',
                    'surveillance': 'camera',
                },
            },
            {
                'type': 'way',
                'id': 3002,
                'center': {'lat': 43.2510, 'lon': 76.9010},
                'tags': {
                    'amenity': 'bicycle_repair_station',
                    'name': 'Bike Fix',
                    'description': 'Насос и набор инструментов',
                    'service:bicycle:pump': 'yes',
                    'service:bicycle:tools': 'yes',
                    'service:bicycle:chain_tool': 'no',
                    'service:bicycle:stand': 'yes',
                    'service:bicycle:charging': 'no',
                    'brand': 'Bike Fixstation',
                    'opening_hours': '24/7',
                    'lastcheck:status': 'working',
                },
            },
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
        self.assertEqual(map_osm_tags_to_track_type({'cycleway:right': ' Lane '}), 'lane')
        self.assertEqual(map_osm_tags_to_track_type({'cycleway:left': 'LANE'}), 'lane')

    def test_builds_semantic_descriptions(self):
        examples = [
            (
                {'cycleway:right': 'lane', 'cycleway:left': 'lane'},
                'Велополосы с обеих сторон улицы',
                'lane',
            ),
            (
                {'cycleway:right': ' Lane ', 'cycleway:left': ' no '},
                'Велополоса с правой стороны улицы',
                'lane',
            ),
            (
                {'cycleway:right': 'no', 'cycleway:left': 'LANE'},
                'Велополоса с левой стороны улицы',
                'lane',
            ),
            (
                {'highway': 'footway', 'bicycle': 'designated'},
                'Велопешеходная дорожка',
                'shared',
            ),
            (
                {'highway': ' CYCLEWAY '},
                'Обособленная велодорожка',
                'separated',
            ),
            ({'cycleway': 'lane'}, 'Велополоса', 'lane'),
        ]

        for tags, description, track_type in examples:
            with self.subTest(tags=tags):
                self.assertEqual(build_osm_description(tags), description)
                self.assertEqual(map_osm_tags_to_track_type(tags), track_type)

    def test_preview_does_not_write_to_database(self):
        queries = []

        def fetch(query):
            queries.append(query)
            payload = overpass_payload()
            payload['elements'].append({
                'type': 'count',
                'tags': {'areas': '1', 'total': '1'},
            })
            return payload

        result = preview_osm_bikelanes(
            'almaty',
            limit=10,
            fetcher=fetch,
        )

        self.assertEqual(result['found'], 1)
        self.assertEqual(result['importable'], 1)
        self.assertEqual(result['errors'], [])
        self.assertEqual(BikeLane.query.count(), 0)
        self.assertIn(
            'is_in(43.250000,76.900000)->.containingAreas;',
            queries[0],
        )
        self.assertIn(
            'area.containingAreas["boundary"="administrative"]'
            '["name"="Алматы"];',
            queries[0],
        )
        self.assertIn(
            'way["highway"="cycleway"](area.searchArea);',
            queries[0],
        )
        self.assertIn('.searchArea out count;', queries[0])

    def test_preview_fails_when_city_admin_area_is_not_found(self):
        payload = {
            'elements': [
                {
                    'type': 'count',
                    'tags': {
                        'nodes': '0',
                        'ways': '0',
                        'relations': '0',
                        'areas': '0',
                        'total': '0',
                    },
                },
            ],
        }

        with self.assertRaisesRegex(
            OsmImportError,
            'Административная граница города «Алматы» не найдена в OSM',
        ):
            preview_osm_bikelanes(
                'almaty',
                fetcher=lambda query: payload,
            )

    def test_imports_bicycle_parking_and_repair_stations_without_duplicates(self):
        queries = []

        def fetch_infrastructure(query):
            queries.append(query)
            return infrastructure_payload()

        preview = preview_osm_infrastructure(
            'almaty',
            limit=10,
            fetcher=fetch_infrastructure,
        )
        imported = import_osm_infrastructure(
            'almaty',
            limit=10,
            fetcher=fetch_infrastructure,
        )
        repeated = import_osm_infrastructure(
            'almaty',
            limit=10,
            fetcher=fetch_infrastructure,
        )

        self.assertEqual(preview['found'], 2)
        self.assertEqual(preview['importable'], 2)
        self.assertEqual(imported['imported'], 2)
        self.assertEqual(repeated['imported'], 0)
        self.assertEqual(repeated['duplicates'], 2)
        self.assertEqual(InfrastructurePoint.query.count(), 2)
        self.assertTrue(all(
            'node["amenity"="bicycle_parking"]' in query
            and 'node["amenity"="bicycle_repair_station"]' in query
            and '(area.searchArea)' in query
            and 'out center' in query
            for query in queries
        ))

        parking = InfrastructurePoint.query.filter_by(osm_id='3001').one()
        repair = InfrastructurePoint.query.filter_by(osm_id='3002').one()
        self.assertEqual(parking.infrastructure_type, 'bicycle_parking')
        self.assertEqual(parking.to_dict()['capacity'], '12')
        self.assertEqual(parking.to_dict()['covered'], 'yes')
        parking_attributes = {
            attribute['key']: attribute['value']
            for attribute in parking.to_dict()['attributes']
        }
        self.assertEqual(parking_attributes['bicycle_parking'], 'stands')
        self.assertEqual(parking_attributes['operator'], 'Алматы паркинг')
        self.assertEqual(parking_attributes['cargo_bike'], 'designated')
        self.assertEqual(parking_attributes['capacity:cargo_bike'], '2')
        self.assertEqual(parking_attributes['maxstay'], '24 hours')
        self.assertEqual(parking_attributes['surveillance'], 'camera')
        self.assertEqual(repair.infrastructure_type, 'bicycle_repair_station')
        self.assertEqual(repair.title, 'Bike Fix')
        self.assertEqual(repair.description, 'Насос и набор инструментов')
        repair_attributes = {
            attribute['key']: attribute['value']
            for attribute in repair.to_dict()['attributes']
        }
        self.assertEqual(repair_attributes['service:bicycle:pump'], 'yes')
        self.assertEqual(repair_attributes['service:bicycle:tools'], 'yes')
        self.assertEqual(repair_attributes['service:bicycle:chain_tool'], 'no')
        self.assertEqual(repair_attributes['service:bicycle:stand'], 'yes')
        self.assertEqual(repair_attributes['service:bicycle:charging'], 'no')
        self.assertEqual(repair_attributes['brand'], 'Bike Fixstation')
        self.assertEqual(repair_attributes['lastcheck:status'], 'working')
        repair.set_photos_list(['uploads/infrastructure/2/example.jpg'])
        self.assertEqual(
            repair.to_dict()['photos'],
            ['uploads/infrastructure/2/example.jpg'],
        )
        self.assertEqual(repair.latitude, 43.2510)
        self.assertEqual(repair.longitude, 76.9010)

        db.session.commit()
        response = self.app.test_client().get(
            f'/api/infrastructure/{repair.id}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()['infrastructure']['description'],
            'Насос и набор инструментов',
        )

    def test_imports_only_selected_infrastructure_type(self):
        queries = []

        def fetch_infrastructure(query):
            queries.append(query)
            return infrastructure_payload()

        preview = preview_osm_infrastructure(
            'almaty',
            fetcher=fetch_infrastructure,
            infrastructure_types={InfrastructurePoint.TYPE_BICYCLE_PARKING},
        )
        result = import_osm_infrastructure(
            'almaty',
            fetcher=fetch_infrastructure,
            infrastructure_types={InfrastructurePoint.TYPE_BICYCLE_PARKING},
        )

        self.assertEqual(preview['found'], 1)
        self.assertEqual(preview['importable'], 1)
        self.assertEqual(result['imported'], 1)
        self.assertEqual(InfrastructurePoint.query.count(), 1)
        self.assertEqual(
            InfrastructurePoint.query.one().infrastructure_type,
            InfrastructurePoint.TYPE_BICYCLE_PARKING,
        )
        self.assertTrue(all(
            '["amenity"="bicycle_parking"]' in query
            and '["amenity"="bicycle_repair_station"]' not in query
            for query in queries
        ))

    def test_minimum_line_length_is_ten_meters(self):
        payload = combined_overpass_payload(
            overpass_payload(
                1101,
                geometry=[
                    {'lat': 43.2500, 'lon': 76.9000},
                    {'lat': 43.2501, 'lon': 76.9000},
                ],
            ),
            overpass_payload(
                1102,
                geometry=[
                    {'lat': 43.2500, 'lon': 76.9000},
                    {'lat': 43.25008, 'lon': 76.9000},
                ],
            ),
        )

        preview = preview_osm_bikelanes('almaty', fetcher=lambda query: payload)
        imported = import_osm_bikelanes('almaty', fetcher=lambda query: payload)

        self.assertEqual(preview['found'], 1)
        self.assertEqual(preview['importable'], 1)
        self.assertIn('way/1102: линия короче 10 м', preview['errors'])
        self.assertEqual(imported['imported'], 1)
        self.assertIn('way/1102: линия короче 10 м', imported['errors'])
        self.assertIsNotNone(BikeLane.query.filter_by(osm_id='1101').first())
        self.assertIsNone(BikeLane.query.filter_by(osm_id='1102').first())

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

    def test_import_merges_connected_ways_and_remembers_all_osm_ids(self):
        tags = {'highway': 'cycleway', 'surface': 'asphalt'}
        payload = combined_overpass_payload(
            overpass_payload(
                1201,
                tags,
                geometry=[
                    {'lat': 43.2500, 'lon': 76.9000},
                    {'lat': 43.2510, 'lon': 76.9010},
                ],
            ),
            overpass_payload(
                1202,
                tags,
                geometry=[
                    {'lat': 43.2520, 'lon': 76.9020},
                    {'lat': 43.2510, 'lon': 76.9010},
                ],
            ),
        )

        preview = preview_osm_bikelanes('almaty', fetcher=lambda query: payload)
        imported = import_osm_bikelanes('almaty', fetcher=lambda query: payload)
        repeated = import_osm_bikelanes('almaty', fetcher=lambda query: payload)

        self.assertEqual(preview['found'], 1)
        self.assertEqual(preview['importable'], 1)
        self.assertEqual(imported['imported'], 1)
        self.assertEqual(repeated['imported'], 0)
        self.assertEqual(repeated['duplicates'], 1)
        self.assertEqual(BikeLane.query.count(), 1)

        bikelane = BikeLane.query.one()
        geometry = json.loads(bikelane.geometry)
        self.assertEqual(
            geometry['coordinates'],
            [
                [76.9, 43.25],
                [76.901, 43.251],
                [76.902, 43.252],
            ],
        )
        metadata = json.loads(bikelane.source_metadata)
        self.assertEqual(
            metadata['osm_import']['member_keys'],
            [
                {'type': 'way', 'id': '1201'},
                {'type': 'way', 'id': '1202'},
            ],
        )

    def test_import_does_not_merge_through_a_branch(self):
        tags = {'highway': 'cycleway', 'surface': 'asphalt'}
        center = {'lat': 43.2510, 'lon': 76.9010}
        payload = combined_overpass_payload(
            overpass_payload(
                1211,
                tags,
                geometry=[
                    {'lat': 43.2500, 'lon': 76.9000},
                    center,
                ],
            ),
            overpass_payload(
                1212,
                tags,
                geometry=[
                    center,
                    {'lat': 43.2520, 'lon': 76.9020},
                ],
            ),
            overpass_payload(
                1213,
                tags,
                geometry=[
                    center,
                    {'lat': 43.2510, 'lon': 76.9030},
                ],
            ),
        )

        preview = preview_osm_bikelanes('almaty', fetcher=lambda query: payload)

        self.assertEqual(preview['found'], 3)
        self.assertEqual(preview['importable'], 3)

    def test_import_does_not_merge_connected_ways_with_different_tags(self):
        payload = combined_overpass_payload(
            overpass_payload(
                1221,
                {'highway': 'cycleway', 'surface': 'asphalt'},
                geometry=[
                    {'lat': 43.2500, 'lon': 76.9000},
                    {'lat': 43.2510, 'lon': 76.9010},
                ],
            ),
            overpass_payload(
                1222,
                {'highway': 'cycleway', 'surface': 'concrete'},
                geometry=[
                    {'lat': 43.2510, 'lon': 76.9010},
                    {'lat': 43.2520, 'lon': 76.9020},
                ],
            ),
        )

        preview = preview_osm_bikelanes('almaty', fetcher=lambda query: payload)

        self.assertEqual(preview['found'], 2)
        self.assertEqual(preview['importable'], 2)

    def test_existing_way_does_not_block_new_connected_way(self):
        tags = {'highway': 'cycleway', 'surface': 'asphalt'}
        first = overpass_payload(
            1231,
            tags,
            geometry=[
                {'lat': 43.2500, 'lon': 76.9000},
                {'lat': 43.2510, 'lon': 76.9010},
            ],
        )
        second = overpass_payload(
            1232,
            tags,
            geometry=[
                {'lat': 43.2510, 'lon': 76.9010},
                {'lat': 43.2520, 'lon': 76.9020},
            ],
        )
        import_osm_bikelanes('almaty', fetcher=lambda query: first)

        result = import_osm_bikelanes(
            'almaty',
            fetcher=lambda query: combined_overpass_payload(first, second),
        )

        self.assertEqual(result['imported'], 1)
        self.assertEqual(result['duplicates'], 1)
        self.assertEqual(BikeLane.query.count(), 2)
        self.assertIsNotNone(BikeLane.query.filter_by(osm_id='1232').first())

    def test_import_limit_counts_new_records_after_leading_duplicates(self):
        import_osm_bikelanes(
            'almaty',
            limit=1,
            fetcher=lambda query: overpass_payload(1001),
        )
        payload = combined_overpass_payload(
            overpass_payload(1001),
            overpass_payload(1002),
        )
        queries = []

        def fetch_candidates(query):
            queries.append(query)
            return payload

        preview = preview_osm_bikelanes(
            'almaty',
            limit=1,
            fetcher=fetch_candidates,
        )
        result = import_osm_bikelanes(
            'almaty',
            limit=1,
            fetcher=fetch_candidates,
        )

        self.assertEqual(preview['found'], 2)
        self.assertEqual(preview['existing'], 1)
        self.assertEqual(preview['importable'], 1)
        self.assertEqual(result['imported'], 1)
        self.assertEqual(result['duplicates'], 1)
        self.assertEqual(BikeLane.query.count(), 2)
        self.assertIsNotNone(BikeLane.query.filter_by(osm_id='1002').first())
        self.assertTrue(all('out geom 1000;' in query for query in queries))

    def test_bicycle_no_is_skipped_in_preview_and_import(self):
        payload = overpass_payload(
            1901,
            {'highway': 'cycleway', 'bicycle': ' No '},
        )
        preview = preview_osm_bikelanes('almaty', fetcher=lambda query: payload)
        imported = import_osm_bikelanes('almaty', fetcher=lambda query: payload)

        self.assertEqual(preview['found'], 0)
        self.assertEqual(preview['importable'], 0)
        self.assertIn('way/1901: bicycle=no', preview['errors'])
        self.assertEqual(imported['imported'], 0)
        self.assertIn('way/1901: bicycle=no', imported['errors'])
        self.assertEqual(BikeLane.query.count(), 0)

    def test_cycleway_no_tags_are_skipped_in_preview_and_import(self):
        excluded_tags = (
            ('cycleway', ' no '),
            ('cycleway:right', 'No'),
            ('cycleway:both', 'NO'),
            ('cycleway:left', 'NO'),
        )

        for index, (tag_name, tag_value) in enumerate(excluded_tags, start=1):
            osm_id = 1910 + index
            payload = overpass_payload(
                osm_id,
                {'highway': 'residential', tag_name: tag_value},
            )

            with self.subTest(tag_name=tag_name):
                preview = preview_osm_bikelanes('almaty', fetcher=lambda query: payload)
                imported = import_osm_bikelanes('almaty', fetcher=lambda query: payload)

                self.assertEqual(preview['found'], 0)
                self.assertEqual(preview['importable'], 0)
                self.assertIn(f'way/{osm_id}: {tag_name}=no', preview['errors'])
                self.assertEqual(imported['imported'], 0)
                self.assertIn(f'way/{osm_id}: {tag_name}=no', imported['errors'])

        self.assertEqual(BikeLane.query.count(), 0)

    def test_cycleway_separate_tags_are_skipped_in_preview_and_import(self):
        excluded_tags = (
            ('cycleway', ' separate '),
            ('cycleway:right', 'Separate'),
            ('cycleway:both', 'SEPARATE'),
            ('cycleway:left', 'separate'),
        )

        for index, (tag_name, tag_value) in enumerate(excluded_tags, start=1):
            osm_id = 1920 + index
            payload = overpass_payload(
                osm_id,
                {'highway': 'cycleway', tag_name: tag_value},
            )

            with self.subTest(tag_name=tag_name):
                preview = preview_osm_bikelanes('almaty', fetcher=lambda query: payload)
                imported = import_osm_bikelanes('almaty', fetcher=lambda query: payload)

                self.assertEqual(preview['found'], 0)
                self.assertEqual(preview['importable'], 0)
                self.assertIn(f'way/{osm_id}: {tag_name}=separate', preview['errors'])
                self.assertEqual(imported['imported'], 0)
                self.assertIn(f'way/{osm_id}: {tag_name}=separate', imported['errors'])

        self.assertEqual(BikeLane.query.count(), 0)

    def test_import_creates_bikelane_with_geojson_linestring(self):
        result = import_osm_bikelanes(
            'almaty',
            limit=10,
            fetcher=lambda query: overpass_payload(
                2002,
                {'cycleway': 'lane', 'name': 'Test lane', 'oneway': 'yes'},
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
        self.assertEqual(bikelane.title, 'Test lane')
        self.assertEqual(bikelane.description, 'Велополоса')
        self.assertTrue(bikelane.is_one_way)
        self.assertNotIn('OpenStreetMap', bikelane.description)
        self.assertNotIn('Теги:', bikelane.description)
        self.assertEqual(json.loads(bikelane.osm_tags)['cycleway'], 'lane')

    def test_imports_bus_lane_with_reduced_characteristics(self):
        queries = []
        payload = overpass_payload(
            2010,
            {
                'highway': 'primary',
                'name': 'Проспект Абая',
                'lanes:bus:forward': '1',
            },
        )

        def fetch_bus_lane(query):
            queries.append(query)
            return payload

        result = import_osm_bikelanes(
            'almaty',
            fetcher=fetch_bus_lane,
        )

        self.assertEqual(result['imported'], 1)
        self.assertTrue(all(
            'way["lanes:bus"]' in query
            and 'way["bus:lanes"]' in query
            and 'way["highway"="busway"]' in query
            for query in queries
        ))
        bus_lane = BikeLane.query.one()
        self.assertEqual(bus_lane.track_type, 'bus_lane')
        self.assertEqual(bus_lane.title, 'Проспект Абая')
        self.assertEqual(bus_lane.description, '')
        self.assertEqual(bus_lane.quality, 0)
        self.assertEqual(bus_lane.overall_quality, None)
        self.assertEqual(bus_lane.quality_color, '#3498db')

    def test_imports_only_selected_line_type(self):
        queries = []
        payload = combined_overpass_payload(
            overpass_payload(
                2011,
                {'highway': 'cycleway', 'name': 'Велодорожка'},
            ),
            overpass_payload(
                2012,
                {
                    'highway': 'primary',
                    'name': 'Автобусная полоса',
                    'lanes:bus:forward': '1',
                },
            ),
        )

        def fetch_bus_lanes(query):
            queries.append(query)
            return payload

        preview = preview_osm_bikelanes(
            'almaty',
            fetcher=fetch_bus_lanes,
            include_bikelanes=False,
            include_bus_lanes=True,
        )
        result = import_osm_bikelanes(
            'almaty',
            fetcher=fetch_bus_lanes,
            include_bikelanes=False,
            include_bus_lanes=True,
        )

        self.assertEqual(preview['found'], 1)
        self.assertEqual(preview['bus_lanes_found'], 1)
        self.assertEqual(result['imported'], 1)
        self.assertEqual(BikeLane.query.count(), 1)
        self.assertEqual(BikeLane.query.one().track_type, 'bus_lane')
        self.assertTrue(all(
            'way["highway"="busway"]' in query
            and 'way["highway"="cycleway"]' not in query
            for query in queries
        ))

    def test_bicycle_designated_is_requested_and_imported(self):
        queries = []
        payload = overpass_payload(
            2004,
            {
                'highway': 'path',
                'bicycle': 'designated',
                'name': 'Designated bicycle path',
            },
        )

        def fetch_designated(query):
            queries.append(query)
            return payload

        preview = preview_osm_bikelanes('almaty', fetcher=fetch_designated)
        result = import_osm_bikelanes('almaty', fetcher=fetch_designated)

        self.assertEqual(preview['found'], 1)
        self.assertEqual(preview['importable'], 1)
        self.assertEqual(result['imported'], 1)
        self.assertTrue(all('way["bicycle"="designated"]' in query for query in queries))
        bikelane = BikeLane.query.filter_by(osm_id='2004').one()
        self.assertEqual(bikelane.track_type, 'shared')
        self.assertEqual(json.loads(bikelane.osm_tags)['bicycle'], 'designated')

    def test_unnamed_import_uses_database_id_for_title(self):
        result = import_osm_bikelanes(
            'almaty',
            fetcher=lambda query: overpass_payload(2003, {'highway': 'cycleway', 'name': '  '}),
        )

        self.assertEqual(result['imported'], 1)
        bikelane = BikeLane.query.one()
        self.assertEqual(bikelane.title, f'Велодорожка №{bikelane.id}')
        self.assertLessEqual(len(bikelane.title), 200)


if __name__ == '__main__':
    unittest.main()
