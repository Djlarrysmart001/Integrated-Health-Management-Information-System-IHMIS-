# app/models/drug_interaction.py

from datetime import datetime, timezone
from app.extensions import db


class DrugInteraction(db.Model):
    """
    A single known drug-drug interaction pair, used by the Clinical Decision
    Support service to warn the Doctor when a prescription contains two
    interacting drugs.

    Deliberately references real Drug rows (drug_id_a / drug_id_b), not free
    text — this keeps it consistent with the existing catalogue and the
    is_pending_setup pattern already used for typed drug names that don't
    match an existing entry (see PharmacyService.find_or_create_by_name).

    Like every other AI touchpoint in this system, this is a knowledge-based
    lookup, not a trained model: the pairs and severities below were sourced
    from a published clinical reference (see `source` field per row) rather
    than learned from data. This is a small, illustrative seed set for a
    single-clinic capstone deployment, NOT a comprehensive interaction
    database — a real deployment would need pharmacist-reviewed data from a
    licensed drug-interaction service.

    Storage convention: drug_id_a is always the smaller of the two IDs, to
    avoid storing the same pair twice in reverse order. The lookup service
    normalizes any pair before querying, so callers never need to know this.
    """
    __tablename__ = "drug_interactions"

    SEVERITIES = ("major", "moderate", "minor")

    __table_args__ = (
        db.UniqueConstraint("drug_id_a", "drug_id_b", name="uq_drug_interaction_pair"),
        db.Index("ix_drug_interaction_drug_a", "drug_id_a"),
        db.Index("ix_drug_interaction_drug_b", "drug_id_b"),
    )

    id          = db.Column(db.Integer, primary_key=True)

    drug_id_a   = db.Column(db.Integer, db.ForeignKey("drugs.id"), nullable=False)
    drug_id_b   = db.Column(db.Integer, db.ForeignKey("drugs.id"), nullable=False)

    severity    = db.Column(db.String(20), nullable=False)  # major | moderate | minor
    description = db.Column(db.Text, nullable=False)

    # Advisory next-step for the Doctor: an alternative drug to consider, a
    # monitoring step, or a dosing-spacing note -- the "what to do about it"
    # that pairs with `description`'s "why it's a problem". Same knowledge-
    # base sourcing as description/source; never auto-applied, the Doctor
    # decides. Nullable so older/edge-case pairs can omit it gracefully.
    recommendation = db.Column(db.Text, nullable=True)

    source       = db.Column(db.String(255), nullable=True)  # citation, for the report/audit trail

    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # ── relationships ──────────────────────────────────────────
    drug_a = db.relationship("Drug", foreign_keys=[drug_id_a])
    drug_b = db.relationship("Drug", foreign_keys=[drug_id_b])

    def to_dict(self):
        return {
            "id":          self.id,
            "drug_id_a":   self.drug_id_a,
            "drug_a_name": self.drug_a.name if self.drug_a else None,
            "drug_id_b":   self.drug_id_b,
            "drug_b_name": self.drug_b.name if self.drug_b else None,
            "severity":    self.severity,
            "description": self.description,
            "recommendation": self.recommendation,
            "source":      self.source,
        }