from app import db
from datetime import datetime, timedelta
import secrets
import string

class VerificationCode(db.Model):
    """Модель для хранения кодов верификации email и восстановления пароля"""
    
    __tablename__ = 'verification_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    code = db.Column(db.String(6), nullable=False)
    code_type = db.Column(db.String(20), nullable=False)  # 'registration' или 'password_reset'
    
    # Счетчики попыток
    attempts = db.Column(db.Integer, default=0, nullable=False)
    request_count = db.Column(db.Integer, default=1, nullable=False)  # Количество запросов кода
    
    # Временные метки
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    verified_at = db.Column(db.DateTime, nullable=True)
    
    # Таймауты
    attempt_locked_until = db.Column(db.DateTime, nullable=True)  # Блокировка на 24 часа после 5 попыток
    request_locked_until = db.Column(db.DateTime, nullable=True)  # Блокировка на 1 час после 5 запросов
    
    # Данные регистрации (для registration type)
    registration_data = db.Column(db.JSON, nullable=True)
    
    def __repr__(self):
        return f'<VerificationCode {self.email} - {self.code_type}>'
    
    @staticmethod
    def generate_code():
        """Генерирует 6-значный код"""
        return ''.join(secrets.choice(string.digits) for _ in range(6))
    
    def is_expired(self):
        """Проверяет, истек ли срок действия кода"""
        return datetime.utcnow() > self.expires_at
    
    def is_attempt_locked(self):
        """Проверяет, заблокирован ли пользователь после неудачных попыток"""
        if self.attempt_locked_until:
            return datetime.utcnow() < self.attempt_locked_until
        return False
    
    def is_request_locked(self):
        """Проверяет, заблокирован ли пользователь от запросов новых кодов"""
        if self.request_locked_until:
            return datetime.utcnow() < self.request_locked_until
        return False
    
    def increment_attempts(self):
        """Увеличивает счетчик попыток и блокирует при достижении лимита"""
        self.attempts += 1
        
        # После 5 попыток - блокировка на 24 часа
        if self.attempts >= 5:
            self.attempt_locked_until = datetime.utcnow() + timedelta(hours=24)
        
        db.session.commit()
    
    def increment_request_count(self):
        """Увеличивает счетчик запросов кодов и блокирует при достижении лимита"""
        self.request_count += 1
        
        # После 5 запросов - блокировка на 1 час
        if self.request_count >= 5:
            self.request_locked_until = datetime.utcnow() + timedelta(hours=1)
        
        db.session.commit()
    
    def verify(self):
        """Отмечает код как использованный"""
        self.verified_at = datetime.utcnow()
        db.session.commit()
    
    @staticmethod
    def create_code(email, code_type, registration_data=None):
        """Создает новый код верификации"""
        code = VerificationCode.generate_code()
        expires_at = datetime.utcnow() + timedelta(minutes=15)
        
        verification = VerificationCode(
            email=email,
            code=code,
            code_type=code_type,
            expires_at=expires_at,
            registration_data=registration_data
        )
        
        db.session.add(verification)
        db.session.commit()
        
        return verification
    
    @staticmethod
    def get_active_code(email, code_type):
        """Получает активный код для email и типа"""
        return VerificationCode.query.filter_by(
            email=email,
            code_type=code_type,
            verified_at=None
        ).order_by(VerificationCode.created_at.desc()).first()
