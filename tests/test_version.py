import pathlib
import tempfile
import unittest

from app import create_app, db
from app.version import load_app_version
from config import Config
from scripts.set_version import set_version, validate_version


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


class VersionTestCase(unittest.TestCase):
    def test_loader_validates_version_and_has_safe_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            version_file = pathlib.Path(directory) / 'VERSION'
            version_file.write_text('2.4.1\n', encoding='utf-8')
            self.assertEqual(load_app_version(version_file), '2.4.1')

            version_file.write_text('release-two\n', encoding='utf-8')
            self.assertEqual(load_app_version(version_file, fallback='0.0'), '0.0')
            self.assertEqual(load_app_version(version_file.with_name('missing')), '0.0')

    def test_version_setter_validates_and_updates_only_destination(self):
        self.assertEqual(validate_version('1.3'), '1.3')
        self.assertEqual(validate_version('1.3.4'), '1.3.4')
        for invalid in ('1', 'v1.3', '1.3-beta', '1.3.4.5'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_version(invalid)

        with tempfile.TemporaryDirectory() as directory:
            version_file = pathlib.Path(directory) / 'VERSION'
            sibling = pathlib.Path(directory) / 'keep.txt'
            sibling.write_text('unchanged', encoding='utf-8')
            set_version('3.2', version_file=version_file)
            self.assertEqual(version_file.read_text(encoding='utf-8'), '3.2\n')
            self.assertEqual(sibling.read_text(encoding='utf-8'), 'unchanged')

    def test_version_context_footer_and_healthz(self):
        expected_version = load_app_version()
        app = create_app(TestConfig)
        with app.app_context():
            db.create_all()
            client = app.test_client()
            response = client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn(f'OPEN-VELOJOL {expected_version}', response.get_data(as_text=True))

            health = client.get('/healthz')
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.get_json()['version'], expected_version)
            db.session.remove()
            db.drop_all()


if __name__ == '__main__':
    unittest.main()
