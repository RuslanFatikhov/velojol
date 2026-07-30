import json
import os
import tempfile
import unittest

from app import create_app, db
from app.models.city import City
from app.models.user import User
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class AdminCitiesTestCase(unittest.TestCase):
    def setUp(self):
        self.static_dir = tempfile.TemporaryDirectory()
        self.app = create_app(TestConfig)
        self.app.static_folder = self.static_dir.name
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
            coat_of_arms='uploads/cities/almaty_coat.jpg',
            background_image='uploads/cities/almaty_bg.jpg',
        )
        self.admin = User(
            email='admin@example.com',
            nickname='admin',
            is_admin=True,
        )
        self.admin.set_password('safe-password')
        db.session.add_all([self.city, self.admin])
        db.session.commit()

        upload_dir = os.path.join(
            self.app.static_folder,
            'uploads',
            'cities',
        )
        os.makedirs(upload_dir, exist_ok=True)
        for filename in ('almaty_coat.jpg', 'almaty_bg.jpg'):
            with open(os.path.join(upload_dir, filename), 'wb') as image_file:
                image_file.write(b'test image')

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin.id)
            session['_fresh'] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.static_dir.cleanup()

    def _edit_data(self, **overrides):
        data = {
            'name': self.city.name,
            'country': self.city.country,
            'coords_lat': str(self.city.coords_lat),
            'coords_lng': str(self.city.coords_lng),
            'zoom': str(self.city.zoom),
            'status': self.city.status,
        }
        data.update(overrides)
        return data

    def test_edit_form_offers_city_image_removal(self):
        response = self.client.get(f'/admin/cities/{self.city.id}/edit')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('name="remove_coat_of_arms"', body)
        self.assertIn('Удалить герб', body)
        self.assertIn('name="remove_background_image"', body)
        self.assertIn('Удалить фон', body)

    def test_cities_are_paginated_by_50(self):
        db.session.add_all([
            City(
                city_id=f'city-{index}',
                name=f'Город {index:02d}',
                country='Казахстан',
                coords_lat=43.25,
                coords_lng=76.9,
                zoom=12,
                status='active',
            )
            for index in range(50)
        ])
        db.session.commit()

        first_page = self.client.get('/admin/cities?page=1')
        second_page = self.client.get('/admin/cities?page=2')
        first_body = first_page.get_data(as_text=True)
        second_body = second_page.get_data(as_text=True)

        self.assertEqual(first_body.count('class="btn-sm btn-warning"'), 50)
        self.assertEqual(second_body.count('class="btn-sm btn-warning"'), 1)
        self.assertIn('aria-label="Пагинация"', first_body)

    def test_edit_can_remove_coat_and_background(self):
        response = self.client.post(
            f'/admin/cities/{self.city.id}/edit',
            data=self._edit_data(
                remove_coat_of_arms='1',
                remove_background_image='1',
            ),
        )

        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.city)
        self.assertIsNone(self.city.coat_of_arms)
        self.assertIsNone(self.city.background_image)
        self.assertFalse(os.path.exists(os.path.join(
            self.app.static_folder,
            'uploads',
            'cities',
            'almaty_coat.jpg',
        )))
        self.assertFalse(os.path.exists(os.path.join(
            self.app.static_folder,
            'uploads',
            'cities',
            'almaty_bg.jpg',
        )))

        cities_json_path = os.path.join(
            self.app.static_folder,
            'data',
            'cities.json',
        )
        with open(cities_json_path, encoding='utf-8') as cities_file:
            city_data = json.load(cities_file)['cities'][0]
        self.assertIsNone(city_data['coat_of_arms'])
        self.assertIsNone(city_data['background_image'])


if __name__ == '__main__':
    unittest.main()
