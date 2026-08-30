"""add doctor assignment and duty status

Revision ID: f4c1a9b2e6d7
Revises: e8b3f2a1c7d5
Create Date: 2026-08-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f4c1a9b2e6d7'
down_revision = 'e8b3f2a1c7d5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_on_duty', sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table('health_files', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('assigned_doctor_id', sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_health_files_assigned_doctor_id',
            'users',
            ['assigned_doctor_id'],
            ['id']
        )


def downgrade():
    with op.batch_alter_table('health_files', schema=None) as batch_op:
        batch_op.drop_constraint('fk_health_files_assigned_doctor_id', type_='foreignkey')
        batch_op.drop_column('assigned_doctor_id')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_on_duty')
