# app/models/medical_certificate.py

from datetime import datetime, timezone
from app.extensions import db


class MedicalCertificate(db.Model):
    """
    A formal certificate issued by a Doctor — sick leave, fitness to
    resume duty/school, or a general medical report. Each certificate
    gets a unique, human-readable number so it can be verified later
    (e.g. by a department checking a submitted sick note).
    """
    __tablename__ = "medical_certificates"

    CERTIFICATE_TYPES = ("sick_leave", "fitness", "medical_report", "other")
    STATUSES          = ("active", "revoked")

    id                  = db.Column(db.Integer, primary_key=True)
    certificate_number  = db.Column(db.String(30), unique=True, nullable=False, index=True)
    patient_id          = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"),
                                    nullable=False, index=True)
    consultation_id     = db.Column(db.Integer, db.ForeignKey("consultations.id"), nullable=True)
    issued_by           = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    certificate_type    = db.Column(db.Enum(*CERTIFICATE_TYPES), nullable=False, default="sick_leave")
    reason              = db.Column(db.Text, nullable=False)
    valid_from          = db.Column(db.Date, nullable=False)
    valid_to            = db.Column(db.Date, nullable=True)
    status              = db.Column(db.Enum(*STATUSES), default="active", nullable=False)
    revoked_by          = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    revoked_at          = db.Column(db.DateTime, nullable=True)
    revoke_reason       = db.Column(db.Text, nullable=True)
    issued_at           = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at          = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # ── relationships ──────────────────────────────────────────
    patient      = db.relationship("Patient", backref=db.backref(
        "medical_certificates", lazy="dynamic", cascade="all, delete-orphan"
    ))
    consultation = db.relationship("Consultation", backref="medical_certificates")
    issuer       = db.relationship("User", foreign_keys=[issued_by])
    revoker      = db.relationship("User", foreign_keys=[revoked_by])

    def to_dict(self):
        return {
            "id":                 self.id,
            "certificate_number": self.certificate_number,
            "patient_id":         self.patient_id,
            "patient_name":       self.patient.full_name if self.patient else None,
            "consultation_id":    self.consultation_id,
            "issued_by":          self.issued_by,
            "issued_by_name":     self.issuer.full_name if self.issuer else None,
            "certificate_type":   self.certificate_type,
            "reason":             self.reason,
            "valid_from":         self.valid_from.isoformat() if self.valid_from else None,
            "valid_to":           self.valid_to.isoformat() if self.valid_to else None,
            "status":             self.status,
            "revoked_by":         self.revoked_by,
            "revoked_by_name":    self.revoker.full_name if self.revoker else None,
            "revoked_at":         self.revoked_at.isoformat() if self.revoked_at else None,
            "revoke_reason":      self.revoke_reason,
            "issued_at":          self.issued_at.isoformat() if self.issued_at else None,
        }