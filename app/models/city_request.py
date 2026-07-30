from datetime import datetime

from app import db


class CityRequest(db.Model):
    """Заявка посетителя на добавление города."""

    __tablename__ = 'city_requests'

    id = db.Column(db.Integer, primary_key=True)
    city_name = db.Column(db.String(120), nullable=False)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=True,
        index=True,
    )
    location_fail = db.Column(db.Boolean, default=False, nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship(
        'User',
        backref=db.backref('city_requests', lazy='dynamic'),
    )
