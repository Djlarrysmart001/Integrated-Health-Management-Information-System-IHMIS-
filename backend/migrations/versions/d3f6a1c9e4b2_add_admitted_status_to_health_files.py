"""add admitted status to health_files

Revision ID: d3f6a1c9e4b2
Revises: c2a9e4f1b8d3
Create Date: 2026-08-08 00:00:00.000000

Adds "admitted" to the health_files.status ENUM, enabling the
admission-via-Nurse loop:

    with_doctor -> admitted -> (Nurse monitors, records vitals) ->
    with_doctor (Nurse forwards back) -> closed (Doctor discharges)

MySQL ENUM columns require a full MODIFY COLUMN to add a new value —
there's no ALTER TYPE ... ADD VALUE like Postgres.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd3f6a1c9e4b2'
down_revision = 'c2a9e4f1b8d3'
branch_labels = None
depends_on = None

OLD_STATUSES = ("with_mho", "with_nurse", "with_doctor", "with_lab", "with_pharmacy", "closed")
NEW_STATUSES = OLD_STATUSES + ("admitted",)


def upgrade():
    with op.batch_alter_table('health_files', schema=None) as batch_op:
        batch_op.alter_column(
            'status',
            existing_type=sa.Enum(*OLD_STATUSES),
            type_=sa.Enum(*NEW_STATUSES),
            existing_nullable=False,
        )


def downgrade():
    op.execute("UPDATE health_files SET status = 'with_doctor' WHERE status = 'admitted'")
    with op.batch_alter_table('health_files', schema=None) as batch_op:
        batch_op.alter_column(
            'status',
            existing_type=sa.Enum(*NEW_STATUSES),
            type_=sa.Enum(*OLD_STATUSES),
            existing_nullable=False,
        )