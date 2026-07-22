# app/models/patient_document.py

from datetime import datetime, timezone
from app.extensions import db


class PatientDocument(db.Model):
    """
    Generic document storage for a patient's file -- student/staff ID
    card scans, referral letters, consent forms, and other supporting
    paperwork. Separate from the passport photo (which lives directly
    on Patient.photo_data) since a patient can have zero or many of
    these, unlike the single passport photo.

    Stored as a BLOB in MySQL (Aiven), matching the passport photo
    storage decision -- same trade-off applies: simplest to build,
    but keep an eye on Aiven's free-tier storage cap as usage grows.
    """
    __tablename__ = "patient_documents"

    DOC_TYPES = ("id_card", "referral_letter", "consent_form", "medical_document", "other")

    id           = db.Column(db.Integer, primary_key=True)
    patient_id   = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    doc_type     = db.Column(db.Enum(*DOC_TYPES), nullable=False, default="other")
    file_name    = db.Column(db.String(255), nullable=False)
    file_mime    = db.Column(db.String(50), nullable=True)
    file_data    = db.Column(db.LargeBinary(length=(2**24)-1), nullable=False)  # MEDIUMBLOB range
    notes        = db.Column(db.String(255), nullable=True)
    uploaded_by  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    uploaded_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    uploader = db.relationship("User", foreign_keys=[uploaded_by])

    def __repr__(self):
        return f"<PatientDocument {self.id} — {self.doc_type} for patient {self.patient_id}>"

    def to_dict(self):
        # File bytes deliberately excluded -- served separately via a
        # dedicated download route, same pattern as the passport photo.
        return {
            "id":            self.id,
            "patient_id":    self.patient_id,
            "doc_type":      self.doc_type,
            "file_name":     self.file_name,
            "file_mime":     self.file_mime,
            "notes":         self.notes,
            "uploaded_by":   self.uploaded_by,
            "uploaded_by_name": self.uploader.full_name if self.uploader else None,
            "uploaded_at":   self.uploaded_at.isoformat() if self.uploaded_at else None,
        }