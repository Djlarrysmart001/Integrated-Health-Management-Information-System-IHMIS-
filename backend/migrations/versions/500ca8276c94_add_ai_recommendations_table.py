"""add ai_recommendations table

Revision ID: 500ca8276c94
Revises: 806244e8767b
Create Date: 2026-07-26 23:05:24.055633

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '500ca8276c94'
down_revision = '806244e8767b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ai_recommendations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recommendation_type', sa.String(length=40), nullable=False),
    sa.Column('source_entity_type', sa.String(length=60), nullable=True),
    sa.Column('source_entity_id', sa.Integer(), nullable=True),
    sa.Column('target_role', sa.String(length=60), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('generated_at', sa.DateTime(), nullable=True),
    sa.Column('reviewed_by', sa.Integer(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ai_recommendations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ai_recommendations_recommendation_type'), ['recommendation_type'], unique=False)
        batch_op.create_index('ix_ai_recommendations_source', ['source_entity_type', 'source_entity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_recommendations_status'), ['status'], unique=False)
        batch_op.create_index('ix_ai_recommendations_type_status', ['recommendation_type', 'status'], unique=False)

    # NOTE: Alembic's autogenerate also detected a type change on
    # patient_documents.file_data and patients.photo_data (MEDIUMBLOB ->
    # LargeBinary). That's cosmetic drift from how SQLAlchemy compares
    # MySQL's MEDIUMBLOB against its generic LargeBinary type, not a real
    # schema change — deliberately removed from this migration so those
    # existing BLOB columns are left untouched.


def downgrade():
    with op.batch_alter_table('ai_recommendations', schema=None) as batch_op:
        batch_op.drop_index('ix_ai_recommendations_type_status')
        batch_op.drop_index(batch_op.f('ix_ai_recommendations_status'))
        batch_op.drop_index('ix_ai_recommendations_source')
        batch_op.drop_index(batch_op.f('ix_ai_recommendations_recommendation_type'))

    op.drop_table('ai_recommendations')