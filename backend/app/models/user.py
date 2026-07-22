# app/models/user.py

from datetime import datetime, timezone
from app.extensions import db


# ─────────────────────────────────────────────
# Association table: users ↔ roles (many-to-many)
# This is a simple join table — no extra columns needed
# ─────────────────────────────────────────────
user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(db.Model):
    """
    Defines the roles in the system.
    Seeded once at startup: Doctor, Nurse, Pharmacist, Lab Technician, Admin.
    """
    __tablename__ = "roles"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Role {self.name}>"

    def to_dict(self):
        return {
            "id":          self.id,
            "name":        self.name,
            "description": self.description,
        }


class User(db.Model):
    """
    System accounts for all healthcare staff.
    Students do NOT have user accounts — they are patients only.
    """
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name    = db.Column(db.String(80), nullable=False)
    last_name     = db.Column(db.String(80), nullable=False)
    phone         = db.Column(db.String(20), nullable=True)
    is_active     = db.Column(db.Boolean, default=True, nullable=False)
    last_login    = db.Column(db.DateTime, nullable=True)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                              onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Many-to-many relationship with Role
    roles = db.relationship("Role", secondary=user_roles, backref="users", lazy="joined")

    # ── helper properties ──────────────────────────────────────
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def has_role(self, role_name: str) -> bool:
        """Check if this user has a specific role."""
        return any(r.name.lower() == role_name.lower() for r in self.roles)

    def get_role_names(self):
        """Return a list of role name strings."""
        return [r.name for r in self.roles]

    def __repr__(self):
        return f"<User {self.username}>"

    def to_dict(self):
        return {
            "id":         self.id,
            "username":   self.username,
            "email":      self.email,
            "first_name": self.first_name,
            "last_name":  self.last_name,
            "full_name":  self.full_name,
            "phone":      self.phone,
            "is_active":  self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "roles":      self.get_role_names(),
            "created_at": self.created_at.isoformat(),
        }