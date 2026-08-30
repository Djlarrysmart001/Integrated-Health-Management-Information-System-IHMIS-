# app/services/auth_service.py

from datetime import datetime, timezone
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity
from app.extensions import db, bcrypt
from app.models.user import User, Role
from app.utils.constants import Roles


class AuthService:

    @staticmethod
    def login(username_or_email: str, password: str) -> dict:
        user = User.query.filter(
            (User.username == username_or_email) |
            (User.email == username_or_email)
        ).first()

        if not user:
            return {"success": False, "message": "Invalid username or password.", "data": None}
        if not user.is_active:
            return {"success": False, "message": "Account deactivated. Contact administrator.", "data": None}
        if not bcrypt.check_password_hash(user.password_hash, password):
            return {"success": False, "message": "Invalid username or password.", "data": None}

        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

        # Audit log — record the login event
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "LOGIN",
            entity_type = "User",
            entity_id   = user.id,
            user_id     = user.id,
            new_value   = {"username": user.username, "roles": user.get_role_names()}
        )

        access_token  = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))

        return {
            "success": True,
            "message": "Login successful.",
            "data": {
                "access_token":  access_token,
                "refresh_token": refresh_token,
                "token_type":    "Bearer",
                "user":          user.to_dict()
            }
        }

    @staticmethod
    def refresh_token() -> dict:
        user_id = get_jwt_identity()
        user    = User.query.get(user_id)
        if not user or not user.is_active:
            return {"success": False, "message": "User not found or deactivated.", "data": None}
        new_access_token = create_access_token(identity=str(user.id))
        return {"success": True, "message": "Token refreshed.", "data": {"access_token": new_access_token, "token_type": "Bearer"}}

    @staticmethod
    def get_current_user(user_id: int) -> dict:
        user = User.query.get(user_id)
        if not user:
            return {"success": False, "message": "User not found.", "data": None}
        return {"success": True, "message": "User profile retrieved.", "data": user.to_dict()}

    @staticmethod
    def update_current_user(user_id: int, data: dict) -> dict:
        """
        Self-service profile update — intentionally narrower than
        UserService.update_user (which is Admin-only and also handles
        username/role changes). This only ever touches the fields below,
        on the caller's own record, so a non-admin user can never use it
        to change their own username or grant themselves a role.
        """
        import json
        user = User.query.get(user_id)
        if not user:
            return {"success": False, "message": "User not found.", "data": None}

        if data.get("email") and data["email"] != user.email:
            if User.query.filter_by(email=data["email"]).first():
                return {"success": False, "message": f"Email '{data['email']}' is already registered.", "data": None}
            user.email = data["email"].strip().lower()

        if data.get("first_name"):
            user.first_name = data["first_name"].strip()
        if data.get("last_name"):
            user.last_name = data["last_name"].strip()
        if "phone" in data:
            user.phone = data["phone"].strip() or None

        if "notification_preferences" in data and isinstance(data["notification_preferences"], dict):
            merged = user.get_notification_preferences()
            for key in User.DEFAULT_NOTIFICATION_PREFERENCES:
                if key in data["notification_preferences"]:
                    merged[key] = bool(data["notification_preferences"][key])
            user.notification_preferences = json.dumps(merged)

        db.session.commit()

        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "UPDATE_OWN_PROFILE",
            entity_type = "User",
            entity_id   = user.id,
            user_id     = user.id,
            new_value   = {"first_name": user.first_name, "last_name": user.last_name, "email": user.email}
        )

        return {"success": True, "message": "Profile updated successfully.", "data": user.to_dict()}

    @staticmethod
    def set_duty_status(user_id: int, is_on_duty: bool) -> dict:
        """
        Lets a Doctor or Nurse toggle their own on-duty status. Deliberately
        only touches this one field on the caller's own record -- same
        narrow-self-service pattern as update_current_user. This is what
        drives the Nurse's "which doctor is available" picker on Forward to
        Doctor (see UserService.get_on_duty_doctors), and the MHO's "which
        nurse is available" picker on Forward to Nurse (see
        UserService.get_on_duty_nurses).
        """
        user = User.query.get(user_id)
        if not user:
            return {"success": False, "message": "User not found.", "data": None}
        if not (user.has_role(Roles.DOCTOR) or user.has_role(Roles.NURSE)):
            return {"success": False, "message": "Only Doctors and Nurses have an on-duty status.", "data": None}

        user.is_on_duty = bool(is_on_duty)
        db.session.commit()

        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "SET_DUTY_STATUS",
            entity_type = "User",
            entity_id   = user.id,
            user_id     = user.id,
            new_value   = {"is_on_duty": user.is_on_duty}
        )

        status_word = "on" if user.is_on_duty else "off"
        return {"success": True, "message": f"You are now {status_word} duty.", "data": user.to_dict()}

    @staticmethod
    def change_password(user_id: int, current_password: str, new_password: str) -> dict:
        user = User.query.get(user_id)
        if not user:
            return {"success": False, "message": "User not found.", "data": None}
        if not bcrypt.check_password_hash(user.password_hash, current_password):
            return {"success": False, "message": "Current password is incorrect.", "data": None}
        if len(new_password) < 8:
            return {"success": False, "message": "New password must be at least 8 characters.", "data": None}
        user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
        db.session.commit()
        return {"success": True, "message": "Password changed successfully.", "data": None}

    @staticmethod
    def seed_roles() -> None:
        for role_name in Roles.ALL:
            if not Role.query.filter_by(name=role_name).first():
                db.session.add(Role(name=role_name, description=f"{role_name} role"))
        db.session.commit()
        print("✅ Roles seeded successfully.")

    @staticmethod
    def seed_admin(username, email, password, first_name, last_name) -> None:
        if User.query.filter_by(email=email).first():
            print(f"⚠️  User with email {email} already exists. Skipping.")
            return
        admin_role = Role.query.filter_by(name=Roles.ADMIN).first()
        if not admin_role:
            print("❌ Admin role not found. Run seed-roles first.")
            return
        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        admin = User(
            username      = username,
            email         = email,
            password_hash = password_hash,
            first_name    = first_name,
            last_name     = last_name,
            is_active     = True,
        )
        admin.roles.append(admin_role)
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Admin user '{username}' created successfully.")