"""add bicycle infrastructure points

Revision ID: 20260726_02
Revises: 20260726_01
Create Date: 2026-07-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260726_02'
down_revision = '20260726_01'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'infrastructure_points',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('city_id', sa.Integer(), nullable=False),
        sa.Column('infrastructure_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column(
            'source',
            sa.String(length=50),
            nullable=False,
            server_default='openstreetmap',
        ),
        sa.Column('osm_type', sa.String(length=20), nullable=False),
        sa.Column('osm_id', sa.String(length=64), nullable=False),
        sa.Column('osm_tags', sa.Text(), nullable=True),
        sa.Column('imported_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['city_id'], ['cities.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_infrastructure_points_osm_object',
        'infrastructure_points',
        ['source', 'osm_type', 'osm_id'],
        unique=True,
    )


def downgrade():
    op.drop_index(
        'uq_infrastructure_points_osm_object',
        table_name='infrastructure_points',
    )
    op.drop_table('infrastructure_points')
