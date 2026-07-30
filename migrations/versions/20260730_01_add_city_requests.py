"""add city requests

Revision ID: 20260730_01
Revises: 20260726_05
Create Date: 2026-07-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260730_01'
down_revision = '20260726_05'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'city_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('city_name', sa.String(length=120), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_city_requests_user_id',
        'city_requests',
        ['user_id'],
    )


def downgrade():
    op.drop_index(
        'ix_city_requests_user_id',
        table_name='city_requests',
    )
    op.drop_table('city_requests')
