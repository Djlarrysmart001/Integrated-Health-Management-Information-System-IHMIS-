# app/models/health_file.py

from datetime import datetime, timezone
from app.extensions import db


class HealthFile(db.Model):
    """
    The top-level record for a single clinic visit, opened by the
    Medical Health Officer (MHO) the moment a patient walks in.

    Status doubles as the "queue" each role's dashboard filters on:
        with_mho      -> just opened, not yet forwarded
        with_nurse    -> MHO forwarded it, waiting on vitals/triage
        with_doctor   -> Nurse forwarded it, waiting on consultation
        with_lab      -> Doctor requested a test, waiting on Lab
        with_pharmacy -> Doctor prescribed, waiting on dispensing
        closed        -> Pharmacist dispensed, visit complete

    Note: "with_lab" always returns to "with_doctor" once the Lab
    uploads a result — the Doctor makes the final call either way.
    """
    __tablename__ = "health_files"

    STATUSES = ("with_mho", "with_nurse", "with_doctor", "with_lab",
                "with_pharmacy", "closed")

    id           = db.Column(db.Integer, primary_key=True)
    patient_id   = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    opened_by    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status       = db.Column(db.Enum(*STATUSES), default="with_mho", nullable=False, index=True)

    # Daily queue position, assigned by the MHO at check-in. Resets each
    # day (computed at assignment time, not stored as a running total) so
    # the queue display can show "Patient #4 of 12 today" style numbering.
    queue_number = db.Column(db.Integer, nullable=True)

    # Stamped the moment this file leaves "with_mho" (i.e. when
    # forward_to_nurse() fires). Used to compute the "Average Check-in
    # Time" KPI: AVG(called_at - opened_at) across today's files.
    called_at    = db.Column(db.DateTime, nullable=True)

    opened_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at    = db.Column(db.DateTime, nullable=True)
    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))

    # ── relationships ──────────────────────────────────────────
    opener       = db.relationship("User", foreign_keys=[opened_by])
    vital_signs  = db.relationship("VitalSigns", backref="health_file", uselist=False)
    consultation = db.relationship("Consultation", backref="health_file", uselist=False)

    def __repr__(self):
        return f"<HealthFile {self.id} — {self.status}>"

    def to_dict(self):
        return {
            "id":               self.id,
            "patient_id":       self.patient_id,
            "patient_name":     self.patient.full_name if self.patient else None,
            "opened_by":        self.opened_by,
            "opened_by_name":   self.opener.full_name if self.opener else None,
            "status":           self.status,
            "queue_number":     self.queue_number,
            "opened_at":        self.opened_at.isoformat() if self.opened_at else None,
            "called_at":        self.called_at.isoformat() if self.called_at else None,
            "closed_at":        self.closed_at.isoformat() if self.closed_at else None,
            "has_vitals":       self.vital_signs is not None,
            "has_consultation": self.consultation is not None,
            "created_at":       self.created_at.isoformat(),
        }