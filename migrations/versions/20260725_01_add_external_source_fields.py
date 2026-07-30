"""add generic external source fields to bikelanes

Revision ID: 20260725_01
Revises: 20260713_01
Create Date: 2026-07-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260725_01'
down_revision = '20260713_01'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'bikelanes',
        sa.Column('external_id', sa.String(length=160), nullable=True)
    )
    op.add_column(
        'bikelanes',
        sa.Column('source_metadata', sa.Text(), nullable=True)
    )
    op.create_index(
        'uq_bikelanes_source_external_id',
        'bikelanes',
        ['source', 'external_id'],
        unique=True
    )


def downgrade():
    op.drop_index('uq_bikelanes_source_external_id', table_name='bikelanes')
    op.drop_column('bikelanes', 'source_metadata')
    op.drop_column('bikelanes', 'external_id')
