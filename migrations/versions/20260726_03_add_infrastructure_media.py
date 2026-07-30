"""add infrastructure descriptions and photos

Revision ID: 20260726_03
Revises: 20260726_02
Create Date: 2026-07-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260726_03'
down_revision = '20260726_02'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('infrastructure_points') as batch_op:
        batch_op.add_column(
            sa.Column(
                'description',
                sa.Text(),
                nullable=False,
                server_default='',
            )
        )
        batch_op.add_column(
            sa.Column(
                'photos',
                sa.Text(),
                nullable=False,
                server_default='[]',
            )
        )


def downgrade():
    with op.batch_alter_table('infrastructure_points') as batch_op:
        batch_op.drop_column('photos')
        batch_op.drop_column('description')
