import pathlib
import unittest

from sqlalchemy import inspect

from app import create_app, db
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


class BannerRemovalTestCase(unittest.TestCase):
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

    def test_bus_lanes_poll_banner_is_fully_removed(self):
        body = self.client.get('/').get_data(as_text=True)
        self.assertNotIn('bus-lanes-banner', body)
        self.assertNotIn('Надо ли добавить автобусные полосы?', body)
        self.assertEqual(
            self.client.get('/api/banner/bus-lanes').status_code,
            404,
        )
        self.assertNotIn('banner_responses', inspect(db.engine).get_table_names())

        static_root = pathlib.Path(self.app.static_folder)
        script = (static_root / 'js/cities.js').read_text(encoding='utf-8')
        stylesheet = (static_root / 'css/cities.css').read_text(encoding='utf-8')
        self.assertNotIn('initBusLanesBanner', script)
        self.assertNotIn('bus-lanes-banner', stylesheet)
        self.assertFalse((static_root / 'img/banner/bus-lanes.png').exists())


if __name__ == '__main__':
    unittest.main()
