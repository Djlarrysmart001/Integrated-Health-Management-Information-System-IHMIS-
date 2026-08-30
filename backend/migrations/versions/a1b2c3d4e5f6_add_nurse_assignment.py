"""add nurse assignment

Revision ID: a1b2c3d4e5f6
Revises: f4c1a9b2e6d7
Create Date: 2026-08-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f4c1a9b2e6d7'
branch_labels = None
depends_on = None


def upgrade():
    # No users-table change needed here -- is_on_duty already exists
    # (added in f4c1a9b2e6d7) and was always a generic boolean; it's
    # simply no longer restricted to the Doctor role at the service layer.
    with op.batch_alter_table('health_files', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('assigned_nurse_id', sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_health_files_assigned_nurse_id',
            'users',
            ['assigned_nurse_id'],
            ['id']
        )


def downgrade():
    with op.batch_alter_table('health_files', schema=None) as batch_op:
        batch_op.drop_constraint('fk_health_files_assigned_nurse_id', type_='foreignkey')
        batch_op.drop_column('assigned_nurse_id')