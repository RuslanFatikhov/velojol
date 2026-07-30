import json
import unittest
from datetime import datetime

from app import create_app, db
from app.models.bikelane import BikeLane
from app.models.city import City
from app.models.infrastructure_point import InfrastructurePoint
from app.models.user import User
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class AdminBikeLaneEditTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

        self.city = City(
            city_id='almaty',
            name='Алматы',
            country='Kazakhstan',
            coords_lat=43.25,
            coords_lng=76.9,
            zoom=12,
            status='active',
        )
        self.admin = User(email='admin@example.com', nickname='admin', is_admin=True)
        self.admin.set_password('safe-password')
        self.owner = User(email='owner@example.com', nickname='owner')
        self.owner.set_password('safe-password')
        db.session.add_all([self.city, self.admin, self.owner])
        db.session.flush()

        self.geometry = json.dumps({
            'type': 'LineString',
            'coordinates': [[76.9, 43.25], [76.901, 43.251]],
        })
        self.bikelane = BikeLane(
            title='OSM lane',
            description='Велополоса',
            city_id=self.city.id,
            city=self.city.city_id,
            geometry=self.geometry,
            track_type='lane',
            quality=4,
            has_parking=False,
            has_markings=True,
            has_signs=False,
            is_one_way=False,
            overall_quality=4,
            photos=json.dumps(['uploads/original.jpg']),
            videos=json.dumps(['https://example.com/video']),
            status='approved',
            source='openstreetmap',
            osm_type='way',
            osm_id='608045690',
            osm_tags=json.dumps({'cycleway:right': 'lane'}),
            imported_at=datetime.utcnow(),
            user_id=self.owner.id,
        )
        db.session.add(self.bikelane)
        db.session.commit()

        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.admin.id)
            session['_fresh'] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _post_data(self, description='Велополоса'):
        return {
            'city': 'almaty',
            'title': 'Updated OSM lane',
            'description': description,
            'track_type': 'lane',
            'quality': '5',
            'has_parking': 'true',
            'has_markings': 'false',
            'has_signs': 'true',
            'is_one_way': 'true',
            'overall_quality': '3',
            'geometry': self.geometry,
            'distance': '140',
            'video_url': 'https://example.com/video',
        }

    def _create_bikelane(self, title, status='pending'):
        bikelane = BikeLane(
            title=title,
            description='Тестовая велодорожка',
            city_id=self.city.id,
            city=self.city.city_id,
            geometry=self.geometry,
            track_type='lane',
            quality=3,
            overall_quality=3,
            status=status,
            user_id=self.owner.id,
        )
        db.session.add(bikelane)
        db.session.commit()
        return bikelane

    def _create_infrastructure(self, title, infrastructure_type):
        point = InfrastructurePoint(
            city_id=self.city.id,
            infrastructure_type=infrastructure_type,
            title=title,
            latitude=43.25,
            longitude=76.9,
            source='openstreetmap',
            osm_type='node',
            osm_id=f'{infrastructure_type}-{title}',
        )
        db.session.add(point)
        db.session.commit()
        return point

    def test_get_uses_shared_prefilled_add_form(self):
        response = self.client.get(f'/admin/bikelanes/{self.bikelane.id}/edit')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="bikelane-form"', body)
        self.assertIn('id="map-drawer"', body)
        self.assertIn('/static/css/add_bikelane.css', body)
        self.assertIn('/static/js/add_bikelane.js', body)
        self.assertIn('data-admin-edit-mode="true"', body)
        self.assertIn('data-description-min-length="1"', body)
        self.assertIn('value="OSM lane"', body)
        self.assertIn(f'action="/admin/bikelanes/{self.bikelane.id}/edit"', body)

    def test_main_edit_page_shows_delete_button_to_admin_at_the_bottom(self):
        response = self.client.get(f'/edit-bikelane/{self.bikelane.id}')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="admin-delete-bikelane-section"', body)
        self.assertIn('form="bikelane-form"', body)
        self.assertIn('data-default-label="Сохранить"', body)
        self.assertIn('>Сохранить</button>', body.replace('\n', '').replace(' ', ''))
        self.assertIn('id="admin-delete-bikelane-btn"', body)
        self.assertIn(
            f'action="/admin/bikelanes/{self.bikelane.id}/delete"',
            body,
        )
        self.assertIn('>Удалить</button>', body.replace('\n', '').replace(' ', ''))
        self.assertGreater(
            body.index('id="admin-delete-bikelane-btn"'),
            body.index('id="submit-bikelane-btn"'),
        )

    def test_main_edit_page_hides_admin_delete_button_from_owner(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.owner.id)
            session['_fresh'] = True

        response = self.client.get(f'/edit-bikelane/{self.bikelane.id}')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('id="admin-delete-bikelane-section"', body)
        self.assertNotIn('id="admin-delete-bikelane-btn"', body)

    def test_admin_adds_bikelane_as_approved_without_moderation(self):
        get_response = self.client.get('/add-bikelane')
        get_body = get_response.get_data(as_text=True)
        self.assertIn('data-default-label="Опубликовать"', get_body)
        self.assertIn('Запись будет опубликована сразу, без модерации.', get_body)

        response = self.client.post(
            '/add-bikelane',
            data=self._post_data(
                description='Подробное описание новой велодорожки'
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])
        self.assertEqual(
            response.get_json()['message'],
            'Велодорожка опубликована!',
        )
        created = BikeLane.query.filter_by(title='Updated OSM lane').one()
        self.assertEqual(created.status, 'approved')
        self.assertEqual(created.moderated_by, self.admin.id)
        self.assertIsNotNone(created.moderated_at)

    def test_admin_main_edit_publishes_pending_bikelane_immediately(self):
        bikelane = self._create_bikelane('Ожидает модерации')

        response = self.client.post(
            f'/edit-bikelane/{bikelane.id}',
            data=self._post_data(
                description='Подробное описание от администратора'
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])
        self.assertEqual(
            response.get_json()['message'],
            'Изменения опубликованы',
        )
        self.assertTrue(
            response.get_json()['redirect_url'].endswith(
                f'/admin/bikelanes/{bikelane.id}'
            )
        )
        db.session.refresh(bikelane)
        self.assertEqual(bikelane.status, 'approved')
        self.assertEqual(bikelane.moderated_by, self.admin.id)

    def test_owner_edit_still_returns_bikelane_to_moderation(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = str(self.owner.id)
            session['_fresh'] = True

        response = self.client.post(
            f'/edit-bikelane/{self.bikelane.id}',
            data=self._post_data(
                description='Подробное описание от владельца'
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])
        self.assertEqual(
            response.get_json()['message'],
            'Изменения отправлены на модерацию',
        )
        db.session.refresh(self.bikelane)
        self.assertEqual(self.bikelane.status, 'pending')
        self.assertIsNone(self.bikelane.moderated_by)
        self.assertIsNone(self.bikelane.moderated_at)

    def test_admin_panel_edit_publishes_pending_bikelane_immediately(self):
        bikelane = self._create_bikelane('Ожидает изменения')

        response = self.client.post(
            f'/admin/bikelanes/{bikelane.id}/edit',
            data=self._post_data(description='Велодорожка'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])
        self.assertEqual(
            response.get_json()['message'],
            'Изменения опубликованы',
        )
        db.session.refresh(bikelane)
        self.assertEqual(bikelane.status, 'approved')
        self.assertEqual(bikelane.moderated_by, self.admin.id)

    def test_post_preserves_source_status_owner_and_existing_media(self):
        original_imported_at = self.bikelane.imported_at
        response = self.client.post(
            f'/admin/bikelanes/{self.bikelane.id}/edit',
            data=self._post_data(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])
        db.session.refresh(self.bikelane)
        self.assertEqual(self.bikelane.title, 'Updated OSM lane')
        self.assertEqual(self.bikelane.status, 'approved')
        self.assertEqual(self.bikelane.source, 'openstreetmap')
        self.assertEqual(self.bikelane.osm_type, 'way')
        self.assertEqual(self.bikelane.osm_id, '608045690')
        self.assertEqual(json.loads(self.bikelane.osm_tags), {'cycleway:right': 'lane'})
        self.assertEqual(self.bikelane.imported_at, original_imported_at)
        self.assertEqual(self.bikelane.user_id, self.owner.id)
        self.assertTrue(self.bikelane.is_one_way)
        self.assertEqual(self.bikelane.get_photos_list(), ['uploads/original.jpg'])
        self.assertEqual(self.bikelane.get_videos_list(), ['https://example.com/video'])

    def test_admin_can_save_short_semantic_description(self):
        response = self.client.post(
            f'/admin/bikelanes/{self.bikelane.id}/edit',
            data=self._post_data(description='Велодорожка'),
        )

        self.assertEqual(response.status_code, 200)
        db.session.refresh(self.bikelane)
        self.assertEqual(self.bikelane.description, 'Велодорожка')

    def test_overall_rating_and_color_use_all_bikelane_characteristics(self):
        self.bikelane.track_type = 'lane'
        self.bikelane.quality = 5
        self.bikelane.has_parking = True
        self.bikelane.has_markings = False
        self.bikelane.has_signs = True
        self.bikelane.overall_quality = None

        # 3 (тип) - 2 (парковка) + 0.5 (знаки) + 1 (покрытие) = 2.5,
        # одинаково округляется до трёх звёзд на сервере и в браузере.
        self.assertEqual(self.bikelane.calculate_overall_quality(), 3)
        self.assertEqual(self.bikelane.effective_overall_quality, 3)
        self.assertEqual(self.bikelane.quality_color, '#f39c12')

        # Даже старое или неверное сохранённое значение не управляет цветом:
        # источником остаётся актуальная сумма характеристик.
        self.bikelane.overall_quality = 1
        self.assertEqual(self.bikelane.quality_color, '#f39c12')
        with self.app.test_request_context():
            self.assertEqual(self.bikelane.to_dict()['overall_quality'], 3)

    def test_car_parking_reduces_overall_rating_by_two_stars(self):
        self.bikelane.track_type = 'separated'
        self.bikelane.quality = 3
        self.bikelane.has_markings = False
        self.bikelane.has_signs = False
        self.bikelane.has_parking = False

        rating_without_parked_cars = self.bikelane.calculate_overall_quality()

        self.bikelane.has_parking = True
        rating_with_parked_cars = self.bikelane.calculate_overall_quality()

        self.assertEqual(rating_without_parked_cars, 5)
        self.assertEqual(rating_with_parked_cars, 3)
        self.assertEqual(
            rating_without_parked_cars - rating_with_parked_cars,
            2,
        )

    def test_server_recalculates_overall_rating_instead_of_trusting_form(self):
        data = self._post_data(description='Велодорожка')
        data['overall_quality'] = '1'

        response = self.client.post(
            f'/admin/bikelanes/{self.bikelane.id}/edit',
            data=data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])
        db.session.refresh(self.bikelane)
        self.assertEqual(self.bikelane.overall_quality, 3)
        self.assertEqual(self.bikelane.quality_color, '#f39c12')

    def test_bikelanes_table_has_bulk_row_selector_and_action_menu(self):
        response = self.client.get('/admin/bikelanes?status=all')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('<h2>Данные</h2>', body)
        self.assertIn('id="select-all-data"', body)
        self.assertIn('class="data-row-selector"', body)
        self.assertIn('id="bulk-actions-menu"', body)
        self.assertIn('/admin/bikelanes/bulk-action', body)
        self.assertIn('data-bulk-action="merge"', body)
        self.assertIn('Объединить', body)
        self.assertIn('id="searchInput"', body)
        self.assertIn('placeholder="Поиск по названию"', body)
        self.assertIn('data-search-text=', body)
        self.assertIn('function filterAdminDataRows()', body)
        self.assertIn('<th style="width: 70px;', body)
        self.assertIn('>ID</th>', body)
        for label in (
            'Велодорожки',
            'Автобусные полосы',
            'Велопарковки',
            'Ремонтные станции',
        ):
            self.assertIn(label, body)

    def test_data_rows_are_paginated_by_50_and_keep_filters(self):
        for index in range(50):
            db.session.add(BikeLane(
                title=f'Линия {index}',
                description='Тестовая велодорожка',
                city_id=self.city.id,
                city=self.city.city_id,
                geometry=self.geometry,
                track_type='lane',
                quality=3,
                overall_quality=3,
                status='approved',
                user_id=self.owner.id,
            ))
        db.session.commit()

        first_page = self.client.get(
            '/admin/bikelanes?data_type=bikelanes&status=all&page=1'
        )
        second_page = self.client.get(
            '/admin/bikelanes?data_type=bikelanes&status=all&page=2'
        )
        first_body = first_page.get_data(as_text=True)
        second_body = second_page.get_data(as_text=True)

        self.assertEqual(first_body.count('<tr data-selectable-row'), 50)
        self.assertEqual(second_body.count('<tr data-selectable-row'), 1)
        self.assertIn('aria-label="Пагинация"', first_body)
        self.assertIn('data_type=bikelanes', first_body)
        self.assertIn('status=all', first_body)

    def test_data_tabs_separate_bikelanes_and_bus_lanes(self):
        bicycle_lane = self._create_bikelane('Обычная', status='approved')
        bus_lane = self._create_bikelane('Автобусная', status='approved')
        bus_lane.track_type = 'bus_lane'
        db.session.commit()

        bicycle_response = self.client.get(
            '/admin/bikelanes?data_type=bikelanes&status=approved'
        )
        bus_response = self.client.get(
            '/admin/bikelanes?data_type=bus_lanes&status=approved'
        )
        bicycle_body = bicycle_response.get_data(as_text=True)
        bus_body = bus_response.get_data(as_text=True)

        self.assertIn(f'>{bicycle_lane.id}</td>', bicycle_body)
        self.assertNotIn(f'>{bus_lane.id}</td>', bicycle_body)
        self.assertIn(f'>{bus_lane.id}</td>', bus_body)
        self.assertNotIn(f'>{bicycle_lane.id}</td>', bus_body)

    def test_infrastructure_tabs_show_only_selected_data_type(self):
        parking = self._create_infrastructure(
            'Парковка',
            InfrastructurePoint.TYPE_BICYCLE_PARKING,
        )
        repair = self._create_infrastructure(
            'Ремонт',
            InfrastructurePoint.TYPE_REPAIR_STATION,
        )

        parking_response = self.client.get(
            '/admin/bikelanes?data_type=bicycle_parking'
        )
        repair_response = self.client.get(
            '/admin/bikelanes?data_type=bicycle_repair_station'
        )
        parking_body = parking_response.get_data(as_text=True)
        repair_body = repair_response.get_data(as_text=True)

        self.assertIn(f'>{parking.id}</td>', parking_body)
        self.assertNotIn('>Ремонт</strong>', parking_body)
        self.assertIn(f'>{repair.id}</td>', repair_body)
        self.assertNotIn('>Парковка</strong>', repair_body)
        self.assertIn('/admin/infrastructure/bulk-delete', parking_body)

    def test_admin_can_bulk_delete_selected_infrastructure(self):
        selected = self._create_infrastructure(
            'Удалить',
            InfrastructurePoint.TYPE_BICYCLE_PARKING,
        )
        untouched = self._create_infrastructure(
            'Оставить',
            InfrastructurePoint.TYPE_BICYCLE_PARKING,
        )
        selected_id = selected.id
        untouched_id = untouched.id

        response = self.client.post(
            '/admin/infrastructure/bulk-delete',
            data={
                'data_type': InfrastructurePoint.TYPE_BICYCLE_PARKING,
                'infrastructure_ids': [str(selected_id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(db.session.get(InfrastructurePoint, selected_id))
        self.assertIsNotNone(db.session.get(InfrastructurePoint, untouched_id))

    def test_admin_can_bulk_approve_selected_bikelanes(self):
        first = self._create_bikelane('Первая')
        second = self._create_bikelane('Вторая')

        response = self.client.post(
            '/admin/bikelanes/bulk-action',
            data={
                'action': 'approve',
                'status_filter': 'pending',
                'bikelane_ids': [str(first.id), str(second.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        db.session.refresh(first)
        db.session.refresh(second)
        self.assertEqual(first.status, 'approved')
        self.assertEqual(second.status, 'approved')
        self.assertEqual(first.moderated_by, self.admin.id)
        self.assertEqual(second.moderated_by, self.admin.id)

    def test_admin_can_bulk_reject_selected_bikelanes(self):
        first = self._create_bikelane('Первая')
        second = self._create_bikelane('Вторая')

        response = self.client.post(
            '/admin/bikelanes/bulk-action',
            data={
                'action': 'reject',
                'comment': 'Недостаточно данных',
                'status_filter': 'pending',
                'bikelane_ids': [str(first.id), str(second.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        db.session.refresh(first)
        db.session.refresh(second)
        self.assertEqual(first.status, 'rejected')
        self.assertEqual(second.status, 'rejected')
        self.assertEqual(first.admin_comment, 'Недостаточно данных')
        self.assertEqual(second.admin_comment, 'Недостаточно данных')

    def test_admin_can_bulk_delete_only_selected_bikelanes(self):
        selected = self._create_bikelane('Удалить')
        untouched = self._create_bikelane('Оставить')
        selected_id = selected.id
        untouched_id = untouched.id

        response = self.client.post(
            '/admin/bikelanes/bulk-action',
            data={
                'action': 'delete',
                'status_filter': 'all',
                'bikelane_ids': [str(selected_id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(db.session.get(BikeLane, selected_id))
        self.assertIsNotNone(db.session.get(BikeLane, untouched_id))

    def test_admin_can_merge_selected_connected_bikelanes(self):
        first = self._create_bikelane('Первая')
        second = self._create_bikelane('Вторая')
        first.geometry = json.dumps({
            'type': 'LineString',
            'coordinates': [[76.9, 43.25], [76.901, 43.251]],
        })
        second.geometry = json.dumps({
            'type': 'LineString',
            'coordinates': [[76.902, 43.252], [76.901, 43.251]],
        })
        first.photos = json.dumps(['uploads/first.jpg'])
        second.photos = json.dumps(['uploads/second.jpg', 'uploads/first.jpg'])
        first.videos = json.dumps(['https://example.com/first'])
        second.videos = json.dumps(['https://example.com/second'])
        first.source = 'openstreetmap'
        first.osm_type = 'way'
        first.osm_id = '7001'
        second.source = 'openstreetmap'
        second.osm_type = 'way'
        second.osm_id = '7002'
        db.session.commit()

        response = self.client.post(
            '/admin/bikelanes/bulk-action',
            data={
                'action': 'merge',
                'status_filter': 'pending',
                'bikelane_ids': [str(second.id), str(first.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith(f'/admin/bikelanes/{first.id}'))
        detail = self.client.get(response.location)
        self.assertIn(
            f'Основная линия: №{first.id}.',
            detail.get_data(as_text=True),
        )
        db.session.refresh(first)
        db.session.refresh(second)
        self.assertEqual(
            first.get_geometry_dict()['coordinates'],
            [
                [76.9, 43.25],
                [76.901, 43.251],
                [76.902, 43.252],
            ],
        )
        self.assertEqual(
            first.get_photos_list(),
            ['uploads/first.jpg', 'uploads/second.jpg'],
        )
        self.assertEqual(
            first.get_videos_list(),
            ['https://example.com/first', 'https://example.com/second'],
        )
        metadata = json.loads(first.source_metadata)
        self.assertEqual(
            metadata['osm_import']['member_keys'],
            [
                {'type': 'way', 'id': '7001'},
                {'type': 'way', 'id': '7002'},
            ],
        )
        self.assertEqual(
            metadata['admin_merge']['merged_bikelane_ids'],
            [second.id],
        )
        self.assertEqual(metadata['admin_merge']['merged_by'], self.admin.id)
        self.assertEqual(second.status, 'rejected')
        self.assertEqual(
            second.admin_comment,
            f'Объединено с линией №{first.id}',
        )
        self.assertEqual(BikeLane.query.count(), 3)

    def test_admin_can_merge_lines_with_a_small_endpoint_gap(self):
        first = self._create_bikelane('Первая с небольшим разрывом')
        second = self._create_bikelane('Вторая с небольшим разрывом')
        first.set_geometry_dict({
            'type': 'LineString',
            'coordinates': [[76.9, 43.25], [76.901, 43.251]],
        })
        second.set_geometry_dict({
            'type': 'LineString',
            'coordinates': [[76.902, 43.252], [76.9011, 43.251]],
        })
        db.session.commit()

        response = self.client.post(
            '/admin/bikelanes/bulk-action',
            data={
                'action': 'merge',
                'status_filter': 'pending',
                'bikelane_ids': [str(second.id), str(first.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith(f'/admin/bikelanes/{first.id}'))
        db.session.refresh(first)
        db.session.refresh(second)
        self.assertEqual(
            first.get_geometry_dict()['coordinates'],
            [
                [76.9, 43.25],
                [76.901, 43.251],
                [76.9011, 43.251],
                [76.902, 43.252],
            ],
        )
        self.assertEqual(second.status, 'rejected')

    def test_admin_merge_rejects_a_branch_without_changing_lines(self):
        first = self._create_bikelane('Первая')
        second = self._create_bikelane('Вторая')
        third = self._create_bikelane('Третья')
        center = [76.901, 43.251]
        first.set_geometry_dict({
            'type': 'LineString',
            'coordinates': [[76.9, 43.25], center],
        })
        second.set_geometry_dict({
            'type': 'LineString',
            'coordinates': [center, [76.902, 43.252]],
        })
        third.set_geometry_dict({
            'type': 'LineString',
            'coordinates': [center, [76.903, 43.251]],
        })
        original_geometries = {
            item.id: item.geometry
            for item in (first, second, third)
        }
        db.session.commit()

        response = self.client.post(
            '/admin/bikelanes/bulk-action',
            data={
                'action': 'merge',
                'status_filter': 'pending',
                'bikelane_ids': [
                    str(first.id),
                    str(second.id),
                    str(third.id),
                ],
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Выбранные линии образуют развилку.', response.get_data(as_text=True))
        for item in (first, second, third):
            db.session.refresh(item)
            self.assertEqual(item.status, 'pending')
            self.assertEqual(item.geometry, original_geometries[item.id])

    def test_admin_merge_requires_lines_of_the_same_type(self):
        bikelane = self._create_bikelane('Велодорожка')
        bus_lane = self._create_bikelane('Автобусная полоса')
        bus_lane.track_type = 'bus_lane'
        db.session.commit()

        response = self.client.post(
            '/admin/bikelanes/bulk-action',
            data={
                'action': 'merge',
                'data_type': 'bikelanes',
                'status_filter': 'pending',
                'bikelane_ids': [str(bikelane.id), str(bus_lane.id)],
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'Некоторые выбранные линии не найдены или относятся к другому типу.',
            response.get_data(as_text=True),
        )
        db.session.refresh(bikelane)
        db.session.refresh(bus_lane)
        self.assertEqual(bikelane.status, 'pending')
        self.assertEqual(bus_lane.status, 'pending')

    def test_public_add_still_requires_twenty_character_description(self):
        response = self.client.post('/add-bikelane', data=self._post_data(description='Велополоса'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()['success'])
        self.assertIn('20 символов', response.get_json()['error'])

    def test_public_add_bus_lane_only_requires_street_name_and_geometry(self):
        data = self._post_data(description='')
        data['track_type'] = 'bus_lane'
        data['quality'] = ''
        data['has_parking'] = 'true'
        data['has_markings'] = 'true'
        data['has_signs'] = 'true'
        data['is_one_way'] = 'true'
        data['video_url'] = 'https://example.com/video'

        response = self.client.post('/add-bikelane', data=data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])
        bus_lane = BikeLane.query.filter_by(track_type='bus_lane').one()
        self.assertEqual(bus_lane.title, 'Updated OSM lane')
        self.assertEqual(bus_lane.description, '')
        self.assertEqual(bus_lane.quality, 0)
        self.assertFalse(bus_lane.has_parking)
        self.assertFalse(bus_lane.has_markings)
        self.assertFalse(bus_lane.has_signs)
        self.assertFalse(bus_lane.is_one_way)
        self.assertEqual(bus_lane.get_videos_list(), [])
        self.assertEqual(bus_lane.quality_color, '#3498db')


if __name__ == '__main__':
    unittest.main()
