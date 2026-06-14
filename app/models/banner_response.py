from datetime import datetime

from app import db


class BannerResponse(db.Model):
    """Ответ пользователя на интерактивный баннер."""
    __tablename__ = 'banner_responses'

    id = db.Column(db.Integer, primary_key=True)
    banner_key = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    cookie_id = db.Column(db.String(64), nullable=True)
    answer = db.Column(db.String(8), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('banner_key', 'user_id', name='uq_banner_response_user'),
        db.UniqueConstraint('banner_key', 'cookie_id', name='uq_banner_response_cookie'),
        db.CheckConstraint("answer IN ('yes', 'no')", name='ck_banner_response_answer'),
        db.Index('ix_banner_response_banner_answer', 'banner_key', 'answer'),
    )
