# app/models/laboratory.py

from datetime import datetime, timezone
from app.extensions import db

lab_request_items = db.Table(
    "lab_request_items",
    db.Column("id", db.Integer, primary_key=True, autoincrement=True),
    db.Column("lab_request_id", db.Integer, db.ForeignKey("lab_requests.id", ondelete="CASCADE")),
    db.Column("lab_test_id", db.Integer, db.ForeignKey("lab_tests.id")),
)


class LabTestCategory(db.Model):
    """
    Groups tests the way the lab actually organises its bench work
    (Haematology, Microbiology, Renal Function Tests, etc.). This is what
    powers the category-first, then-test dropdown on the Doctor's lab
    request screen, and the grouped view on the Lab Test Catalogue page.
    """
    __tablename__ = "lab_test_categories"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255), nullable=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    tests = db.relationship("LabTest", backref="category", lazy="dynamic")

    def to_dict(self, include_test_count=False):
        data = {
            "id":          self.id,
            "name":        self.name,
            "description": self.description,
        }
        if include_test_count:
            data["test_count"] = self.tests.filter_by(is_active=True).count()
        return data


class LabTest(db.Model):
    __tablename__ = "lab_tests"

    id               = db.Column(db.Integer, primary_key=True)
    name             = db.Column(db.String(120), nullable=False, index=True)
    category_id      = db.Column(db.Integer, db.ForeignKey("lab_test_categories.id"), nullable=True, index=True)
    normal_range     = db.Column(db.String(120), nullable=True)
    unit             = db.Column(db.String(30), nullable=True)
    turnaround_hours = db.Column(db.Integer, default=24)
    is_active        = db.Column(db.Boolean, default=True)

    # Set True only when a Doctor requests a test by typed name instead of
    # picking one from the catalogue — created immediately (active) so the
    # request can still go through, but flagged so Lab/Admin knows it still
    # needs a real category/normal_range/unit/turnaround time filled in.
    # Mirrors Drug.is_pending_setup exactly.
    is_pending_setup = db.Column(db.Boolean, default=False, nullable=False)

    # `category` relationship object comes from LabTestCategory.tests
    # backref above (category_id is the raw FK column).

    def to_dict(self):
        return {
            "id":                self.id,
            "name":              self.name,
            "category_id":       self.category_id,
            "category":          self.category.name if self.category else None,
            "normal_range":      self.normal_range,
            "unit":              self.unit,
            "turnaround_hours":  self.turnaround_hours,
            "is_active":         self.is_active,
            "is_pending_setup":  self.is_pending_setup,
        }


class LabRequest(db.Model):
    __tablename__ = "lab_requests"

    id              = db.Column(db.Integer, primary_key=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id      = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    requested_by    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    priority        = db.Column(db.Enum("routine", "urgent", "stat"), default="routine")
    status          = db.Column(db.Enum("pending", "sample_collected", "in_progress", "completed", "cancelled"), default="pending", nullable=False)
    notes           = db.Column(db.Text, nullable=True)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Completing all results on a request already moves the health file
    # back to the Doctor in the background (HealthFileService.return_from_lab),
    # but that was invisible to the Lab Tech and never notified the Doctor.
    # These two columns back an explicit "Send Results to Doctor" action so
    # Lab can see, at a glance, what's completed-but-not-yet-sent.
    sent_to_doctor      = db.Column(db.Boolean, default=False, nullable=False)
    sent_to_doctor_at   = db.Column(db.DateTime, nullable=True)
    sent_to_doctor_by   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # NOTE: this relationship was missing before. Without it, to_dict() had
    # no way to surface the patient's name, and the frontend table/queue
    # always rendered "—" for the patient column no matter what the UI
    # tried to read (r.patient?.full_name, r.patient_name, etc.).
    patient = db.relationship("Patient", foreign_keys=[patient_id])

    requested_by_user = db.relationship("User", foreign_keys=[requested_by], backref="lab_requests_made")
    sent_to_doctor_user = db.relationship("User", foreign_keys=[sent_to_doctor_by])
    tests             = db.relationship("LabTest", secondary=lab_request_items, lazy="joined")
    results           = db.relationship("LabResult", backref="lab_request", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self, include_results=False):
        data = {
            "id":                self.id,
            "consultation_id":   self.consultation_id,
            "patient_id":        self.patient_id,
            "patient": {
                "id":         self.patient.id,
                "full_name":  self.patient.full_name,
                "patient_id": getattr(self.patient, "patient_id", None),
            } if self.patient else None,
            "requested_by":      self.requested_by,
            "requested_by_name": self.requested_by_user.full_name if self.requested_by_user else None,
            "priority":          self.priority,
            "status":            self.status,
            "notes":             self.notes,
            "tests":             [t.to_dict() for t in self.tests],
            "has_pending_setup_test": any(t.is_pending_setup for t in self.tests),
            "sent_to_doctor":    self.sent_to_doctor,
            "sent_to_doctor_at": self.sent_to_doctor_at.isoformat() if self.sent_to_doctor_at else None,
            "sent_to_doctor_by_name": self.sent_to_doctor_user.full_name if self.sent_to_doctor_user else None,
            "created_at":        self.created_at.isoformat(),
            "updated_at":        self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_results:
            data["results"] = [r.to_dict() for r in self.results]
        return data


class LabResult(db.Model):
    __tablename__ = "lab_results"

    id              = db.Column(db.Integer, primary_key=True)
    lab_request_id  = db.Column(db.Integer, db.ForeignKey("lab_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    lab_test_id     = db.Column(db.Integer, db.ForeignKey("lab_tests.id"), nullable=False)
    patient_id      = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    result_value    = db.Column(db.Text, nullable=True)
    unit            = db.Column(db.String(30), nullable=True)
    reference_range = db.Column(db.String(120), nullable=True)
    interpretation  = db.Column(db.Enum("normal", "low", "high", "critical"), nullable=True)
    remarks         = db.Column(db.Text, nullable=True)
    performed_by    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    verified_by     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    result_date     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    lab_test          = db.relationship("LabTest", foreign_keys=[lab_test_id])
    performed_by_user = db.relationship("User", foreign_keys=[performed_by])
    verified_by_user  = db.relationship("User", foreign_keys=[verified_by])

    def to_dict(self):
        return {
            "id":                self.id,
            "lab_request_id":    self.lab_request_id,
            "lab_test_id":       self.lab_test_id,
            "test_name":         self.lab_test.name if self.lab_test else None,
            "result_value":      self.result_value,
            "unit":              self.unit,
            "reference_range":   self.reference_range,
            "interpretation":    self.interpretation,
            "remarks":           self.remarks,
            "performed_by":      self.performed_by,
            "performed_by_name": self.performed_by_user.full_name if self.performed_by_user else None,
            "verified_by_name":  self.verified_by_user.full_name if self.verified_by_user else None,
            "result_date":       self.result_date.isoformat() if self.result_date else None,
        }