# app/models/admission.py

from datetime import datetime, timezone
from app.extensions import db


class Admission(db.Model):
    """
    Doctor admits a patient for extended observation/care beyond a
    normal walk-in visit (e.g. overnight observation, isolation).
    Like a Referral, admitting a patient ends their normal MHO -> Nurse
    -> Doctor -> Lab -> Pharmacy walk-in flow — they're now an inpatient
    rather than someone waiting in a queue.
    """
    __tablename__ = "admissions"

    STATUSES = ("admitted", "discharged", "transferred")

    id                      = db.Column(db.Integer, primary_key=True)
    patient_id              = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"),
                                        nullable=False, index=True)
    health_file_id          = db.Column(db.Integer, db.ForeignKey("health_files.id"), nullable=True)
    consultation_id         = db.Column(db.Integer, db.ForeignKey("consultations.id"), nullable=True)
    admitted_by             = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ward                    = db.Column(db.String(100), nullable=False)
    bed_number              = db.Column(db.String(20), nullable=True)
    admission_reason        = db.Column(db.Text, nullable=False)
    admission_date          = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expected_discharge_date = db.Column(db.Date, nullable=True)
    actual_discharge_date   = db.Column(db.DateTime, nullable=True)
    discharge_summary       = db.Column(db.Text, nullable=True)
    discharged_by           = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    status                  = db.Column(db.Enum(*STATUSES), default="admitted", nullable=False, index=True)
    created_at              = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # ── relationships ──────────────────────────────────────────
    patient          = db.relationship("Patient", backref=db.backref(
        "admissions", lazy="dynamic", cascade="all, delete-orphan"
    ))
    admitting_doctor  = db.relationship("User", foreign_keys=[admitted_by])
    discharging_user  = db.relationship("User", foreign_keys=[discharged_by])

    def to_dict(self):
        return {
            "id":                      self.id,
            "patient_id":              self.patient_id,
            "patient_name":            self.patient.full_name if self.patient else None,
            "health_file_id":          self.health_file_id,
            "consultation_id":         self.consultation_id,
            "admitted_by":             self.admitted_by,
            "admitted_by_name":        self.admitting_doctor.full_name if self.admitting_doctor else None,
            "ward":                    self.ward,
            "bed_number":              self.bed_number,
            "admission_reason":        self.admission_reason,
            "admission_date":          self.admission_date.isoformat() if self.admission_date else None,
            "expected_discharge_date": self.expected_discharge_date.isoformat() if self.expected_discharge_date else None,
            "actual_discharge_date":   self.actual_discharge_date.isoformat() if self.actual_discharge_date else None,
            "discharge_summary":       self.discharge_summary,
            "discharged_by":           self.discharged_by,
            "discharged_by_name":      self.discharging_user.full_name if self.discharging_user else None,
            "status":                  self.status,
            "created_at":              self.created_at.isoformat(),
        }