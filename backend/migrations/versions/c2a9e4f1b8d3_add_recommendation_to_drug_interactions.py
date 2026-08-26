"""add recommendation to drug_interactions

Revision ID: c2a9e4f1b8d3
Revises: b157159e866f
Create Date: 2026-08-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c2a9e4f1b8d3'
down_revision = 'b157159e866f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('drug_interactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('recommendation', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('drug_interactions', schema=None) as batch_op:
        batch_op.drop_column('recommendation')