import unittest
from unittest.mock import patch

from flask import redirect

from app import create_app, db
from app.models.user import User
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    GOOGLE_CLIENT_ID = 'test-client-id'
    GOOGLE_CLIENT_SECRET = 'test-client-secret'
    GOOGLE_REDIRECT_URI = 'http://localhost/auth/google/callback'
    GOOGLE_OAUTH_ENABLED = True


class FakeGoogleClient:
    def __init__(self, userinfo):
        self.userinfo = userinfo
        self.redirect_uri = None

    def authorize_redirect(self, redirect_uri):
        self.redirect_uri = redirect_uri
        return redirect('https://accounts.google.test/authorize')

    def authorize_access_token(self):
        return {'userinfo': self.userinfo}


class GoogleAuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _callback(self, userinfo):
        fake_client = FakeGoogleClient(userinfo)
        with patch('app.routes.auth._get_google_client', return_value=fake_client):
            return self.client.get('/auth/google/callback')

    def test_login_page_shows_google_button(self):
        response = self.client.get('/auth/login')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Войти через Google', response.get_data(as_text=True))

    def test_google_login_starts_oidc_flow_and_keeps_local_next(self):
        fake_client = FakeGoogleClient({})
        with patch('app.routes.auth._get_google_client', return_value=fake_client):
            response = self.client.get('/auth/google?next=/profile/alice')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, 'https://accounts.google.test/authorize')
        self.assertEqual(fake_client.redirect_uri, TestConfig.GOOGLE_REDIRECT_URI)
        with self.client.session_transaction() as auth_session:
            self.assertEqual(auth_session['google_oauth_next'], '/profile/alice')

    def test_google_login_rejects_external_next(self):
        fake_client = FakeGoogleClient({})
        with patch('app.routes.auth._get_google_client', return_value=fake_client):
            self.client.get('/auth/google?next=https://attacker.example/path')

        with self.client.session_transaction() as auth_session:
            self.assertIsNone(auth_session['google_oauth_next'])

    def test_callback_creates_and_logs_in_google_user(self):
        response = self._callback({
            'sub': 'google-user-1',
            'email': 'rider@example.com',
            'email_verified': True,
            'given_name': 'Rider',
            'picture': 'https://example.com/avatar.jpg',
        })

        self.assertEqual(response.status_code, 302)
        user = User.query.filter_by(google_sub='google-user-1').one()
        self.assertEqual(user.email, 'rider@example.com')
        self.assertEqual(user.nickname, 'Rider')
        self.assertEqual(user.avatar_url, 'https://example.com/avatar.jpg')
        self.assertTrue(user.password_hash)
        with self.client.session_transaction() as auth_session:
            self.assertEqual(auth_session['_user_id'], str(user.id))

    def test_callback_links_existing_user_by_verified_email(self):
        user = User(email='rider@example.com', nickname='local_rider')
        user.set_password('safe-password')
        db.session.add(user)
        db.session.commit()

        self._callback({
            'sub': 'google-user-2',
            'email': 'RIDER@example.com',
            'email_verified': True,
        })

        db.session.refresh(user)
        self.assertEqual(user.google_sub, 'google-user-2')
        self.assertEqual(User.query.count(), 1)

    def test_callback_rejects_unverified_email(self):
        response = self._callback({
            'sub': 'google-user-3',
            'email': 'rider@example.com',
            'email_verified': False,
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/auth/login'))
        self.assertEqual(User.query.count(), 0)

    def test_callback_does_not_log_in_banned_user(self):
        user = User(
            email='banned@example.com',
            nickname='banned_rider',
            google_sub='google-user-4',
            is_banned=True,
            ban_reason='spam',
        )
        user.set_password('safe-password')
        db.session.add(user)
        db.session.commit()

        self._callback({
            'sub': 'google-user-4',
            'email': 'banned@example.com',
            'email_verified': True,
        })

        with self.client.session_transaction() as auth_session:
            self.assertNotIn('_user_id', auth_session)


if __name__ == '__main__':
    unittest.main()
