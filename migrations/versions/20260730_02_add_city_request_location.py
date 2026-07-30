"""add location details to city requests

Revision ID: 20260730_02
Revises: 20260730_01
Create Date: 2026-07-30 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260730_02'
down_revision = '20260730_01'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'city_requests',
        sa.Column(
            'location_fail',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'city_requests',
        sa.Column('latitude', sa.Float(), nullable=True),
    )
    op.add_column(
        'city_requests',
        sa.Column('longitude', sa.Float(), nullable=True),
    )


def downgrade():
    op.drop_column('city_requests', 'longitude')
    op.drop_column('city_requests', 'latitude')
    op.drop_column('city_requests', 'location_fail')
