# app/models/staff_attendance.py

from datetime import datetime, timezone, date as date_cls
from app.extensions import db


class StaffAttendance(db.Model):
    """
    One row per staff member per day. Supports self-service clock-in/
    clock-out, and manual recording/correction by a Nurse or Admin
    (matches the "Record Staff Attendance" permission on the Nurse role) —
    covers cases like marking someone absent/on-leave with no clock-in,
    or backfilling a missed entry.
    """
    __tablename__ = "staff_attendance"

    STATUSES = ("present", "absent", "late", "on_leave", "half_day")

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    date         = db.Column(db.Date, nullable=False, default=lambda: datetime.now(timezone.utc).date(), index=True)
    clock_in     = db.Column(db.DateTime, nullable=True)
    clock_out    = db.Column(db.DateTime, nullable=True)
    status       = db.Column(db.Enum(*STATUSES), default="present", nullable=False)
    recorded_by  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # null = self clock-in
    notes        = db.Column(db.Text, nullable=True)
    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uq_staff_attendance_user_date"),
    )

    # ── relationships ──────────────────────────────────────────
    user     = db.relationship("User", foreign_keys=[user_id])
    recorder = db.relationship("User", foreign_keys=[recorded_by])

    @property
    def hours_worked(self):
        if self.clock_in and self.clock_out:
            delta = self.clock_out - self.clock_in
            return round(delta.total_seconds() / 3600, 2)
        return None

    def to_dict(self):
        return {
            "id":            self.id,
            "user_id":       self.user_id,
            "user_name":     self.user.full_name if self.user else None,
            "date":          self.date.isoformat() if self.date else None,
            "clock_in":      self.clock_in.isoformat() if self.clock_in else None,
            "clock_out":     self.clock_out.isoformat() if self.clock_out else None,
            "hours_worked":  self.hours_worked,
            "status":        self.status,
            "recorded_by":   self.recorded_by,
            "recorded_by_name": self.recorder.full_name if self.recorder else "Self",
            "notes":         self.notes,
            "created_at":    self.created_at.isoformat(),
        }