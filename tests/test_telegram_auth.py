import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from authlib.jose import JsonWebKey, jwt
from flask import redirect

from app import create_app, db, oauth
from app.models.user import User
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    TELEGRAM_CLIENT_ID = '8823648335'
    TELEGRAM_CLIENT_SECRET = 'test-client-secret'
    TELEGRAM_REDIRECT_URI = 'http://localhost/auth/telegram/callback'
    TELEGRAM_OAUTH_ENABLED = True


class FakeTelegramClient:
    def __init__(self, userinfo):
        self.userinfo = userinfo
        self.redirect_uri = None

    def authorize_redirect(self, redirect_uri):
        self.redirect_uri = redirect_uri
        return redirect('https://oauth.telegram.test/authorize')

    def authorize_access_token(self):
        return {'userinfo': self.userinfo}


class TelegramAuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()
        self.telegram_signing_key = JsonWebKey.generate_key(
            'RSA',
            2048,
            is_private=True,
        )
        self.telegram_private_jwk = self.telegram_signing_key.as_dict(
            is_private=True
        )
        self.telegram_public_jwk = self.telegram_signing_key.as_dict()
        for jwk in (self.telegram_private_jwk, self.telegram_public_jwk):
            jwk['kid'] = 'telegram-test-key'
            jwk['alg'] = 'RS256'
        self.app.config['TELEGRAM_JWKS'] = {
            'keys': [self.telegram_public_jwk],
        }

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _callback(self, userinfo):
        fake_client = FakeTelegramClient(userinfo)
        with patch('app.routes.auth._get_telegram_client', return_value=fake_client):
            return self.client.get('/auth/telegram/callback')

    def _id_token_callback(self, **overrides):
        self.client.get('/auth/login')
        with self.client.session_transaction() as auth_session:
            nonce = auth_session['telegram_login_nonce']

        claims = {
            'iss': 'https://oauth.telegram.org',
            'aud': TestConfig.TELEGRAM_CLIENT_ID,
            'sub': '123456789',
            'iat': int(time.time()),
            'exp': int(time.time()) + 300,
            'nonce': nonce,
            'name': 'Velo Rider',
            'given_name': 'Velo',
            'preferred_username': 'velorider',
            'picture': 'https://example.com/telegram-avatar.jpg',
        }
        claims.update(overrides)
        id_token = jwt.encode(
            {'alg': 'RS256', 'kid': 'telegram-test-key'},
            claims,
            self.telegram_private_jwk,
        ).decode('utf-8')
        return self.client.post(
            '/auth/telegram/callback',
            data={'id_token': id_token},
        )

    def test_login_page_shows_providers_without_email_form(self):
        response = self.client.get('/auth/login')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Войти через Telegram', body)
        self.assertIn('Войти через Google', body)
        self.assertNotIn('type="email"', body)
        self.assertNotIn('type="password"', body)
        self.assertNotIn('Забыли пароль?', body)
        self.assertNotIn('Создать аккаунт', body)

    def test_login_page_starts_widget_flow_in_the_browser(self):
        response = self.client.get('/auth/login?next=/profile/alice')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('oauth.telegram.org/js/telegram-login.js?3', body)
        self.assertIn('window.Telegram.Login.auth', body)
        self.assertIn(TestConfig.TELEGRAM_CLIENT_ID, body)
        with self.client.session_transaction() as auth_session:
            self.assertEqual(auth_session['telegram_oauth_next'], '/profile/alice')

    def test_telegram_fallback_never_waits_for_oidc_metadata(self):
        with patch('app.routes.auth._get_telegram_client') as get_client:
            response = self.client.get('/auth/telegram?next=/profile/alice')

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/auth/login'))
        get_client.assert_not_called()
        with self.client.session_transaction() as auth_session:
            self.assertEqual(auth_session['telegram_oauth_next'], '/profile/alice')

    def test_real_oidc_client_uses_state_nonce_and_pkce(self):
        telegram_client = oauth.create_client('telegram')
        metadata = {
            'authorization_endpoint': 'https://oauth.telegram.test/authorize',
            'token_endpoint': 'https://oauth.telegram.test/token',
            'issuer': 'https://oauth.telegram.test',
        }

        with patch.object(
            telegram_client,
            'load_server_metadata',
            return_value=metadata,
        ), self.app.test_request_context():
            response = telegram_client.authorize_redirect(
                TestConfig.TELEGRAM_REDIRECT_URI
            )

        params = parse_qs(urlsplit(response.location).query)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(params['response_type'], ['code'])
        self.assertEqual(params['code_challenge_method'], ['S256'])
        self.assertTrue(params['code_challenge'][0])
        self.assertTrue(params['state'][0])
        self.assertTrue(params['nonce'][0])
        self.assertEqual(params['scope'], ['openid profile'])

    def test_telegram_login_rejects_external_next(self):
        fake_client = FakeTelegramClient({})
        with patch('app.routes.auth._get_telegram_client', return_value=fake_client):
            self.client.get('/auth/telegram?next=https://attacker.example/path')

        with self.client.session_transaction() as auth_session:
            self.assertIsNone(auth_session['telegram_oauth_next'])

    def test_callback_creates_and_logs_in_telegram_user_without_email(self):
        response = self._callback({
            'sub': 'telegram-user-1',
            'name': 'Velo Rider',
            'preferred_username': 'velorider',
            'picture': 'https://example.com/telegram-avatar.jpg',
        })

        self.assertEqual(response.status_code, 302)
        user = User.query.filter_by(telegram_sub='telegram-user-1').one()
        self.assertIsNone(user.email)
        self.assertEqual(user.nickname, 'velorider')
        self.assertEqual(user.telegram_url, 'https://t.me/velorider')
        self.assertEqual(user.avatar_url, 'https://example.com/telegram-avatar.jpg')
        self.assertTrue(user.password_hash)
        with self.client.session_transaction() as auth_session:
            self.assertEqual(auth_session['_user_id'], str(user.id))

    def test_id_token_callback_creates_user_without_server_http(self):
        response = self._id_token_callback()

        self.assertEqual(response.status_code, 302)
        user = User.query.filter_by(telegram_sub='123456789').one()
        self.assertIsNone(user.email)
        self.assertEqual(user.nickname, 'velorider')
        self.assertEqual(user.telegram_url, 'https://t.me/velorider')
        self.assertEqual(user.avatar_url, 'https://example.com/telegram-avatar.jpg')
        with self.client.session_transaction() as auth_session:
            self.assertEqual(auth_session['_user_id'], str(user.id))

    def test_id_token_callback_rejects_invalid_or_expired_token(self):
        self.client.get('/auth/login')
        response = self.client.post('/auth/telegram/callback', data={
            'id_token': 'invalid',
        })
        self.assertTrue(response.location.endswith('/auth/login'))
        self.assertEqual(User.query.count(), 0)

        response = self._id_token_callback(exp=int(time.time()) - 61)
        self.assertTrue(response.location.endswith('/auth/login'))
        self.assertEqual(User.query.count(), 0)

    def test_id_token_callback_rejects_wrong_nonce(self):
        response = self._id_token_callback(nonce='attacker-nonce')

        self.assertTrue(response.location.endswith('/auth/login'))
        self.assertEqual(User.query.count(), 0)

    def test_callback_reuses_existing_telegram_user(self):
        user = User(
            email=None,
            nickname='existing_rider',
            telegram_sub='telegram-user-2',
        )
        user.set_password('unused-password')
        db.session.add(user)
        db.session.commit()

        self._callback({
            'sub': 'telegram-user-2',
            'preferred_username': 'different_username',
        })

        self.assertEqual(User.query.count(), 1)
        with self.client.session_transaction() as auth_session:
            self.assertEqual(auth_session['_user_id'], str(user.id))

    def test_callback_generates_unique_nickname(self):
        existing = User(email='rider@example.com', nickname='velorider')
        existing.set_password('safe-password')
        db.session.add(existing)
        db.session.commit()

        self._callback({
            'sub': 'telegram-user-3',
            'preferred_username': 'velorider',
        })

        telegram_user = User.query.filter_by(
            telegram_sub='telegram-user-3'
        ).one()
        self.assertEqual(telegram_user.nickname, 'velorider_2')

    def test_callback_rejects_missing_subject(self):
        response = self._callback({
            'preferred_username': 'velorider',
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith('/auth/login'))
        self.assertEqual(User.query.count(), 0)

    def test_callback_does_not_log_in_banned_user(self):
        user = User(
            email=None,
            nickname='banned_rider',
            telegram_sub='telegram-user-4',
            is_banned=True,
            ban_reason='spam',
        )
        user.set_password('unused-password')
        db.session.add(user)
        db.session.commit()

        self._callback({'sub': 'telegram-user-4'})

        with self.client.session_transaction() as auth_session:
            self.assertNotIn('_user_id', auth_session)


if __name__ == '__main__':
    unittest.main()
