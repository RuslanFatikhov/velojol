"""add one-way attribute to bikelanes

Revision ID: 20260726_01
Revises: 20260725_02
Create Date: 2026-07-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260726_01'
down_revision = '20260725_02'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'bikelanes',
        sa.Column(
            'is_one_way',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_column('bikelanes', 'is_one_way')
