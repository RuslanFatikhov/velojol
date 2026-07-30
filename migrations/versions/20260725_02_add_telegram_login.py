"""add Telegram subject identifier and allow users without email

Revision ID: 20260725_02
Revises: 20260725_01
Create Date: 2026-07-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260725_02'
down_revision = '20260725_01'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'email',
            existing_type=sa.String(length=120),
            nullable=True,
        )
        batch_op.add_column(
            sa.Column('telegram_sub', sa.String(length=255), nullable=True)
        )
        batch_op.create_index(
            'ix_users_telegram_sub',
            ['telegram_sub'],
            unique=True,
        )


def downgrade():
    # Сохраняем Telegram-пользователей при откате схемы: обязательное поле
    # получает уникальный технический адрес, который не используется для входа.
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE users
            SET email = 'telegram-' || id || '@invalid.local'
            WHERE email IS NULL
            """
        )
    )

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_index('ix_users_telegram_sub')
        batch_op.drop_column('telegram_sub')
        batch_op.alter_column(
            'email',
            existing_type=sa.String(length=120),
            nullable=False,
        )
