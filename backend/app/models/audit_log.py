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

    # Human-readable label for each action code, used to build the
    # "Description" column the Admin audit log / CSV export shows.
    # Falls back to a title-cased version of the raw action code for
    # anything not listed here, so new action types never render blank.
    _ACTION_LABELS = {
        "LOGIN":                        "Logged in",
        "LOGOUT":                       "Logged out",
        "CREATE_PATIENT":               "Registered patient",
        "CREATE_USER":                  "Created user account",
        "UPDATE_USER":                  "Updated user account",
        "DEACTIVATE_USER":              "Deactivated user account",
        "REACTIVATE_USER":              "Reactivated user account",
        "OPEN_HEALTH_FILE":             "Opened health file",
        "CLOSE_HEALTH_FILE":            "Closed health file",
        "FORWARD_TO_NURSE":             "Forwarded file to Nurse",
        "FORWARD_TO_DOCTOR":            "Forwarded file to Doctor",
        "FORWARD_TO_LAB":               "Forwarded request to Laboratory",
        "FORWARD_TO_PHARMACY":          "Forwarded prescription to Pharmacy",
        "RECORD_VITALS":                "Recorded vital signs",
        "OPEN_CONSULTATION":            "Opened consultation",
        "CLOSE_CONSULTATION":           "Closed consultation",
        "ADD_DIAGNOSIS":                "Added diagnosis",
        "CREATE_PRESCRIPTION":          "Created prescription",
        "CANCEL_PRESCRIPTION":          "Cancelled prescription",
        "DISPENSE_PRESCRIPTION":        "Dispensed prescription",
        "DRUG_INTERACTION_WARNING_SHOWN": "Drug interaction warning shown",
        "RAISE_LAB_REQUEST":            "Raised lab request",
        "RECORD_LAB_RESULTS":           "Recorded lab results",
        "RETURN_FROM_LAB":              "Returned results from Laboratory",
        "SEND_LAB_RESULTS_TO_DOCTOR":   "Sent lab results to Doctor",
        "ADMIT_PATIENT":                "Admitted patient",
        "UPDATE_REFERRAL_STATUS":       "Updated referral status",
        "GENERATE_AI_RECOMMENDATION":   "AI recommendation generated",
        "ACCEPTED_AI_RECOMMENDATION":   "Accepted AI recommendation",
        "DISMISSED_AI_RECOMMENDATION":  "Dismissed AI recommendation",
    }

    def _build_description(self):
        """
        Builds a readable, one-line description of this log entry, e.g.
        'Closed consultation #145' or 'Dispensed prescription #114 (3 item(s))'.
        Uses old_value/new_value where they add useful specifics, without
        assuming every action populated them.
        """
        label = self._ACTION_LABELS.get(
            self.action,
            self.action.replace("_", " ").capitalize()
        )

        target = ""
        if self.entity_type and self.entity_id and self.action not in ("LOGIN", "LOGOUT"):
            target = f" {self.entity_type} #{self.entity_id}"

        extra = ""
        nv = self.new_value or {}
        if self.action == "DISPENSE_PRESCRIPTION" and "items_dispensed" in nv:
            extra = f" ({nv['items_dispensed']} item(s))"
        elif self.action in ("CREATE_USER", "UPDATE_USER") and "username" in nv:
            extra = f" ({nv['username']})"
        elif self.action == "UPDATE_REFERRAL_STATUS" and "status" in nv:
            extra = f" -> {nv['status']}"

        return f"{label}{target}{extra}".strip()

    def to_dict(self):
        return {
            "id":          self.id,
            "user_id":     self.user_id,
            "user": ({
                "id":        self.user.id,
                "username":  self.user.username,
                "full_name": self.user.full_name,
                "roles":     self.user.get_role_names(),
            } if self.user else None),
            "action":      self.action,
            "description": self._build_description(),
            "entity_type": self.entity_type,
            "entity_id":   self.entity_id,
            "ip_address":  self.ip_address,
            "created_at":  self.created_at.isoformat(),
        }