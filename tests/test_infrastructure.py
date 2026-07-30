import io
import json
import os
import tempfile
import unittest
from datetime import datetime

from PIL import Image

from app import create_app, db
from app.models.city import City
from app.models.infrastructure_point import InfrastructurePoint
from app.models.user import User
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class InfrastructureTestCase(unittest.TestCase):
    def setUp(self):
        self.upload_directory = tempfile.TemporaryDirectory()
        self.app = create_app(TestConfig)
        self.app.config['UPLOAD_FOLDER'] = self.upload_directory.name
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

        city = City(
            city_id='almaty',
            name='Алматы',
            country='Kazakhstan',
            coords_lat=43.25,
            coords_lng=76.9,
            zoom=12,
            status='active',
        )
        admin = User(
            email='admin-infrastructure@example.com',
            nickname='infrastructure-admin',
            is_admin=True,
        )
        admin.set_password('safe-password')
        viewer = User(
            email='viewer-infrastructure@example.com',
            nickname='infrastructure-viewer',
            is_admin=False,
        )
        viewer.set_password('safe-password')
        db.session.add_all([city, admin, viewer])
        db.session.flush()
        self.city = city

        self.point = InfrastructurePoint(
            city_id=city.id,
            infrastructure_type=InfrastructurePoint.TYPE_BICYCLE_PARKING,
            title='Велопарковка',
            description='',
            photos='[]',
            latitude=43.25,
            longitude=76.9,
            source='openstreetmap',
            osm_type='node',
            osm_id='5001',
            osm_tags=json.dumps({
                'amenity': 'bicycle_parking',
                'legacy:unknown': 'preserve-me',
            }),
            imported_at=datetime.utcnow(),
        )
        db.session.add(self.point)
        db.session.commit()
        self.admin_id = admin.id
        self.viewer_id = viewer.id

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin_id)
            session['_fresh'] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.upload_directory.cleanup()

    def test_admin_can_edit_parking_location_attributes_and_photo(self):
        image_data = io.BytesIO()
        Image.new('RGB', (80, 60), 'green').save(image_data, format='PNG')
        image_data.seek(0)

        response = self.client.post(
            f'/edit-parking/{self.point.id}',
            data={
                'title': 'Парковка у главного входа',
                'description': 'Парковка возле главного входа',
                'latitude': '43.2512345',
                'longitude': '76.9123456',
                'fee': 'no',
                'covered': 'yes',
                'access': 'customers',
                'bicycle_parking': 'stands',
                'capacity': '18',
                'cargo_bike': 'designated',
                'capacity:cargo_bike': '2',
                'surveillance': 'yes',
                'opening_hours': '24/7',
                'photos': (image_data, 'parking.png'),
            },
            content_type='multipart/form-data',
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        db.session.refresh(self.point)
        self.assertEqual(self.point.title, 'Парковка у главного входа')
        self.assertEqual(
            self.point.description,
            'Парковка возле главного входа',
        )
        self.assertAlmostEqual(self.point.latitude, 43.2512345)
        self.assertAlmostEqual(self.point.longitude, 76.9123456)
        tags = self.point.get_osm_tags()
        self.assertEqual(tags['fee'], 'no')
        self.assertEqual(tags['covered'], 'yes')
        self.assertEqual(tags['access'], 'customers')
        self.assertEqual(tags['bicycle_parking'], 'stands')
        self.assertEqual(tags['capacity'], '18')
        self.assertEqual(tags['capacity:cargo_bike'], '2')
        self.assertEqual(tags['legacy:unknown'], 'preserve-me')
        photos = self.point.get_photos_list()
        self.assertEqual(len(photos), 1)
        self.assertTrue(photos[0].startswith('uploads/infrastructure/'))
        self.assertTrue(os.path.exists(os.path.join(
            self.upload_directory.name,
            'infrastructure',
            str(self.point.id),
            os.path.basename(photos[0]),
        )))

        api_response = self.client.get(f'/api/infrastructure/{self.point.id}')
        infrastructure = api_response.get_json()['infrastructure']
        self.assertEqual(infrastructure['photos'], photos)
        self.assertIn(
            f'/edit-parking/{self.point.id}',
            infrastructure['edit_url'],
        )

    def test_parking_editor_has_map_photos_and_parking_fields(self):
        response = self.client.get(f'/edit-parking/{self.point.id}')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Редактирование велопарковки', body)
        self.assertIn('id="infrastructure-edit-map"', body)
        self.assertIn('id="infrastructure-latitude"', body)
        self.assertIn('id="infrastructure-longitude"', body)
        self.assertIn('name="description"', body)
        self.assertIn('name="photos"', body)
        self.assertIn('name="fee"', body)
        self.assertIn('Бесплатная', body)
        self.assertIn('Платная', body)
        self.assertIn('name="covered"', body)
        self.assertIn('Крытая', body)
        self.assertIn('Не крытая', body)
        self.assertIn('name="bicycle_parking"', body)
        self.assertIn('name="capacity"', body)
        self.assertIn('/static/js/edit_infrastructure.js', body)

    def test_add_bikelane_screen_has_object_type_tabs(self):
        response = self.client.get('/add-bikelane?city=almaty')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('aria-label="Что добавить"', body)
        self.assertIn('Дорожку', body)
        self.assertIn('Парковку', body)
        self.assertIn('Ремонтную стойку', body)
        self.assertIn('/add-bikelane?type=parking&amp;city=almaty', body)
        self.assertIn('/add-bikelane?type=repair&amp;city=almaty', body)
        self.assertIn('data-add-object-type="bikelane"', body)

    def test_add_parking_tab_uses_infrastructure_creation_form(self):
        response = self.client.get('/add-bikelane?type=parking&city=almaty')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Добавление велопарковки', body)
        self.assertIn('name="object_type" value="parking"', body)
        self.assertIn('id="infrastructure-city"', body)
        self.assertIn('value="almaty"', body)
        self.assertIn('name="bicycle_parking"', body)
        self.assertIn('name="capacity"', body)
        self.assertIn('aria-current="page"', body)

    def test_add_repair_tab_uses_repair_creation_form(self):
        response = self.client.get('/add-bikelane?type=repair&city=almaty')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Добавление ремонтной стойки', body)
        self.assertIn('name="object_type" value="repair"', body)
        self.assertIn('name="service:bicycle:pump"', body)
        self.assertIn('name="service:bicycle:tools"', body)

    def test_admin_can_add_parking_from_add_bikelane_screen(self):
        response = self.client.post(
            '/add-bikelane?type=parking',
            data={
                'object_type': 'parking',
                'city': 'almaty',
                'title': 'Парковка у школы',
                'description': 'Новая велопарковка',
                'latitude': '43.255',
                'longitude': '76.915',
                'fee': 'no',
                'bicycle_parking': 'stands',
                'capacity': '12',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/city/almaty'))
        created = InfrastructurePoint.query.filter_by(
            title='Парковка у школы',
        ).one()
        self.assertEqual(
            created.infrastructure_type,
            InfrastructurePoint.TYPE_BICYCLE_PARKING,
        )
        self.assertEqual(created.city_id, self.city.id)
        self.assertEqual(created.source, 'user')
        self.assertEqual(created.get_osm_tags()['amenity'], 'bicycle_parking')
        self.assertEqual(created.get_osm_tags()['capacity'], '12')

    def test_admin_can_add_repair_station_from_add_bikelane_screen(self):
        response = self.client.post(
            '/add-bikelane?type=repair',
            data={
                'object_type': 'repair',
                'city': 'almaty',
                'title': 'Ремонтная стойка в парке',
                'description': 'Стойка рядом со входом',
                'latitude': '43.257',
                'longitude': '76.917',
                'service:bicycle:pump': 'yes',
                'service:bicycle:tools': 'yes',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/city/almaty'))
        created = InfrastructurePoint.query.filter_by(
            title='Ремонтная стойка в парке',
        ).one()
        self.assertEqual(
            created.infrastructure_type,
            InfrastructurePoint.TYPE_REPAIR_STATION,
        )
        self.assertEqual(
            created.get_osm_tags()['amenity'],
            'bicycle_repair_station',
        )
        self.assertEqual(
            created.get_osm_tags()['service:bicycle:pump'],
            'yes',
        )

    def test_repair_editor_has_its_own_url_and_service_fields(self):
        repair = InfrastructurePoint(
            city_id=self.city.id,
            infrastructure_type=InfrastructurePoint.TYPE_REPAIR_STATION,
            title='Ремонтная станция',
            description='',
            photos='[]',
            latitude=43.26,
            longitude=76.91,
            source='openstreetmap',
            osm_type='node',
            osm_id='5002',
            osm_tags=json.dumps({
                'amenity': 'bicycle_repair_station',
                'service:bicycle:pump': 'yes',
            }),
            imported_at=datetime.utcnow(),
        )
        db.session.add(repair)
        db.session.commit()

        response = self.client.get(f'/edit-repair/{repair.id}')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Редактирование ремонтной станции', body)
        self.assertIn('name="service:bicycle:pump"', body)
        self.assertIn('name="service:bicycle:tools"', body)
        self.assertIn('name="service:bicycle:chain_tool"', body)
        self.assertIn('name="service:bicycle:stand"', body)
        self.assertIn('name="service:bicycle:charging"', body)
        self.assertIn('name="lastcheck:status"', body)
        self.assertEqual(
            self.client.get(f'/edit-parking/{repair.id}').status_code,
            404,
        )

    def test_legacy_admin_edit_url_uses_the_same_editor(self):
        response = self.client.get(
            f'/admin/infrastructure/{self.point.id}/edit'
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'Редактирование велопарковки',
            response.get_data(as_text=True),
        )

    def test_non_admin_cannot_open_infrastructure_editors(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.viewer_id)
            session['_fresh'] = True

        response = self.client.get(f'/edit-parking/{self.point.id}')

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/'))


if __name__ == '__main__':
    unittest.main()
