# app/models/medical_record.py

from datetime import datetime, timezone
from app.extensions import db


class MedicalRecord(db.Model):
    """
    One master medical record per patient.
    Stores background health information: allergies, chronic conditions,
    surgical history, etc. Created when a patient is first registered.
    """
    __tablename__ = "medical_records"

    id                   = db.Column(db.Integer, primary_key=True)
    patient_id           = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"),
                                     unique=True, nullable=False)
    known_allergies      = db.Column(db.Text, nullable=True)
    chronic_conditions   = db.Column(db.Text, nullable=True)
    current_medications  = db.Column(db.Text, nullable=True)
    surgical_history     = db.Column(db.Text, nullable=True)
    family_history       = db.Column(db.Text, nullable=True)
    immunization_history = db.Column(db.Text, nullable=True)
    notes                = db.Column(db.Text, nullable=True)
    created_by           = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by           = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at           = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at           = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                                     onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id":                   self.id,
            "patient_id":           self.patient_id,
            "known_allergies":      self.known_allergies,
            "chronic_conditions":   self.chronic_conditions,
            "current_medications":  self.current_medications,
            "surgical_history":     self.surgical_history,
            "family_history":       self.family_history,
            "immunization_history": self.immunization_history,
            "notes":                self.notes,
            "updated_at":           self.updated_at.isoformat() if self.updated_at else None,
        }