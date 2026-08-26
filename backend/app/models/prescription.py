# app/models/prescription.py

from datetime import datetime, timezone
from app.extensions import db


class Prescription(db.Model):
    """
    Header record for a prescription written during a consultation.
    One consultation can have multiple prescriptions over time.
    """
    __tablename__ = "prescriptions"

    id              = db.Column(db.Integer, primary_key=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey("consultations.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    patient_id      = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    prescribed_by   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status          = db.Column(
        db.Enum("pending", "dispensed", "partially_dispensed", "cancelled"),
        default="pending",
        nullable=False,
    )
    notes           = db.Column(db.Text, nullable=True)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                                onupdate=lambda: datetime.now(timezone.utc))

    # ── relationships ──────────────────────────────────────────
    prescribed_by_user = db.relationship("User", foreign_keys=[prescribed_by],
                                         backref="prescriptions_written")
    items              = db.relationship("PrescriptionItem", backref="prescription",
                                         lazy="joined", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":              self.id,
            "consultation_id": self.consultation_id,
            "patient_id":      self.patient_id,
            "prescribed_by":   self.prescribed_by,
            "status":          self.status,
            "notes":           self.notes,
            "items":           [item.to_dict() for item in self.items],
            "created_at":      self.created_at.isoformat(),
        }


class PrescriptionItem(db.Model):
    """
    Each individual drug line on a prescription.
    """
    __tablename__ = "prescription_items"

    id              = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey("prescriptions.id", ondelete="CASCADE"),
                                nullable=False)
    drug_id         = db.Column(db.Integer, db.ForeignKey("drugs.id"), nullable=False)
    dosage          = db.Column(db.String(60), nullable=True)    # e.g. "500mg"
    frequency       = db.Column(db.String(60), nullable=True)    # e.g. "3 times daily"
    duration        = db.Column(db.String(60), nullable=True)    # e.g. "5 days"
    quantity        = db.Column(db.Integer, nullable=True)
    instructions    = db.Column(db.Text, nullable=True)
    is_dispensed    = db.Column(db.Boolean, default=False)
    dispensed_at    = db.Column(db.DateTime, nullable=True)
    dispensed_by    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    def to_dict(self):
        return {
            "id":                     self.id,
            "drug_id":                self.drug_id,
            "drug_name":              self.drug.name if self.drug else None,
            # Lets the frontend show a "NEW — needs Pharmacy setup" badge
            # on any item whose drug was auto-created from a doctor-typed
            # name, and keep showing it correctly after a page reload —
            # this reflects live state, so it disappears once Pharmacy
            # clears the flag via update_drug.
            "drug_is_pending_setup":  self.drug.is_pending_setup if self.drug else False,
            "dosage":                 self.dosage,
            "frequency":              self.frequency,
            "duration":               self.duration,
            "quantity":               self.quantity,
            "instructions":           self.instructions,
            "is_dispensed":           self.is_dispensed,
            "dispensed_at":           self.dispensed_at.isoformat() if self.dispensed_at else None,
        }