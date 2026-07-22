# app/models/notification.py

from datetime import datetime, timezone
from app.extensions import db


class Notification(db.Model):
    """In-app notifications sent to staff users."""
    __tablename__ = "notifications"

    id                = db.Column(db.Integer, primary_key=True)
    recipient_id      = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                                  nullable=False, index=True)
    title             = db.Column(db.String(200), nullable=False)
    message           = db.Column(db.Text, nullable=False)
    notification_type = db.Column(
        db.Enum("patient_flow", "lab_result", "low_stock", "system", "general"),
        default="general",
    )
    reference_id      = db.Column(db.Integer, nullable=True)
    reference_type    = db.Column(db.String(50), nullable=True)
    is_read           = db.Column(db.Boolean, default=False)
    created_at        = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    recipient = db.relationship("User", foreign_keys=[recipient_id], backref="notifications")

    def to_dict(self):
        return {
            "id":                self.id,
            "title":             self.title,
            "message":           self.message,
            "notification_type": self.notification_type,
            "is_read":           self.is_read,
            "created_at":        self.created_at.isoformat(),
        }