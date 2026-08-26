# app/models/consultation.py

from datetime import datetime, timezone
from app.extensions import db


class Consultation(db.Model):
    """
    Represents a single clinical visit/encounter.
    A doctor opens a consultation, records findings, attaches diagnoses,
    writes prescriptions, requests lab tests, then closes it.
    """
    __tablename__ = "consultations"

    id                              = db.Column(db.Integer, primary_key=True)
    patient_id                      = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"),
                                                nullable=False, index=True)
    health_file_id                  = db.Column(db.Integer, db.ForeignKey("health_files.id", ondelete="CASCADE"),
                                                nullable=True, index=True)
    doctor_id                       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    visit_date                      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    chief_complaint                 = db.Column(db.Text, nullable=True)
    history_of_presenting_illness   = db.Column(db.Text, nullable=True)
    physical_examination            = db.Column(db.Text, nullable=True)
    clinical_notes                  = db.Column(db.Text, nullable=True)
    status                          = db.Column(db.Enum("open", "closed"), default="open", nullable=False)
    closed_at                       = db.Column(db.DateTime, nullable=True)
    created_at                      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # ── relationships ──────────────────────────────────────────
    doctor        = db.relationship("User", foreign_keys=[doctor_id], backref="consultations")
    diagnoses     = db.relationship("Diagnosis", backref="consultation",
                                    lazy="dynamic", cascade="all, delete-orphan")
    prescriptions = db.relationship("Prescription", backref="consultation",
                                    lazy="dynamic", cascade="all, delete-orphan")
    lab_requests  = db.relationship("LabRequest", backref="consultation",
                                    lazy="dynamic", cascade="all, delete-orphan")
    vital_signs   = db.relationship("VitalSigns", backref="consultation", uselist=False)
    referrals     = db.relationship("Referral", backref="consultation",
                                    lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Consultation {self.id} — {self.status}>"

    def to_dict(self):
        return {
            "id":                            self.id,
            "patient_id":                    self.patient_id,
            "patient_name":                  self.patient.full_name if self.patient else None,
            "patient_number":                self.patient.patient_number if self.patient else None,
            "health_file_id":                self.health_file_id,
            "doctor_id":                     self.doctor_id,
            "doctor_name":                   self.doctor.full_name if self.doctor else None,
            "visit_date":                    self.visit_date.isoformat() if self.visit_date else None,
            "chief_complaint":               self.chief_complaint,
            "history_of_presenting_illness": self.history_of_presenting_illness,
            "physical_examination":          self.physical_examination,
            "clinical_notes":                self.clinical_notes,
            "status":                        self.status,
            "closed_at":                     self.closed_at.isoformat() if self.closed_at else None,
            "created_at":                    self.created_at.isoformat(),
        }


class Diagnosis(db.Model):
    """
    A consultation can have multiple diagnoses (primary + secondary).
    """
    __tablename__ = "diagnoses"

    id               = db.Column(db.Integer, primary_key=True)
    consultation_id  = db.Column(db.Integer, db.ForeignKey("consultations.id", ondelete="CASCADE"),
                                 nullable=False, index=True)
    icd10_code       = db.Column(db.String(10), nullable=True)
    description      = db.Column(db.Text, nullable=False)
    diagnosis_type   = db.Column(db.Enum("primary", "secondary"), default="primary")
    created_by       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id":              self.id,
            "consultation_id": self.consultation_id,
            "icd10_code":      self.icd10_code,
            "description":     self.description,
            "diagnosis_type":  self.diagnosis_type,
            "created_at":      self.created_at.isoformat(),
        }