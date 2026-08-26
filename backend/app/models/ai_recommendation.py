# app/models/ai_recommendation.py

from datetime import datetime, timezone
from app.extensions import db


class AIRecommendation(db.Model):
    """
    A single advisory suggestion produced by any AI/rule-based service in the
    system (Triage Assistant, Clinical Decision Support, Inventory Forecast,
    Access Anomaly Detector).

    Design intent (per IHMIS addendum, section 3 — Class Diagram):
      - This table is STRICTLY ADVISORY. No row here ever writes to a
        Consultation, Prescription, VitalSigns, or DrugInventory record
        directly. The responsible clinical/operational role must explicitly
        accept a recommendation (status -> "accepted") before it has any
        effect on the patient record or inventory — and even then, the
        accepting service is what performs the real write, not this model.
      - Every recommendation generated, and every accept/dismiss decision,
        is also written to AuditLog via AuditService.log(), so this table
        is a supplement to the audit trail, not a replacement for it.

    recommendation_type (kept as a plain string, not Enum, so new AI
    features can be added without a migration — validated at the service
    layer instead):
        TRIAGE_SCORE            -> Nurse, derived from a VitalSigns record
        DRUG_INTERACTION        -> Doctor, derived from a Prescription/Consultation
        DIFFERENTIAL_DIAGNOSIS  -> Doctor, derived from a Consultation
        INVENTORY_FORECAST      -> Pharmacist, derived from a Drug
        ACCESS_ANOMALY          -> Admin, derived from AuditLog activity

    source_entity_type / source_entity_id mirror the same pattern already
    used by AuditLog.entity_type / AuditLog.entity_id, so lookups like
    "all AI recommendations for VitalSigns #42" are consistent with how
    AuditService.get_entity_history() already works.
    """
    __tablename__ = "ai_recommendations"

    STATUSES = ("pending", "accepted", "dismissed")

    __table_args__ = (
        db.Index("ix_ai_recommendations_source", "source_entity_type", "source_entity_id"),
        db.Index("ix_ai_recommendations_type_status", "recommendation_type", "status"),
    )

    id                  = db.Column(db.Integer, primary_key=True)

    recommendation_type = db.Column(db.String(40), nullable=False, index=True)

    # What this recommendation is ABOUT (e.g. "VitalSigns", 42)
    source_entity_type  = db.Column(db.String(60), nullable=True)
    source_entity_id    = db.Column(db.Integer, nullable=True)

    # Which role this recommendation is meant to be reviewed by.
    # NOTE: stored as plain string matching Roles.* constants rather than
    # a FK, since it's a target audience, not a specific user.
    target_role         = db.Column(db.String(60), nullable=False)

    # The actual suggestion content — shape depends on recommendation_type.
    # e.g. {"score": 7, "band": "Urgent", "reasons": [...]}
    #      {"interacting_drugs": ["Drug A", "Drug B"], "severity": "high"}
    #      {"drug_id": 12, "projected_days_remaining": 5, "avg_daily_use": 3.2}
    payload              = db.Column(db.JSON, nullable=False)

    status               = db.Column(db.String(20), nullable=False,
                                     default="pending", index=True)

    generated_at         = db.Column(db.DateTime,
                                     default=lambda: datetime.now(timezone.utc))

    reviewed_by          = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at          = db.Column(db.DateTime, nullable=True)

    # ── relationships ──────────────────────────────────────────
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])

    def to_dict(self):
        return {
            "id":                  self.id,
            "recommendation_type": self.recommendation_type,
            "source_entity_type":  self.source_entity_type,
            "source_entity_id":    self.source_entity_id,
            "target_role":         self.target_role,
            "payload":             self.payload,
            "status":              self.status,
            "generated_at":        self.generated_at.isoformat() if self.generated_at else None,
            "reviewed_by":         self.reviewed_by,
            "reviewed_by_name":    self.reviewer.full_name if self.reviewer else None,
            "reviewed_at":         self.reviewed_at.isoformat() if self.reviewed_at else None,
        }