# app/services/user_service.py

from app.extensions import db, bcrypt
from app.models.user import User, Role
from app.utils.constants import Roles


class UserService:

    @staticmethod
    def get_on_duty_doctors():
        """
        Doctors currently on duty and active -- this is the exact list the
        Nurse's "Forward to Doctor" picker shows. Deliberately narrower
        than get_all_users: no pagination, no search, just the small live
        list a Nurse needs at the moment of forwarding a file.
        """
        doctors = (
            User.query
            .join(User.roles)
            .filter(Role.name == Roles.DOCTOR, User.is_on_duty == True, User.is_active == True)
            .order_by(User.first_name.asc())
            .all()
        )
        return {
            "success": True,
            "message": f"{len(doctors)} doctor(s) currently on duty.",
            "data": {"doctors": [d.to_dict() for d in doctors]}
        }

    @staticmethod
    def get_on_duty_nurses():
        """
        Nurses currently on duty and active -- this is the exact list the
        MHO's "Forward to Nurse" picker shows. Mirrors get_on_duty_doctors
        exactly, one stage earlier in the flow.
        """
        nurses = (
            User.query
            .join(User.roles)
            .filter(Role.name == Roles.NURSE, User.is_on_duty == True, User.is_active == True)
            .order_by(User.first_name.asc())
            .all()
        )
        return {
            "success": True,
            "message": f"{len(nurses)} nurse(s) currently on duty.",
            "data": {"nurses": [n.to_dict() for n in nurses]}
        }

    @staticmethod
    def get_all_users(page=1, per_page=20, search=None, role=None, is_active=None):
        query = User.query

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (User.username.ilike(search_term)) |
                (User.email.ilike(search_term)) |
                (User.first_name.ilike(search_term)) |
                (User.last_name.ilike(search_term))
            )
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        if role:
            query = query.join(User.roles).filter(Role.name == role)

        query = query.order_by(User.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": "Users retrieved successfully.",
            "data": {
                "users":        [u.to_dict() for u in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
                "per_page":     per_page,
                "has_next":     pagination.has_next,
                "has_prev":     pagination.has_prev,
            }
        }

    @staticmethod
    def get_user_by_id(user_id: int):
        user = User.query.get(user_id)
        if not user:
            return {"success": False, "message": f"User with ID {user_id} not found.", "data": None}
        return {"success": True, "message": "User retrieved successfully.", "data": user.to_dict()}

    @staticmethod
    def create_user(data: dict, performed_by: int = None):
        required = ["username", "email", "password", "first_name", "last_name", "roles"]
        for field in required:
            if not data.get(field):
                return {"success": False, "message": f"'{field}' is required.", "data": None}

        if User.query.filter_by(username=data["username"]).first():
            return {"success": False, "message": f"Username '{data['username']}' is already taken.", "data": None}

        if User.query.filter_by(email=data["email"]).first():
            return {"success": False, "message": f"Email '{data['email']}' is already registered.", "data": None}

        if len(data["password"]) < 8:
            return {"success": False, "message": "Password must be at least 8 characters.", "data": None}

        role_objects = []
        for role_name in data["roles"]:
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                return {
                    "success": False,
                    "message": f"Role '{role_name}' does not exist. Valid roles: {', '.join(Roles.ALL)}",
                    "data": None
                }
            role_objects.append(role)

        password_hash = bcrypt.generate_password_hash(data["password"]).decode("utf-8")

        user = User(
            username      = data["username"].strip(),
            email         = data["email"].strip().lower(),
            password_hash = password_hash,
            first_name    = data["first_name"].strip(),
            last_name     = data["last_name"].strip(),
            phone         = (data.get("phone") or "").strip() or None,
            is_active     = True,
        )
        for role in role_objects:
            user.roles.append(role)

        db.session.add(user)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "CREATE_USER",
            entity_type = "User",
            entity_id   = user.id,
            user_id     = performed_by,
            new_value   = {"username": user.username, "roles": user.get_role_names()}
        )
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"User '{user.username}' created successfully.",
            "data": user.to_dict()
        }

    @staticmethod
    def update_user(user_id: int, data: dict, performed_by: int = None):
        user = User.query.get(user_id)
        if not user:
            return {"success": False, "message": f"User with ID {user_id} not found.", "data": None}

        if data.get("username") and data["username"] != user.username:
            if User.query.filter_by(username=data["username"]).first():
                return {"success": False, "message": f"Username '{data['username']}' is already taken.", "data": None}
            user.username = data["username"].strip()

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

        if data.get("roles"):
            role_objects = []
            for role_name in data["roles"]:
                role = Role.query.filter_by(name=role_name).first()
                if not role:
                    return {"success": False, "message": f"Role '{role_name}' does not exist.", "data": None}
                role_objects.append(role)
            user.roles = role_objects

        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "UPDATE_USER",
            entity_type = "User",
            entity_id   = user.id,
            user_id     = performed_by,
            new_value   = {"username": user.username, "roles": user.get_role_names()}
        )
        # ───────────────────────────────────────────────────────

        return {"success": True, "message": "User updated successfully.", "data": user.to_dict()}

    @staticmethod
    def deactivate_user(user_id: int, requesting_user_id: int):
        user = User.query.get(user_id)
        if not user:
            return {"success": False, "message": f"User with ID {user_id} not found.", "data": None}
        if user_id == requesting_user_id:
            return {"success": False, "message": "You cannot deactivate your own account.", "data": None}

        user.is_active = False
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "DEACTIVATE_USER",
            entity_type = "User",
            entity_id   = user_id,
            user_id     = requesting_user_id,
            new_value   = {"is_active": False}
        )
        # ───────────────────────────────────────────────────────

        return {"success": True, "message": f"User '{user.username}' has been deactivated.", "data": user.to_dict()}

    @staticmethod
    def reactivate_user(user_id: int):
        user = User.query.get(user_id)
        if not user:
            return {"success": False, "message": f"User with ID {user_id} not found.", "data": None}

        user.is_active = True
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "REACTIVATE_USER",
            entity_type = "User",
            entity_id   = user_id,
            new_value   = {"is_active": True}
        )
        # ───────────────────────────────────────────────────────

        return {"success": True, "message": f"User '{user.username}' has been reactivated.", "data": user.to_dict()}

    @staticmethod
    def assign_roles(user_id: int, role_names: list):
        user = User.query.get(user_id)
        if not user:
            return {"success": False, "message": f"User with ID {user_id} not found.", "data": None}

        role_objects = []
        for role_name in role_names:
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                return {
                    "success": False,
                    "message": f"Role '{role_name}' does not exist. Valid: {', '.join(Roles.ALL)}",
                    "data": None
                }
            role_objects.append(role)

        user.roles = role_objects
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "ASSIGN_ROLES",
            entity_type = "User",
            entity_id   = user_id,
            new_value   = {"roles": user.get_role_names()}
        )
        # ───────────────────────────────────────────────────────

        return {"success": True, "message": f"Roles updated for '{user.username}'.", "data": user.to_dict()}

    @staticmethod
    def get_all_roles():
        roles = Role.query.all()
        return {"success": True, "message": "Roles retrieved successfully.", "data": [r.to_dict() for r in roles]}