# app/models/system_settings.py

from datetime import datetime, timezone
from app.extensions import db


class SystemSettings(db.Model):
    """
    Key-value store for system-wide configuration.
    e.g. institution_name, working_hours_start, low_stock_email_enabled
    """
    __tablename__ = "system_settings"

    id          = db.Column(db.Integer, primary_key=True)
    key         = db.Column(db.String(80), unique=True, nullable=False, index=True)
    value       = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    updated_by  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "key":         self.key,
            "value":       self.value,
            "description": self.description,
            "updated_at":  self.updated_at.isoformat() if self.updated_at else None,
        }