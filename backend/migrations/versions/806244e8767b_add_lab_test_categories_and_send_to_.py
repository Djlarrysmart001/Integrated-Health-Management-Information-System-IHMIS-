"""add lab_test_categories and send-to-doctor tracking

Revision ID: 806244e8767b
Revises: be7becdb4104
Create Date: 2026-07-25 10:02:18.680389

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

# revision identifiers, used by Alembic.
revision = '806244e8767b'
down_revision = 'be7becdb4104'
branch_labels = None
depends_on = None


# Full category -> example-test seed list. Edit freely before running the
# migration if you want to add/change anything.
CATEGORY_SEED = [
    ("Haematology", [
        "Full Blood Count (FBC)", "Haemoglobin (Hb)", "Packed Cell Volume (PCV)",
        "White Blood Cell Count (WBC)", "Platelet Count", "ESR", "Blood Film",
    ]),
    ("Blood Grouping & Immunology", [
        "ABO Blood Group", "Rhesus Factor (Rh)", "Genotype", "Sickling Test",
    ]),
    ("Clinical Chemistry / Biochemistry", [
        "Blood Glucose", "Fasting Blood Sugar (FBS)", "Random Blood Sugar (RBS)",
        "Urea", "Creatinine", "Uric Acid", "Electrolytes",
    ]),
    ("Liver Function Tests (LFT)", [
        "ALT", "AST", "ALP", "Total Bilirubin", "Direct Bilirubin", "Total Protein", "Albumin",
    ]),
    ("Lipid Profile", [
        "Total Cholesterol", "HDL", "LDL", "Triglycerides",
    ]),
    ("Renal Function Tests (RFT)", [
        # Urea / Creatinine already seeded under Clinical Chemistry above —
        # skipped here since a test can only belong to one category.
        "Urea", "Creatinine", "Sodium", "Potassium", "Chloride", "Bicarbonate",
    ]),
    ("Microbiology", [
        "Urine Culture", "Blood Culture", "Stool Culture", "Wound Swab Culture", "Sputum Culture",
    ]),
    ("Parasitology", [
        "Malaria Parasite Test", "Stool for Ova and Parasites", "Urine Parasite Examination",
    ]),
    ("Urinalysis", [
        "Urine Routine Examination", "Urine Microscopy", "Urine Pregnancy Test",
        "Urine Protein", "Urine Glucose",
    ]),
    ("Stool Examination", [
        "Stool Routine Examination", "Occult Blood Test", "Ova and Parasites",
    ]),
    ("Serology / Immunology", [
        "Widal Test", "Hepatitis B Surface Antigen (HBsAg)", "Hepatitis C Test",
        "HIV Screening", "VDRL/RPR",
    ]),
    ("Endocrinology / Hormonal Tests", [
        "Thyroid Function Test (T3, T4, TSH)", "Insulin", "Cortisol",
    ]),
    ("Diabetes Tests", [
        # Fasting/Random Blood Sugar already seeded under Clinical Chemistry
        # above — skipped here for the same one-category-per-test reason.
        "Fasting Blood Sugar", "Random Blood Sugar", "HbA1c", "Oral Glucose Tolerance Test (OGTT)",
    ]),
    ("Pregnancy & Reproductive Health", [
        "Pregnancy Test (\u03b2-hCG)", "Semen Analysis", "Vaginal Swab", "High Vaginal Swab",
    ]),
    ("Coagulation / Blood Clotting", [
        "Prothrombin Time (PT)", "INR", "Activated Partial Thromboplastin Time (APTT)",
    ]),
    ("Immunoassay / Rapid Diagnostic Tests", [
        "Malaria Rapid Diagnostic Test", "HIV Rapid Test", "Hepatitis B Rapid Test", "Hepatitis C Rapid Test",
    ]),
    ("Toxicology / Drug Screening", [
        "Urine Drug Screen", "Alcohol Screening",
    ]),
    ("Cytology / Histopathology", [
        "Pap Smear", "Fine Needle Aspiration Cytology", "Tissue Biopsy",
    ]),
]


def upgrade():
    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    # ── 1. Create lab_test_categories ───────────────────────────
    op.create_table(
        'lab_test_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lab_test_categories', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lab_test_categories_name'), ['name'], unique=True)

    lab_test_categories = sa.table(
        'lab_test_categories',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
        sa.column('description', sa.String),
        sa.column('created_at', sa.DateTime),
    )

    # ── 2. lab_requests: send-to-doctor tracking ─────────────────
    # server_default=sa.false() so existing rows get a real value —
    # without it, MySQL rejects adding a NOT NULL column to a non-empty
    # table. Dropped again below once every row has it, to match the
    # model (default=False is enforced in Python, not at the DB level).
    with op.batch_alter_table('lab_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sent_to_doctor', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('sent_to_doctor_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('sent_to_doctor_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_lab_requests_sent_to_doctor_by', 'users', ['sent_to_doctor_by'], ['id'])

    with op.batch_alter_table('lab_requests', schema=None) as batch_op:
        batch_op.alter_column('sent_to_doctor', server_default=None)

    # ── 3. lab_tests: add category_id (old 'category' string column ──
    # is kept for now — it's still needed as the source data for the
    # migration step right below, and gets dropped afterwards).
    with op.batch_alter_table('lab_tests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_lab_tests_category_id'), ['category_id'], unique=False)
        batch_op.create_foreign_key('fk_lab_tests_category_id', 'lab_test_categories', ['category_id'], ['id'])

    lab_tests = sa.table(
        'lab_tests',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
        sa.column('category', sa.String),      # old string column, still present here
        sa.column('category_id', sa.Integer),
        sa.column('is_active', sa.Boolean),
        sa.column('is_pending_setup', sa.Boolean),
    )

    def get_or_create_category(name: str) -> int:
        clean = (name or "Uncategorized").strip() or "Uncategorized"
        existing = bind.execute(
            sa.select(lab_test_categories.c.id).where(
                sa.func.lower(lab_test_categories.c.name) == clean.lower()
            )
        ).first()
        if existing:
            return existing[0]
        result = bind.execute(
            lab_test_categories.insert().values(name=clean, description=None, created_at=now)
        )
        # NOTE: result.inserted_primary_key doesn't work here because
        # lab_test_categories was built with the lightweight sa.table()
        # helper (used deliberately for these data-migration inserts),
        # which carries no primary-key metadata -- SQLAlchemy has no way
        # to know 'id' is the PK, so inserted_primary_key comes back
        # empty. lastrowid reads MySQL's AUTO_INCREMENT value directly
        # and works regardless of that missing metadata.
        return result.lastrowid

    # ── 4. Migrate existing free-text categories into rows ───────
    existing_categories = bind.execute(
        sa.select(sa.distinct(lab_tests.c.category)).where(lab_tests.c.category.isnot(None))
    ).fetchall()

    for (cat_name,) in existing_categories:
        if not cat_name or not cat_name.strip():
            continue
        cat_id = get_or_create_category(cat_name)
        bind.execute(
            lab_tests.update()
            .where(sa.func.lower(lab_tests.c.category) == cat_name.strip().lower())
            .values(category_id=cat_id)
        )

    # Anything left with no category at all (NULL/blank) -> Uncategorized
    uncategorized_id = get_or_create_category("Uncategorized")
    bind.execute(
        lab_tests.update()
        .where(lab_tests.c.category_id.is_(None))
        .values(category_id=uncategorized_id)
    )

    # ── 5. Seed the full category/test list ──────────────────────
    def test_name_exists(name: str) -> bool:
        row = bind.execute(
            sa.select(lab_tests.c.id).where(sa.func.lower(lab_tests.c.name) == name.strip().lower())
        ).first()
        return row is not None

    for category_name, test_names in CATEGORY_SEED:
        cat_id = get_or_create_category(category_name)
        for test_name in test_names:
            if test_name_exists(test_name):
                continue
            bind.execute(
                lab_tests.insert().values(
                    name=test_name.strip(),
                    category_id=cat_id,
                    is_active=True,
                    is_pending_setup=False,
                )
            )

    # ── 6. Drop the old free-text category column ────────────────
    with op.batch_alter_table('lab_tests', schema=None) as batch_op:
        batch_op.drop_column('category')


def downgrade():
    bind = op.get_bind()

    # Restore the old string column and backfill it from the category
    # relationship before dropping the relational structure.
    with op.batch_alter_table('lab_tests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category', sa.String(length=80), nullable=True))

    lab_tests = sa.table(
        'lab_tests',
        sa.column('id', sa.Integer),
        sa.column('category', sa.String),
        sa.column('category_id', sa.Integer),
    )
    lab_test_categories = sa.table(
        'lab_test_categories',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
    )

    categories = bind.execute(sa.select(lab_test_categories.c.id, lab_test_categories.c.name)).fetchall()
    for cat_id, cat_name in categories:
        bind.execute(
            lab_tests.update().where(lab_tests.c.category_id == cat_id).values(category=cat_name)
        )

    with op.batch_alter_table('lab_tests', schema=None) as batch_op:
        batch_op.drop_constraint('fk_lab_tests_category_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_lab_tests_category_id'))
        batch_op.drop_column('category_id')

    with op.batch_alter_table('lab_requests', schema=None) as batch_op:
        batch_op.drop_constraint('fk_lab_requests_sent_to_doctor_by', type_='foreignkey')
        batch_op.drop_column('sent_to_doctor_by')
        batch_op.drop_column('sent_to_doctor_at')
        batch_op.drop_column('sent_to_doctor')

    with op.batch_alter_table('lab_test_categories', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lab_test_categories_name'))

    op.drop_table('lab_test_categories')