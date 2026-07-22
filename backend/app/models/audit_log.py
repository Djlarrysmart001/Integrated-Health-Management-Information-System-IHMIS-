# app/models/audit_log.py

from datetime import datetime, timezone
from app.extensions import db


class AuditLog(db.Model):
    """
    Immutable record of every important action in the system.
    Never update or delete audit log entries.

    This table grows forever and will become the largest table in the
    system over the clinic's lifetime -- every stage transition, every
    dispense, every registration writes here. The composite index on
    (entity_type, entity_id) is deliberately the ONLY extra index added
    beyond what's essential: it directly matches the exact lookup
    pattern used by get_entity_history()/get_care_trail() and the
    analytics wait-time computation, which would otherwise force a
    full table scan on the biggest table in the database every time
    someone opens a care trail or the analytics dashboard. Kept
    minimal on purpose -- this table is INSERT-heavy, and every extra
    index adds write overhead on every single action logged, so we
    only index what's actually queried.
    """
    __tablename__ = "audit_logs"
    __table_args__ = (
        db.Index("ix_audit_logs_entity_type_entity_id", "entity_type", "entity_id"),
    )

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action      = db.Column(db.String(100), nullable=False, index=True)   # e.g. CREATE_PATIENT
    entity_type = db.Column(db.String(60), nullable=True)     # e.g. Patient
    entity_id   = db.Column(db.Integer, nullable=True)
    old_value   = db.Column(db.JSON, nullable=True)
    new_value   = db.Column(db.JSON, nullable=True)
    ip_address  = db.Column(db.String(45), nullable=True)
    user_agent  = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user = db.relationship("User", foreign_keys=[user_id], backref="audit_logs")

    def to_dict(self):
        return {
            "id":          self.id,
            "user_id":     self.user_id,
            "action":      self.action,
            "entity_type": self.entity_type,
            "entity_id":   self.entity_id,
            "ip_address":  self.ip_address,
            "created_at":  self.created_at.isoformat(),
        }