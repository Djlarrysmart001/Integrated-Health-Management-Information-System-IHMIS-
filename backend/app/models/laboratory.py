# app/models/laboratory.py

from datetime import datetime, timezone
from app.extensions import db

lab_request_items = db.Table(
    "lab_request_items",
    db.Column("id", db.Integer, primary_key=True, autoincrement=True),
    db.Column("lab_request_id", db.Integer, db.ForeignKey("lab_requests.id", ondelete="CASCADE")),
    db.Column("lab_test_id", db.Integer, db.ForeignKey("lab_tests.id")),
)


class LabTest(db.Model):
    __tablename__ = "lab_tests"

    id               = db.Column(db.Integer, primary_key=True)
    name             = db.Column(db.String(120), nullable=False, index=True)
    category         = db.Column(db.String(80), nullable=True)
    normal_range     = db.Column(db.String(120), nullable=True)
    unit             = db.Column(db.String(30), nullable=True)
    turnaround_hours = db.Column(db.Integer, default=24)
    is_active        = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id":               self.id,
            "name":             self.name,
            "category":         self.category,
            "normal_range":     self.normal_range,
            "unit":             self.unit,
            "turnaround_hours": self.turnaround_hours,
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

    requested_by_user = db.relationship("User", foreign_keys=[requested_by], backref="lab_requests_made")
    tests             = db.relationship("LabTest", secondary=lab_request_items, lazy="joined")
    results           = db.relationship("LabResult", backref="lab_request", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":              self.id,
            "consultation_id": self.consultation_id,
            "patient_id":      self.patient_id,
            "requested_by":    self.requested_by,
            "priority":        self.priority,
            "status":          self.status,
            "notes":           self.notes,
            "tests":           [t.to_dict() for t in self.tests],
            "created_at":      self.created_at.isoformat(),
        }


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

    lab_test = db.relationship("LabTest", foreign_keys=[lab_test_id])

    def to_dict(self):
        return {
            "id":              self.id,
            "lab_request_id":  self.lab_request_id,
            "lab_test_id":     self.lab_test_id,
            "test_name":       self.lab_test.name if self.lab_test else None,
            "result_value":    self.result_value,
            "unit":            self.unit,
            "reference_range": self.reference_range,
            "interpretation":  self.interpretation,
            "remarks":         self.remarks,
            "result_date":     self.result_date.isoformat() if self.result_date else None,
        }
