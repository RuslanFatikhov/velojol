from app import db
from datetime import datetime


class Notification(db.Model):
    """
    Модель уведомлений для пользователей
    """
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Получатель уведомления
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Тип уведомления
    type = db.Column(db.Enum(
        'bikelane_approved', 
        'bikelane_rejected', 
        'bikelane_pending',
        name='notification_type'
    ), nullable=False)
    
    # Заголовок и текст уведомления
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    # Связанный объект (велодорожка)
    bikelane_id = db.Column(db.Integer, db.ForeignKey('bikelanes.id'), nullable=True)
    
    # Статус прочтения
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    
    # Временные метки
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # Связи
    bikelane = db.relationship('BikeLane', backref='notifications')
    
    def __repr__(self):
        return f'<Notification {self.title}>'
    
    def mark_as_read(self):
        """Отметить уведомление как прочитанное"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
    
    @classmethod
    def create_bikelane_approved(cls, user, bikelane, admin_comment=None):
        """Создать уведомление об одобрении велодорожки"""
        message = f'Ваша велодорожка "{bikelane.title}" была одобрена!'
        if admin_comment:
            message += f'\n\nКомментарий модератора: {admin_comment}'
        
        notification = cls(
            user_id=user.id,
            type='bikelane_approved',
            title='Велодорожка одобрена',
            message=message,
            bikelane_id=bikelane.id
        )
        
        db.session.add(notification)
        return notification
