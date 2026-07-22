# app/models/immunization.py

from datetime import datetime, timezone
from app.extensions import db


class Immunization(db.Model):
    """
    A single vaccine dose administered to a patient. One row per dose,
    so a multi-dose schedule (e.g. Hepatitis B doses 1/2/3) shows up
    as separate, individually-traceable records — including the batch
    number, which matters if a vaccine batch is later recalled.
    """
    __tablename__ = "immunizations"

    id                 = db.Column(db.Integer, primary_key=True)
    patient_id         = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"),
                                   nullable=False, index=True)
    vaccine_name       = db.Column(db.String(120), nullable=False, index=True)
    dose_number        = db.Column(db.Integer, nullable=False, default=1)
    date_administered  = db.Column(db.Date, nullable=False)
    administered_by    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    batch_number       = db.Column(db.String(60), nullable=True)
    site                = db.Column(db.String(60), nullable=True)   # e.g. "Left deltoid"
    next_dose_due       = db.Column(db.Date, nullable=True)
    adverse_reaction    = db.Column(db.Text, nullable=True)
    notes               = db.Column(db.Text, nullable=True)
    created_at          = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # ── relationships ──────────────────────────────────────────
    patient       = db.relationship("Patient", backref=db.backref(
        "immunizations", lazy="dynamic", cascade="all, delete-orphan"
    ))
    administrator = db.relationship("User", foreign_keys=[administered_by])

    def to_dict(self):
        return {
            "id":                self.id,
            "patient_id":        self.patient_id,
            "patient_name":      self.patient.full_name if self.patient else None,
            "vaccine_name":      self.vaccine_name,
            "dose_number":       self.dose_number,
            "date_administered": self.date_administered.isoformat() if self.date_administered else None,
            "administered_by":   self.administered_by,
            "administered_by_name": self.administrator.full_name if self.administrator else None,
            "batch_number":      self.batch_number,
            "site":              self.site,
            "next_dose_due":     self.next_dose_due.isoformat() if self.next_dose_due else None,
            "adverse_reaction":  self.adverse_reaction,
            "notes":             self.notes,
            "created_at":        self.created_at.isoformat(),
        }