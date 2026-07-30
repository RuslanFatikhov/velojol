import pathlib
import stat
import unittest

from app import create_app, db
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    MAPBOX_TOKEN = 'pk.test-public-token'


class MapAssetsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_base_uses_current_mapbox_sdk(self):
        body = self.app.test_client().get('/auth/login').get_data(as_text=True)

        self.assertIn('api.mapbox.com/mapbox-gl-js/v3.25.0/mapbox-gl.css', body)
        self.assertIn('api.mapbox.com/mapbox-gl-js/v3.25.0/mapbox-gl.js', body)

    def test_city_map_requires_public_mapbox_token(self):
        script_path = pathlib.Path(self.app.static_folder) / 'js' / 'city_map_mapbox.js'
        source = script_path.read_text(encoding='utf-8')

        self.assertIn('new mapboxgl.Map', source)
        self.assertIn("MAPBOX_TOKEN.startsWith('pk.')", source)
        self.assertIn('mapboxgl.accessToken = MAPBOX_TOKEN', source)
        self.assertIn("style: 'mapbox://styles/mapbox/light-v11'", source)
        self.assertNotIn('maplibregl', source)

    def test_city_map_supports_user_geolocation_and_city_switch(self):
        template_root = pathlib.Path(self.app.root_path) / self.app.template_folder
        city_source = (template_root / 'public/city.html').read_text(
            encoding='utf-8'
        )
        script_path = pathlib.Path(self.app.static_folder) / 'js' / 'city_map_mapbox.js'
        script_source = script_path.read_text(encoding='utf-8')

        self.assertIn('id="cityGeolocationButton"', city_source)
        self.assertIn("filename='img/icon/target.svg'", city_source)
        self.assertIn('navigator.geolocation.getCurrentPosition(', script_source)
        self.assertIn(
            'https://api.mapbox.com/search/geocode/v6/reverse',
            script_source,
        )
        self.assertIn("fetch('/api/location/city'", script_source)
        self.assertIn('window.location.assign(payload.redirect_url);', script_source)
        self.assertIn(
            "payload.message || 'Этого города пока нет на сайте.'",
            script_source,
        )

    def test_bikelane_modal_shows_bikelane_id_at_the_bottom(self):
        script_path = pathlib.Path(self.app.static_folder) / 'js' / 'city_map_mapbox.js'
        source = script_path.read_text(encoding='utf-8')

        self.assertIn('ID: ${bikelane.id}', source)

    def test_bikelane_modal_shows_one_way_attribute(self):
        script_path = pathlib.Path(self.app.static_folder) / 'js' / 'city_map_mapbox.js'
        source = script_path.read_text(encoding='utf-8')

        self.assertIn(
            "Односторонняя — ${bikelane.is_one_way ? 'Да' : 'Нет'}",
            source,
        )

    def test_bus_lane_uses_simplified_form_and_blue_map_color(self):
        script_path = pathlib.Path(self.app.static_folder) / 'js' / 'city_map_mapbox.js'
        script_source = script_path.read_text(encoding='utf-8')
        template_root = pathlib.Path(self.app.root_path) / self.app.template_folder
        add_source = (template_root / 'add_bikelane.html').read_text(encoding='utf-8')
        add_script = (
            pathlib.Path(self.app.static_folder) / 'js' / 'add_bikelane.js'
        ).read_text(encoding='utf-8')
        city_source = (template_root / 'public/city.html').read_text(encoding='utf-8')

        self.assertIn('id="track_bus_lane"', add_source)
        self.assertIn("filename='img/icon/bikelane/5.png'", add_source)
        self.assertIn('class="island bikelane-only"', add_source)
        self.assertIn('section.hidden = isBusLane', add_script)
        self.assertIn('field.disabled = isBusLane', add_script)
        self.assertIn('<span>Автобусные полосы</span>', city_source)
        self.assertIn('id="showBusLanesFilter"', city_source)
        self.assertIn("bikelane.is_bus_lane ? ''", script_source)
        self.assertIn('bikelane.color || getQualityColor', script_source)

    def test_city_map_draws_osm_bicycle_infrastructure(self):
        script_path = pathlib.Path(self.app.static_folder) / 'js' / 'city_map_mapbox.js'
        source = script_path.read_text(encoding='utf-8')

        self.assertIn('drawInfrastructurePoints();', source)
        self.assertIn("new mapboxgl.Marker({", source)
        self.assertIn("? 'repair.svg'", source)
        self.assertIn(": 'parking.svg'", source)
        self.assertIn('showInfrastructureModal(point.id);', source)
        self.assertIn('fetch(`/api/infrastructure/${infrastructureId}`)', source)
        self.assertIn('Array.isArray(point.attributes)', source)
        self.assertIn('formatInfrastructureAttributeValue(attribute)', source)
        self.assertIn('initModalPhotoGallery(point.photos || []);', source)
        self.assertIn('applyMapLayerFilters();', source)

        template_root = pathlib.Path(self.app.root_path) / self.app.template_folder
        edit_source = (
            template_root / 'admin/edit_infrastructure.html'
        ).read_text(encoding='utf-8')
        self.assertIn('name="description"', edit_source)
        self.assertIn('name="photos"', edit_source)

    def test_map_filter_checkbox_has_borderless_active_states(self):
        stylesheet = pathlib.Path(self.app.static_folder) / 'css' / 'button.css'
        source = stylesheet.read_text(encoding='utf-8')

        self.assertIn('appearance: none;', source)
        self.assertIn('border: none;', source)
        self.assertIn(
            'background: var(--secondary-40, rgba(106, 106, 106, 0.40));',
            source,
        )
        self.assertIn('background: var(--accent-100, #34C759);', source)
        self.assertIn('background-image: url("../img/icon/check.svg");', source)

    def test_line_editor_supports_safe_drawing_and_existing_line_edits(self):
        template_root = pathlib.Path(self.app.root_path) / self.app.template_folder
        template_source = (template_root / 'add_bikelane.html').read_text(
            encoding='utf-8'
        )
        script_source = (
            pathlib.Path(self.app.static_folder) / 'js' / 'add_bikelane.js'
        ).read_text(encoding='utf-8')
        style_source = (
            pathlib.Path(self.app.static_folder) / 'css' / 'add_bikelane.css'
        ).read_text(encoding='utf-8')

        self.assertIn('id="map-editor-state"', template_source)
        self.assertIn('id="map-editor-meta"', template_source)
        self.assertIn('id="undo-line-point-btn"', template_source)
        self.assertIn('id="finish-line-btn"', template_source)
        self.assertIn('id="reset-line-btn"', template_source)
        self.assertIn('function undoLastLinePoint()', script_source)
        self.assertIn("event.key.toLowerCase() === 'z'", script_source)
        self.assertIn('function bindPolylineEditing(polyline)', script_source)
        self.assertIn("polyline.on('edit'", script_source)
        self.assertIn('function getQualityStarsColor(quality)', script_source)
        self.assertIn('updateCurrentPolylineColor(quality)', script_source)
        self.assertIn('if (!isDrawingLine && currentPolyline)', script_source)
        self.assertIn(
            "window.confirm('Очистить текущую линию и нарисовать заново?')",
            script_source,
        )
        self.assertNotIn('Debug Geometry', script_source)
        self.assertIn('#map .leaflet-editing-icon', style_source)
        self.assertIn('width: 24px !important;', style_source)

    def test_map_objects_render_rating_review_and_photo_ui(self):
        script_path = pathlib.Path(self.app.static_folder) / 'js' / 'city_map_mapbox.js'
        source = script_path.read_text(encoding='utf-8')
        stylesheet = pathlib.Path(self.app.static_folder) / 'css' / 'modal.css'
        css_source = stylesheet.read_text(encoding='utf-8')

        self.assertIn("initObjectReviews('bikelane', bikelane.id);", source)
        self.assertIn(
            "initObjectReviews('infrastructure', point.id);",
            source,
        )
        self.assertIn('/api/reviews/${targetType}/${targetId}', source)
        self.assertIn('name="rating"', source)
        self.assertIn('name="text"', source)
        self.assertIn('name="photos"', source)
        self.assertIn('.review-average', css_source)
        self.assertIn('.review-star-button', css_source)
        self.assertIn('.review-card', css_source)

    def test_city_templates_publish_configured_mapbox_token(self):
        template_root = pathlib.Path(self.app.root_path) / self.app.template_folder
        script_source = (
            pathlib.Path(self.app.static_folder) / 'js' / 'city_map_mapbox.js'
        ).read_text(encoding='utf-8')

        for relative_path in ('public/city.html', 'auth/my_bikelanes.html'):
            source = (template_root / relative_path).read_text(encoding='utf-8')
            self.assertIn('window.MAPBOX_TOKEN = {{ config.MAPBOX_TOKEN | tojson }};', source)

        city_source = (template_root / 'public/city.html').read_text(encoding='utf-8')
        self.assertIn(
            'window.infrastructureData = {{ infrastructure_json | safe }};',
            city_source,
        )
        self.assertIn('id="showBikelanesFilter"', city_source)
        self.assertIn('id="showBusLanesFilter"', city_source)
        self.assertIn('id="showParkingFilter"', city_source)
        self.assertIn('id="showRepairFilter"', city_source)
        self.assertNotIn(
            '<option value="bus_lane">Автобусная полоса</option>',
            city_source,
        )
        self.assertIn('CITY_MAP_FILTERS_STORAGE_KEY', script_source)
        self.assertIn('localStorage.setItem(', script_source)
        self.assertIn('restoreFilterState();', script_source)

    def test_bikelane_list_can_be_sorted_by_requested_fields(self):
        template_root = pathlib.Path(self.app.root_path) / self.app.template_folder
        city_source = (template_root / 'public/city.html').read_text(encoding='utf-8')
        script_source = (
            pathlib.Path(self.app.static_folder) / 'js' / 'city_map_mapbox.js'
        ).read_text(encoding='utf-8')

        self.assertIn('id="bikelanesSort"', city_source)
        for value in (
            'alphabetical',
            'distance_desc',
            'quality_desc',
            'date_desc',
        ):
            self.assertIn(f'value="{value}"', city_source)
        self.assertIn('function normalizeBikelaneTitle(title)', script_source)
        self.assertIn('(?:улица|ул\\.?)', script_source)
        self.assertIn('Number(second.length)', script_source)
        self.assertIn('Number(second.overall_quality)', script_source)
        self.assertIn('Date.parse(second.created_at', script_source)
        self.assertIn('filteredBikelanes = sortBikelanes(', script_source)

    def test_favicon_directories_are_web_readable(self):
        static_root = pathlib.Path(self.app.static_folder)

        for relative_path in ('favicon_io', 'img/favicon_io'):
            mode = stat.S_IMODE((static_root / relative_path).stat().st_mode)
            self.assertEqual(mode, 0o755)


if __name__ == '__main__':
    unittest.main()
