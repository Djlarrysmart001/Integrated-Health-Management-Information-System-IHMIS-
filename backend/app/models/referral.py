# app/models/referral.py

from datetime import datetime, timezone
from app.extensions import db


class Referral(db.Model):
    """Doctor issues a referral to send a patient to an external facility."""
    __tablename__ = "referrals"

    id                    = db.Column(db.Integer, primary_key=True)
    consultation_id       = db.Column(db.Integer, db.ForeignKey("consultations.id", ondelete="CASCADE"),
                                      nullable=False)
    patient_id            = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    referred_by           = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    referred_to_facility  = db.Column(db.String(200), nullable=False)
    reason                = db.Column(db.Text, nullable=True)
    urgency               = db.Column(db.Enum("routine", "urgent", "emergency"), default="routine")
    status                = db.Column(
        db.Enum("issued", "accepted", "completed", "cancelled"), default="issued"
    )
    notes                 = db.Column(db.Text, nullable=True)
    created_at            = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    referred_by_user = db.relationship("User", foreign_keys=[referred_by], backref="referrals_made")

    def to_dict(self):
        return {
            "id":                   self.id,
            "consultation_id":      self.consultation_id,
            "patient_id":           self.patient_id,
            "referred_to_facility": self.referred_to_facility,
            "reason":               self.reason,
            "urgency":              self.urgency,
            "status":               self.status,
            "created_at":           self.created_at.isoformat(),
        }