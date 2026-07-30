from datetime import datetime
import json

from app import db


class InfrastructurePoint(db.Model):
    """Точечный объект велосипедной инфраструктуры."""

    __tablename__ = 'infrastructure_points'
    __table_args__ = (
        db.Index(
            'uq_infrastructure_points_osm_object',
            'source',
            'osm_type',
            'osm_id',
            unique=True,
        ),
    )

    TYPE_BICYCLE_PARKING = 'bicycle_parking'
    TYPE_REPAIR_STATION = 'bicycle_repair_station'

    COMMON_OSM_ATTRIBUTES = (
        ('operator', 'Оператор', 'text'),
        ('opening_hours', 'Время работы', 'text'),
        ('access', 'Доступ', 'text'),
        ('fee', 'Платная', 'yes_no'),
        ('indoor', 'В помещении', 'yes_no'),
    )
    PARKING_OSM_ATTRIBUTES = (
        ('bicycle_parking', 'Тип велопарковки', 'text'),
        ('capacity', 'Вместимость', 'text'),
        ('covered', 'Крытая', 'yes_no'),
        ('cargo_bike', 'Для грузовых велосипедов', 'text'),
        ('capacity:cargo_bike', 'Мест для грузовых велосипедов', 'text'),
        ('maxstay', 'Максимальное время парковки', 'text'),
        ('surveillance', 'Видеонаблюдение', 'text'),
    )
    REPAIR_OSM_ATTRIBUTES = (
        ('brand', 'Бренд станции', 'text'),
        ('service:bicycle:pump', 'Насос', 'yes_no'),
        ('service:bicycle:tools', 'Инструменты', 'yes_no'),
        ('service:bicycle:chain_tool', 'Выжимка цепи', 'yes_no'),
        ('service:bicycle:stand', 'Ремонтная стойка', 'yes_no'),
        ('service:bicycle:charging', 'Зарядка электровелосипеда', 'yes_no'),
        ('lastcheck:status', 'Состояние при последней проверке', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    city_id = db.Column(db.Integer, db.ForeignKey('cities.id'), nullable=False)
    infrastructure_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='', nullable=False)
    photos = db.Column(db.Text, default='[]', nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(50), default='openstreetmap', nullable=False)
    osm_type = db.Column(db.String(20), nullable=False)
    osm_id = db.Column(db.String(64), nullable=False)
    osm_tags = db.Column(db.Text, nullable=True)
    imported_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    @property
    def type_display(self):
        return {
            self.TYPE_BICYCLE_PARKING: 'Велопарковка',
            self.TYPE_REPAIR_STATION: 'Стойка для ремонта велосипедов',
        }.get(self.infrastructure_type, 'Велоинфраструктура')

    def get_osm_tags(self):
        try:
            value = json.loads(self.osm_tags or '{}')
            return value if isinstance(value, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_photos_list(self):
        try:
            value = json.loads(self.photos or '[]')
            return value if isinstance(value, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_photos_list(self, photos):
        self.photos = json.dumps(photos or [], ensure_ascii=False)

    def get_osm_attributes(self):
        tags = self.get_osm_tags()
        type_attributes = (
            self.PARKING_OSM_ATTRIBUTES
            if self.infrastructure_type == self.TYPE_BICYCLE_PARKING
            else self.REPAIR_OSM_ATTRIBUTES
        )
        attributes = []

        for key, label, value_type in self.COMMON_OSM_ATTRIBUTES + type_attributes:
            value = tags.get(key)
            if value is None or str(value).strip() == '':
                continue
            attributes.append({
                'key': key,
                'label': label,
                'value': value,
                'value_type': value_type,
            })

        return attributes

    def to_dict(self):
        tags = self.get_osm_tags()
        return {
            'id': self.id,
            'type': self.infrastructure_type,
            'type_display': self.type_display,
            'title': self.title,
            'description': self.description or '',
            'photos': self.get_photos_list(),
            'attributes': self.get_osm_attributes(),
            'coordinates': [self.longitude, self.latitude],
            'capacity': tags.get('capacity'),
            'covered': tags.get('covered'),
            'access': tags.get('access'),
            'fee': tags.get('fee'),
            'opening_hours': tags.get('opening_hours'),
            'osm_type': self.osm_type,
            'osm_id': self.osm_id,
        }
