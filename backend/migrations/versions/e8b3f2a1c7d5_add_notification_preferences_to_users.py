"""add notification_preferences to users

Revision ID: e8b3f2a1c7d5
Revises: d3f6a1c9e4b2
Create Date: 2026-08-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e8b3f2a1c7d5'
down_revision = 'd3f6a1c9e4b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notification_preferences', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('notification_preferences')