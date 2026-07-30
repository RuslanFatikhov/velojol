import json
import unittest
from datetime import datetime

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


class AdminReviewsTestCase(unittest.TestCase):
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
        self.reviewer = User(
            email='reviewer@example.com',
            nickname='reviewer',
        )
        self.reviewer.set_password('safe-password')
        self.city = City(
            city_id='almaty',
            name='Алматы',
            country='Казахстан',
            coords_lat=43.25,
            coords_lng=76.9,
            zoom=12,
            status='active',
        )
        db.session.add_all([self.admin, self.reviewer, self.city])
        db.session.flush()

        self.bikelane = BikeLane(
            title='Тестовая велодорожка',
            description='Описание',
            city_id=self.city.id,
            city=self.city.city_id,
            geometry=json.dumps({
                'type': 'LineString',
                'coordinates': [[76.9, 43.25], [76.91, 43.26]],
            }),
            track_type='lane',
            quality=4,
            status='approved',
        )
        self.infrastructure = InfrastructurePoint(
            city_id=self.city.id,
            infrastructure_type=InfrastructurePoint.TYPE_REPAIR_STATION,
            title='Ремонтная станция',
            latitude=43.25,
            longitude=76.9,
            source='openstreetmap',
            osm_type='node',
            osm_id='review-test',
            imported_at=datetime.utcnow(),
        )
        db.session.add_all([self.bikelane, self.infrastructure])
        db.session.flush()
        db.session.add_all([
            Review(
                user_id=self.reviewer.id,
                bikelane_id=self.bikelane.id,
                rating=5,
                text='Отличная велодорожка',
                photos='["uploads/reviews/photo.jpg"]',
            ),
            Review(
                user_id=self.reviewer.id,
                infrastructure_point_id=self.infrastructure.id,
                rating=4,
                text='Полезная станция',
            ),
        ])
        db.session.commit()

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin.id)
            session['_fresh'] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_admin_reviews_page_shows_all_target_types(self):
        response = self.client.get('/admin/reviews')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('<h2>Отзывы</h2>', body)
        self.assertIn('Отличная велодорожка', body)
        self.assertIn('Полезная станция', body)
        self.assertIn('Тестовая велодорожка', body)
        self.assertIn('Ремонтная станция', body)
        self.assertIn('reviewer@example.com', body)
        self.assertIn('5 / 5', body)
        self.assertIn('href="/admin/reviews"', body)

    def test_admin_reviews_are_paginated_by_50(self):
        extra_users = []
        for index in range(50):
            user = User(
                email=f'reviewer-{index}@example.com',
                nickname=f'reviewer-{index}',
            )
            user.set_password('safe-password')
            extra_users.append(user)
        db.session.add_all(extra_users)
        db.session.flush()
        db.session.add_all([
            Review(
                user_id=user.id,
                bikelane_id=self.bikelane.id,
                rating=3,
                text=f'Отзыв {index}',
            )
            for index, user in enumerate(extra_users)
        ])
        db.session.commit()

        first_page = self.client.get('/admin/reviews?page=1')
        second_page = self.client.get('/admin/reviews?page=2')
        first_body = first_page.get_data(as_text=True)
        second_body = second_page.get_data(as_text=True)

        self.assertEqual(first_body.count('data-review-id='), 50)
        self.assertEqual(second_body.count('data-review-id='), 2)
        self.assertIn('aria-label="Пагинация"', first_body)
        self.assertIn('page=2', first_body)


if __name__ == '__main__':
    unittest.main()
