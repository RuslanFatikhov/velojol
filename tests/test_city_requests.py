import unittest

from app import create_app, db
from app.models.city import City
from app.models.city_request import CityRequest
from app.models.user import User
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class CityRequestsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

        self.admin = User(
            email='admin@example.com',
            nickname='admin',
            is_admin=True,
        )
        self.admin.set_password('safe-password')
        self.user = User(
            email='rider@example.com',
            nickname='rider',
        )
        self.user.set_password('safe-password')
        self.almaty = City(
            city_id='almaty',
            name='Алматы',
            country='Казахстан',
            coords_lat=43.25,
            coords_lng=76.9,
            zoom=12,
            status='active',
        )
        self.astana = City(
            city_id='astana',
            name='Астана',
            country='Казахстан',
            coords_lat=51.1694,
            coords_lng=71.4491,
            zoom=12,
            status='active',
        )
        db.session.add_all([
            self.admin,
            self.user,
            self.almaty,
            self.astana,
        ])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login(self, user):
        with self.client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True

    def test_home_uses_existing_modal_ui_for_city_request(self):
        response = self.client.get('/')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'id="cityRequestModal" class="modal-overlay" hidden '
            'style="display: none;"',
            body,
        )
        self.assertIn('class="modal-middle"', body)
        self.assertIn('<h3 class="prime100">Хочу свой город</h3>', body)
        self.assertIn(
            'Напишите какой город вы хотите увидеть на сайте.',
            body,
        )
        self.assertIn('name="city_name"', body)
        self.assertIn('class="form-input search-input"', body)
        self.assertIn('Отправить', body)
        self.assertNotIn('https://tally.so/', body)

        with self.app.open_resource('static/js/cities.js') as script_file:
            script = script_file.read().decode('utf-8')
        self.assertIn("cityRequestModal.style.display = 'flex';", script)
        self.assertIn("cityRequestModal.style.display = 'none';", script)

    def test_home_sorts_countries_ignoring_leading_emoji(self):
        db.session.add_all([
            City(
                city_id='buenos-aires',
                name='Буэнос-Айрес',
                country='🇦🇷 Аргентина',
                coords_lat=-34.6037,
                coords_lng=-58.3816,
                zoom=12,
                status='active',
            ),
            City(
                city_id='minsk',
                name='Минск',
                country='Беларусь',
                coords_lat=53.9006,
                coords_lng=27.559,
                zoom=12,
                status='active',
            ),
            City(
                city_id='cape-town',
                name='Кейптаун',
                country='🌍 Южная Африка',
                coords_lat=-33.9249,
                coords_lng=18.4241,
                zoom=12,
                status='active',
            ),
        ])
        db.session.commit()

        body = self.client.get('/').get_data(as_text=True)

        self.assertLess(body.index('🇦🇷 Аргентина'), body.index('Беларусь'))
        self.assertLess(body.index('Беларусь'), body.index('Казахстан'))
        self.assertLess(body.index('Казахстан'), body.index('🌍 Южная Африка'))

    def test_guest_can_submit_city_request(self):
        response = self.client.post(
            '/city-requests',
            data={'city_name': '  Тараз  '},
        )

        self.assertEqual(response.status_code, 302)
        city_request = CityRequest.query.one()
        self.assertEqual(city_request.city_name, 'Тараз')
        self.assertIsNone(city_request.user_id)

    def test_authenticated_request_keeps_user(self):
        self._login(self.user)

        self.client.post(
            '/city-requests',
            data={'city_name': 'Костанай'},
        )

        city_request = CityRequest.query.one()
        self.assertEqual(city_request.user_id, self.user.id)

    def test_empty_or_too_long_request_is_not_saved(self):
        self.client.post('/city-requests', data={'city_name': '   '})
        self.client.post('/city-requests', data={'city_name': 'a' * 121})

        self.assertEqual(CityRequest.query.count(), 0)

    def test_location_opens_another_available_city(self):
        response = self.client.post(
            '/api/location/city',
            json={
                'latitude': 51.1694,
                'longitude': 71.4491,
                'city_names': ['Астана', 'Astana'],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['available'])
        self.assertEqual(payload['city']['id'], 'astana')
        self.assertEqual(payload['redirect_url'], '/city/astana')
        self.assertEqual(CityRequest.query.count(), 0)

    def test_missing_location_is_sent_to_city_requests_with_flag(self):
        response = self.client.post(
            '/api/location/city',
            json={
                'latitude': 42.9,
                'longitude': 71.37,
                'city_names': ['Тараз', 'Taraz'],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload['available'])
        self.assertEqual(payload['message'], 'Этого города пока нет на сайте.')

        city_request = CityRequest.query.one()
        self.assertEqual(city_request.city_name, 'Тараз')
        self.assertTrue(city_request.location_fail)
        self.assertEqual(city_request.latitude, 42.9)
        self.assertEqual(city_request.longitude, 71.37)

    def test_location_rejects_invalid_coordinates(self):
        response = self.client.post(
            '/api/location/city',
            json={
                'latitude': 95,
                'longitude': 71.37,
                'city_names': ['Город'],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(CityRequest.query.count(), 0)

    def test_admin_section_lists_all_city_requests(self):
        db.session.add_all([
            CityRequest(city_name='Шымкент'),
            CityRequest(city_name='Караганда', user_id=self.user.id),
            CityRequest(
                city_name='Тараз',
                location_fail=True,
                latitude=42.9,
                longitude=71.37,
            ),
        ])
        db.session.commit()
        self._login(self.admin)

        response = self.client.get('/admin/city-requests')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('<h2>Хочу свой город</h2>', body)
        self.assertIn('Шымкент', body)
        self.assertIn('Караганда', body)
        self.assertIn('location-fail', body)
        self.assertIn('42.900000, 71.370000', body)
        self.assertIn('Гость', body)
        self.assertIn('rider@example.com', body)
        self.assertIn('href="/admin/city-requests"', body)


if __name__ == '__main__':
    unittest.main()
