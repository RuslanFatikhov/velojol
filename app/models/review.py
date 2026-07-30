from datetime import datetime
import json

from app import db


class Review(db.Model):
    """Оценка и отзыв пользователя об объекте велоинфраструктуры."""

    __tablename__ = 'reviews'
    __table_args__ = (
        db.CheckConstraint(
            'rating >= 1 AND rating <= 5',
            name='ck_reviews_rating_range',
        ),
        db.CheckConstraint(
            '('
            'bikelane_id IS NOT NULL AND infrastructure_point_id IS NULL'
            ') OR ('
            'bikelane_id IS NULL AND infrastructure_point_id IS NOT NULL'
            ')',
            name='ck_reviews_single_target',
        ),
        db.UniqueConstraint(
            'user_id',
            'bikelane_id',
            name='uq_reviews_user_bikelane',
        ),
        db.UniqueConstraint(
            'user_id',
            'infrastructure_point_id',
            name='uq_reviews_user_infrastructure',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=False,
    )
    bikelane_id = db.Column(
        db.Integer,
        db.ForeignKey('bikelanes.id'),
        nullable=True,
    )
    infrastructure_point_id = db.Column(
        db.Integer,
        db.ForeignKey('infrastructure_points.id'),
        nullable=True,
    )
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, default='', nullable=False)
    photos = db.Column(db.Text, default='[]', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = db.relationship(
        'User',
        backref=db.backref('object_reviews', lazy='dynamic'),
    )
    bikelane = db.relationship(
        'BikeLane',
        backref=db.backref(
            'reviews',
            lazy='dynamic',
            cascade='all, delete-orphan',
        ),
    )
    infrastructure_point = db.relationship(
        'InfrastructurePoint',
        backref=db.backref(
            'reviews',
            lazy='dynamic',
            cascade='all, delete-orphan',
        ),
    )

    def get_photos_list(self):
        try:
            value = json.loads(self.photos or '[]')
            return value if isinstance(value, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_photos_list(self, photos):
        self.photos = json.dumps(photos or [], ensure_ascii=False)

    def to_dict(self):
        return {
            'id': self.id,
            'rating': self.rating,
            'text': self.text or '',
            'photos': self.get_photos_list(),
            'created_at': (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
            'updated_at': (
                self.updated_at.isoformat()
                if self.updated_at
                else None
            ),
            'author': {
                'id': self.user.id,
                'nickname': self.user.nickname,
                'avatar': self.user.display_avatar,
            },
        }
