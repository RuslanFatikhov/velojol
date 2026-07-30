import json
import unittest

from app import create_app, db
from app.models.bikelane import BikeLane
from app.models.city import City
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAPBOX_TOKEN = 'pk.test-public-token'


class CityDistanceStatsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

        self.city = City(
            city_id='almaty',
            name='Алматы',
            country='Казахстан',
            coords_lat=43.25,
            coords_lng=76.9,
            zoom=12,
            status='active',
        )
        db.session.add(self.city)
        db.session.flush()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _add_line(self, track_type, coordinates, status='approved'):
        line = BikeLane(
            title=track_type,
            description='Тестовая линия',
            city_id=self.city.id,
            city=self.city.city_id,
            geometry=json.dumps({
                'type': 'LineString',
                'coordinates': coordinates,
            }),
            track_type=track_type,
            quality=4 if track_type != 'bus_lane' else 0,
            status=status,
        )
        db.session.add(line)
        return line

    def test_city_page_shows_distance_breakdown_in_tooltip(self):
        bikelane = self._add_line(
            'lane',
            [[76.9, 43.25], [76.901, 43.251]],
        )
        bus_lane = self._add_line(
            'bus_lane',
            [[76.9, 43.25], [76.902, 43.252]],
        )
        self._add_line(
            'lane',
            [[76.9, 43.25], [76.91, 43.26]],
            status='pending',
        )
        db.session.commit()

        response = self.client.get('/city/almaty')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('class="city-distance-tooltip"', body)
        self.assertIn('Автобусные полосы', body)
        self.assertIn('Велодорожки', body)
        self.assertIn(f'{bus_lane.calculate_length()} км', body)
        self.assertIn(f'{bikelane.calculate_length()} км', body)

        breakdown = self.city.get_distance_breakdown()
        self.assertEqual(
            breakdown['total'],
            round(breakdown['bus_lanes'] + breakdown['bikelanes'], 2),
        )


if __name__ == '__main__':
    unittest.main()
