import io
import json
import os
import tempfile
import unittest
from datetime import datetime

from PIL import Image

from app import create_app, db
from app.models.bikelane import BikeLane
from app.models.city import City
from app.models.infrastructure_point import InfrastructurePoint
from app.models.review import Review
from app.models.user import User
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ReviewsTestCase(unittest.TestCase):
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
        user = User(
            email='reviewer@example.com',
            nickname='reviewer',
        )
        user.set_password('safe-password')
        db.session.add_all([city, user])
        db.session.flush()

        self.bikelane = BikeLane(
            title='Тестовая велодорожка',
            description='Описание тестовой велодорожки',
            city_id=city.id,
            city=city.city_id,
            geometry=json.dumps({
                'type': 'LineString',
                'coordinates': [[76.9, 43.25], [76.901, 43.251]],
            }),
            track_type='lane',
            quality=4,
            status='approved',
            user_id=user.id,
        )
        self.infrastructure = InfrastructurePoint(
            city_id=city.id,
            infrastructure_type=InfrastructurePoint.TYPE_REPAIR_STATION,
            title='Ремонтная станция',
            description='',
            photos='[]',
            latitude=43.25,
            longitude=76.9,
            source='openstreetmap',
            osm_type='node',
            osm_id='7001',
            imported_at=datetime.utcnow(),
        )
        db.session.add_all([self.bikelane, self.infrastructure])
        db.session.commit()
        self.user_id = user.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.upload_directory.cleanup()

    def _login(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.user_id)
            session['_fresh'] = True

    @staticmethod
    def _photo():
        image_data = io.BytesIO()
        Image.new('RGB', (100, 80), 'orange').save(
            image_data,
            format='PNG',
        )
        image_data.seek(0)
        return image_data

    def test_anonymous_user_can_read_but_cannot_post_review(self):
        response = self.client.get(
            f'/api/reviews/bikelane/{self.bikelane.id}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()['authenticated'])

        response = self.client.post(
            f'/api/reviews/bikelane/{self.bikelane.id}',
            data={'rating': '5', 'text': 'Отлично'},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Review.query.count(), 0)

    def test_user_can_rate_review_and_attach_photo_then_update(self):
        self._login()
        response = self.client.post(
            f'/api/reviews/bikelane/{self.bikelane.id}',
            data={
                'rating': '5',
                'text': 'Удобная и безопасная дорожка.',
                'photos': (self._photo(), 'review.png'),
            },
            content_type='multipart/form-data',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['summary'], {'average': 5.0, 'count': 1})
        self.assertEqual(len(payload['reviews']), 1)
        self.assertEqual(payload['reviews'][0]['rating'], 5)
        self.assertEqual(len(payload['reviews'][0]['photos']), 1)

        photo_path = payload['reviews'][0]['photos'][0]
        self.assertTrue(photo_path.startswith('uploads/reviews/'))
        self.assertTrue(os.path.exists(os.path.join(
            self.upload_directory.name,
            'reviews',
            str(payload['reviews'][0]['id']),
            os.path.basename(photo_path),
        )))

        response = self.client.post(
            f'/api/reviews/bikelane/{self.bikelane.id}',
            data={
                'rating': '4',
                'text': 'Обновлённый отзыв.',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Review.query.count(), 1)
        updated = response.get_json()
        self.assertEqual(updated['summary'], {'average': 4.0, 'count': 1})
        self.assertEqual(updated['current_user_review']['rating'], 4)
        self.assertEqual(len(updated['current_user_review']['photos']), 1)

    def test_same_user_can_review_an_infrastructure_object(self):
        self._login()
        response = self.client.post(
            f'/api/reviews/infrastructure/{self.infrastructure.id}',
            data={
                'rating': '3',
                'text': 'Насос работает.',
            },
        )
        self.assertEqual(response.status_code, 200)
        review = Review.query.one()
        self.assertIsNone(review.bikelane_id)
        self.assertEqual(
            review.infrastructure_point_id,
            self.infrastructure.id,
        )

    def test_rating_must_be_between_one_and_five(self):
        self._login()
        response = self.client.post(
            f'/api/reviews/bikelane/{self.bikelane.id}',
            data={'rating': '6', 'text': 'Неверная оценка'},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Review.query.count(), 0)


if __name__ == '__main__':
    unittest.main()
