"""add Google subject identifier to users

Revision ID: 20260713_01
Revises: 20260614_01
Create Date: 2026-07-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260713_01'
down_revision = '20260614_01'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('google_sub', sa.String(length=255), nullable=True))
    op.create_index('ix_users_google_sub', 'users', ['google_sub'], unique=True)


def downgrade():
    op.drop_index('ix_users_google_sub', table_name='users')
    op.drop_column('users', 'google_sub')
