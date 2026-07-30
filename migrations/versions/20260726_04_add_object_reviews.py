"""add reviews for map objects

Revision ID: 20260726_04
Revises: 20260726_03
Create Date: 2026-07-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260726_04'
down_revision = '20260726_03'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('bikelane_id', sa.Integer(), nullable=True),
        sa.Column('infrastructure_point_id', sa.Integer(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False, server_default=''),
        sa.Column('photos', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            'rating >= 1 AND rating <= 5',
            name='ck_reviews_rating_range',
        ),
        sa.CheckConstraint(
            '('
            'bikelane_id IS NOT NULL AND infrastructure_point_id IS NULL'
            ') OR ('
            'bikelane_id IS NULL AND infrastructure_point_id IS NOT NULL'
            ')',
            name='ck_reviews_single_target',
        ),
        sa.ForeignKeyConstraint(['bikelane_id'], ['bikelanes.id']),
        sa.ForeignKeyConstraint(
            ['infrastructure_point_id'],
            ['infrastructure_points.id'],
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id',
            'bikelane_id',
            name='uq_reviews_user_bikelane',
        ),
        sa.UniqueConstraint(
            'user_id',
            'infrastructure_point_id',
            name='uq_reviews_user_infrastructure',
        ),
    )
    op.create_index(
        'ix_reviews_bikelane_id',
        'reviews',
        ['bikelane_id'],
    )
    op.create_index(
        'ix_reviews_infrastructure_point_id',
        'reviews',
        ['infrastructure_point_id'],
    )


def downgrade():
    op.drop_index(
        'ix_reviews_infrastructure_point_id',
        table_name='reviews',
    )
    op.drop_index(
        'ix_reviews_bikelane_id',
        table_name='reviews',
    )
    op.drop_table('reviews')
