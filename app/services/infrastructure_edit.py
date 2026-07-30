import json
import math

from app.models.infrastructure_point import InfrastructurePoint


YES_NO_OPTIONS = (
    ('', 'Не указано'),
    ('yes', 'Да'),
    ('no', 'Нет'),
)

COMMON_FIELDS = (
    {
        'name': 'fee',
        'label': 'Стоимость',
        'type': 'select',
        'options': (
            ('', 'Не указано'),
            ('no', 'Бесплатная'),
            ('yes', 'Платная'),
        ),
    },
    {
        'name': 'access',
        'label': 'Доступ',
        'type': 'select',
        'options': (
            ('', 'Не указано'),
            ('yes', 'Свободный'),
            ('customers', 'Только для клиентов'),
            ('permissive', 'Разрешён владельцем'),
            ('private', 'Частный'),
            ('no', 'Нет доступа'),
        ),
    },
    {
        'name': 'indoor',
        'label': 'В помещении',
        'type': 'select',
        'options': YES_NO_OPTIONS,
    },
    {
        'name': 'opening_hours',
        'label': 'Время работы',
        'type': 'text',
        'placeholder': 'Например, 24/7 или Mo-Fr 09:00-18:00',
    },
    {
        'name': 'operator',
        'label': 'Оператор',
        'type': 'text',
        'placeholder': 'Организация или владелец',
    },
)

PARKING_FIELDS = (
    {
        'name': 'bicycle_parking',
        'label': 'Тип велопарковки',
        'type': 'select',
        'options': (
            ('', 'Не указано'),
            ('stands', 'П-образные стойки'),
            ('rack', 'Решётка'),
            ('wall_loops', 'Колесодержатели'),
            ('lockers', 'Велобоксы'),
            ('shed', 'Навес или павильон'),
            ('building', 'Отдельное здание'),
            ('floor', 'Разметка на площадке'),
            ('informal', 'Неофициальная парковка'),
        ),
    },
    {
        'name': 'capacity',
        'label': 'Количество мест',
        'type': 'number',
        'placeholder': 'Например, 12',
    },
    {
        'name': 'covered',
        'label': 'Крытая',
        'type': 'select',
        'options': (
            ('', 'Не указано'),
            ('yes', 'Крытая'),
            ('no', 'Не крытая'),
        ),
    },
    {
        'name': 'cargo_bike',
        'label': 'Для грузовых велосипедов',
        'type': 'select',
        'options': (
            ('', 'Не указано'),
            ('yes', 'Подходит'),
            ('designated', 'Есть специальные места'),
            ('no', 'Не подходит'),
        ),
    },
    {
        'name': 'capacity:cargo_bike',
        'label': 'Мест для грузовых велосипедов',
        'type': 'number',
        'placeholder': 'Например, 2',
    },
    {
        'name': 'surveillance',
        'label': 'Видеонаблюдение',
        'type': 'select',
        'options': YES_NO_OPTIONS,
    },
    {
        'name': 'maxstay',
        'label': 'Максимальное время парковки',
        'type': 'text',
        'placeholder': 'Например, 24 hours',
    },
)

REPAIR_FIELDS = (
    {
        'name': 'brand',
        'label': 'Бренд станции',
        'type': 'text',
        'placeholder': 'Производитель или бренд',
    },
    {
        'name': 'service:bicycle:pump',
        'label': 'Насос',
        'type': 'select',
        'options': YES_NO_OPTIONS,
    },
    {
        'name': 'service:bicycle:tools',
        'label': 'Инструменты',
        'type': 'select',
        'options': YES_NO_OPTIONS,
    },
    {
        'name': 'service:bicycle:chain_tool',
        'label': 'Выжимка цепи',
        'type': 'select',
        'options': YES_NO_OPTIONS,
    },
    {
        'name': 'service:bicycle:stand',
        'label': 'Ремонтная стойка',
        'type': 'select',
        'options': YES_NO_OPTIONS,
    },
    {
        'name': 'service:bicycle:charging',
        'label': 'Зарядка электровелосипеда',
        'type': 'select',
        'options': YES_NO_OPTIONS,
    },
    {
        'name': 'lastcheck:status',
        'label': 'Состояние',
        'type': 'select',
        'options': (
            ('', 'Не указано'),
            ('working', 'Работает'),
            ('partially_working', 'Работает частично'),
            ('broken', 'Не работает'),
        ),
    },
)


def infrastructure_form_fields(point):
    tags = point.get_osm_tags()
    type_fields = (
        PARKING_FIELDS
        if point.infrastructure_type == InfrastructurePoint.TYPE_BICYCLE_PARKING
        else REPAIR_FIELDS
    )
    return [
        {**field, 'value': str(tags.get(field['name'], '') or '')}
        for field in COMMON_FIELDS + type_fields
    ]


def apply_infrastructure_form(point, form):
    title = form.get('title', '').strip()
    description = form.get('description', '').strip()
    if len(title) < 3:
        raise ValueError('Название должно содержать минимум 3 символа.')

    try:
        latitude = float(form.get('latitude', ''))
        longitude = float(form.get('longitude', ''))
    except (TypeError, ValueError):
        raise ValueError('Укажите корректное положение метки на карте.') from None
    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise ValueError('Укажите корректное положение метки на карте.')

    fields = infrastructure_form_fields(point)
    tags = point.get_osm_tags()
    for field in fields:
        name = field['name']
        value = form.get(name, '').strip()
        if not value:
            tags.pop(name, None)
            continue

        if field['type'] == 'select':
            allowed = {option_value for option_value, _label in field['options']}
            if value not in allowed:
                raise ValueError(f'Недопустимое значение поля «{field["label"]}».')
        elif field['type'] == 'number':
            try:
                number = int(value)
            except ValueError:
                raise ValueError(
                    f'Поле «{field["label"]}» должно быть целым числом.'
                ) from None
            if number < 0:
                raise ValueError(
                    f'Поле «{field["label"]}» не может быть отрицательным.'
                )
            value = str(number)
        elif len(value) > 200:
            raise ValueError(
                f'Поле «{field["label"]}» не должно превышать 200 символов.'
            )

        tags[name] = value

    tags['name'] = title
    if description:
        tags['description'] = description
    else:
        tags.pop('description', None)

    point.title = title
    point.description = description
    point.latitude = latitude
    point.longitude = longitude
    point.osm_tags = json.dumps(tags, ensure_ascii=False, sort_keys=True)
