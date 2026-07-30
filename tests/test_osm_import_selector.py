import unittest
from pathlib import Path

from app.routes.admin.osm_import import IMPORT_LIMIT_OPTIONS, IMPORT_TYPE_OPTIONS
from app.services.osm_import import _normalize_limit


ROOT = Path(__file__).resolve().parents[1]


class OsmImportSelectorTestCase(unittest.TestCase):
    def test_admin_import_form_contains_all_selectable_types(self):
        template = (ROOT / 'app/templates/admin/osm_import.html').read_text(
            encoding='utf-8',
        )

        self.assertIn('name="import_types"', template)
        self.assertIn('Что импортировать', template)
        self.assertEqual(
            IMPORT_TYPE_OPTIONS,
            (
                ('bikelanes', 'Велодорожки'),
                ('bus_lanes', 'Автобусные полосы'),
                ('bicycle_parking', 'Парковки'),
                ('bicycle_repair_station', 'Велостанции'),
            ),
        )

    def test_admin_import_form_offers_larger_limits(self):
        template = (ROOT / 'app/templates/admin/osm_import.html').read_text(
            encoding='utf-8',
        )

        self.assertIn('import_limit_options', template)
        self.assertEqual(IMPORT_LIMIT_OPTIONS, (100, 500, 1000))
        self.assertEqual(_normalize_limit(100), 100)
        self.assertEqual(_normalize_limit(500), 500)
        self.assertEqual(_normalize_limit(1000), 1000)
        self.assertEqual(_normalize_limit(5000), 1000)


if __name__ == '__main__':
    unittest.main()
