"""add banner responses

Revision ID: 20260609_01
Revises: 
Create Date: 2026-06-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260609_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'banner_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('banner_key', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('cookie_id', sa.String(length=64), nullable=True),
        sa.Column('answer', sa.String(length=8), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("answer IN ('yes', 'no')", name='ck_banner_response_answer'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('banner_key', 'cookie_id', name='uq_banner_response_cookie'),
        sa.UniqueConstraint('banner_key', 'user_id', name='uq_banner_response_user')
    )
    op.create_index(
        'ix_banner_response_banner_answer',
        'banner_responses',
        ['banner_key', 'answer'],
        unique=False
    )


def downgrade():
    op.drop_index('ix_banner_response_banner_answer', table_name='banner_responses')
    op.drop_table('banner_responses')
