"""add osm import fields to bikelanes

Revision ID: 20260614_01
Revises: 20260609_01
Create Date: 2026-06-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260614_01'
down_revision = '20260609_01'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'bikelanes',
        sa.Column('source', sa.String(length=50), nullable=False, server_default='manual')
    )
    op.add_column('bikelanes', sa.Column('osm_type', sa.String(length=20), nullable=True))
    op.add_column('bikelanes', sa.Column('osm_id', sa.String(length=64), nullable=True))
    op.add_column('bikelanes', sa.Column('osm_tags', sa.Text(), nullable=True))
    op.add_column('bikelanes', sa.Column('imported_at', sa.DateTime(), nullable=True))
    op.add_column('bikelanes', sa.Column('import_job_id', sa.Integer(), nullable=True))
    op.create_index(
        'uq_bikelanes_osm_source_object',
        'bikelanes',
        ['source', 'osm_type', 'osm_id'],
        unique=True
    )


def downgrade():
    op.drop_index('uq_bikelanes_osm_source_object', table_name='bikelanes')
    op.drop_column('bikelanes', 'import_job_id')
    op.drop_column('bikelanes', 'imported_at')
    op.drop_column('bikelanes', 'osm_tags')
    op.drop_column('bikelanes', 'osm_id')
    op.drop_column('bikelanes', 'osm_type')
    op.drop_column('bikelanes', 'source')
