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
        admitted      -> Doctor admitted for inpatient monitoring, Nurse's care
        closed        -> Pharmacist dispensed (or Doctor discharged), visit complete

    Note: "with_lab" always returns to "with_doctor" once the Lab
    uploads a result — the Doctor makes the final call either way.

    Similarly, "admitted" always returns to "with_doctor" once the
    Nurse forwards the file back after inpatient monitoring — an
    admitted patient is never discharged directly by the Nurse; the
    Doctor makes that call too. See HealthFileService.admit_patient /
    forward_to_doctor / discharge_patient.
    """
    __tablename__ = "health_files"

    STATUSES = ("with_mho", "with_nurse", "with_doctor", "with_lab",
                "with_pharmacy", "admitted", "closed")

    id           = db.Column(db.Integer, primary_key=True)
    patient_id   = db.Column(db.Integer, db.ForeignKey("patients.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    opened_by    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status       = db.Column(db.Enum(*STATUSES), default="with_mho", nullable=False, index=True)

    # Which Doctor this file is currently assigned to. Set the moment the
    # Nurse forwards to a specific on-duty doctor (see
    # HealthFileService.forward_to_doctor) — NOT set by anything before
    # that point. Stays set across the with_lab / admitted loop-backs, so
    # a file always returns to the same doctor who first picked it up,
    # even if it briefly left "with_doctor" along the way.
    assigned_doctor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    # Which Nurse this file is currently assigned to. Set the moment the
    # MHO forwards to a specific on-duty nurse (see
    # HealthFileService.forward_to_nurse) — mirrors assigned_doctor_id
    # exactly, one stage earlier in the flow. Only meaningful while the
    # file sits "with_nurse"; unlike assigned_doctor_id it isn't looped
    # back to later (the admitted/with_lab loop-backs are a Doctor-side
    # concern), but it's left set afterwards purely as a historical
    # record of who triaged this visit.
    assigned_nurse_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

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
    opener          = db.relationship("User", foreign_keys=[opened_by])
    assigned_doctor = db.relationship("User", foreign_keys=[assigned_doctor_id])
    assigned_nurse  = db.relationship("User", foreign_keys=[assigned_nurse_id])
    vital_signs     = db.relationship("VitalSigns", backref="health_file", uselist=False)
    consultation    = db.relationship("Consultation", backref="health_file", uselist=False)

    def __repr__(self):
        return f"<HealthFile {self.id} — {self.status}>"

    def to_dict(self):
        return {
            "id":                  self.id,
            "patient_id":          self.patient_id,
            "patient_name":        self.patient.full_name if self.patient else None,
            "opened_by":           self.opened_by,
            "opened_by_name":      self.opener.full_name if self.opener else None,
            "status":              self.status,
            "assigned_doctor_id":  self.assigned_doctor_id,
            "assigned_doctor_name": self.assigned_doctor.full_name if self.assigned_doctor else None,
            "assigned_nurse_id":   self.assigned_nurse_id,
            "assigned_nurse_name": self.assigned_nurse.full_name if self.assigned_nurse else None,
            "queue_number":        self.queue_number,
            "opened_at":           self.opened_at.isoformat() if self.opened_at else None,
            "called_at":           self.called_at.isoformat() if self.called_at else None,
            "closed_at":           self.closed_at.isoformat() if self.closed_at else None,
            "has_vitals":          self.vital_signs is not None,
            "has_consultation":    self.consultation is not None,
            "created_at":          self.created_at.isoformat(),
        }