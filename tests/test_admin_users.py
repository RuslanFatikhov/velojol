import json
import unittest

from app import create_app, db
from app.models.bikelane import BikeLane
from app.models.city import City
from app.models.notification import Notification
from app.models.review import Review
from app.models.user import User
from app.models.verification import VerificationCode
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class AdminUsersTestCase(unittest.TestCase):
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
            email='user@example.com',
            nickname='user',
        )
        self.user.set_password('safe-password')
        self.other_user = User(
            email='other@example.com',
            nickname='other',
        )
        self.other_user.set_password('safe-password')
        self.city = City(
            city_id='almaty',
            name='Алматы',
            country='Казахстан',
            coords_lat=43.25,
            coords_lng=76.9,
            zoom=12,
            status='active',
        )
        db.session.add_all([
            self.admin,
            self.user,
            self.other_user,
            self.city,
        ])
        db.session.commit()

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin.id)
            session['_fresh'] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _create_bikelane(self):
        bikelane = BikeLane(
            title='Пользовательская линия',
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
            user_id=self.user.id,
            moderated_by=self.user.id,
        )
        db.session.add(bikelane)
        db.session.commit()
        return bikelane

    def test_users_page_has_selectors_and_bulk_delete_action(self):
        response = self.client.get('/admin/users')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="select-all-users"', body)
        self.assertIn('class="user-row-selector"', body)
        self.assertIn('id="bulk-users-menu"', body)
        self.assertIn('action="/admin/users/bulk-delete"', body)
        self.assertIn('id="delete-selected-users"', body)
        self.assertIn(
            'disabled title="Нельзя удалить текущего администратора"',
            body,
        )

    def test_users_are_paginated_by_50(self):
        extra_users = []
        for index in range(48):
            user = User(
                email=f'user-{index}@example.com',
                nickname=f'user-{index}',
            )
            user.set_password('safe-password')
            extra_users.append(user)
        db.session.add_all(extra_users)
        db.session.commit()

        first_page = self.client.get('/admin/users?page=1')
        second_page = self.client.get('/admin/users?page=2')
        first_body = first_page.get_data(as_text=True)
        second_body = second_page.get_data(as_text=True)

        self.assertEqual(first_body.count('class="user-row-selector"'), 50)
        self.assertEqual(second_body.count('class="user-row-selector"'), 1)
        self.assertIn('aria-label="Пагинация"', first_body)

    def test_bulk_delete_removes_personal_data_and_preserves_bikelane(self):
        bikelane = self._create_bikelane()
        notification = Notification(
            user_id=self.user.id,
            type='bikelane_pending',
            title='Тест',
            message='Сообщение',
        )
        review = Review(
            user_id=self.user.id,
            bikelane_id=bikelane.id,
            rating=5,
            text='Отзыв',
        )
        verification = VerificationCode.create_code(
            self.user.email,
            'password_reset',
        )
        self.other_user.is_banned = True
        self.other_user.banned_by = self.user.id
        db.session.add_all([notification, review])
        db.session.commit()
        notification_id = notification.id
        review_id = review.id
        verification_id = verification.id

        response = self.client.post(
            '/admin/users/bulk-delete',
            data={'user_ids': [str(self.user.id)]},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(db.session.get(User, self.user.id))
        self.assertIsNotNone(db.session.get(BikeLane, bikelane.id))
        db.session.refresh(bikelane)
        db.session.refresh(self.other_user)
        self.assertIsNone(bikelane.user_id)
        self.assertIsNone(bikelane.moderated_by)
        self.assertIsNone(self.other_user.banned_by)
        self.assertIsNone(db.session.get(Notification, notification_id))
        self.assertIsNone(db.session.get(Review, review_id))
        self.assertIsNone(
            db.session.get(VerificationCode, verification_id)
        )

    def test_bulk_delete_never_deletes_current_admin(self):
        response = self.client.post(
            '/admin/users/bulk-delete',
            data={'user_ids': [str(self.admin.id), str(self.user.id)]},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(db.session.get(User, self.admin.id))
        self.assertIsNone(db.session.get(User, self.user.id))

    def test_bulk_delete_requires_a_valid_user_selection(self):
        response = self.client.post(
            '/admin/users/bulk-delete',
            data={'user_ids': ['invalid']},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'Выберите хотя бы одного пользователя.',
            response.get_data(as_text=True),
        )
        self.assertIsNotNone(db.session.get(User, self.user.id))


if __name__ == '__main__':
    unittest.main()
