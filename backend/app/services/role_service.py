# app/services/role_service.py

from app.extensions import db
from app.models.user import Role
from app.utils.constants import Roles


class RoleService:
    """
    Manages Role records themselves (distinct from assigning roles to
    users, which UserService already handles).

    Important: this codebase enforces access control via hardcoded
    role_required(Roles.X, ...) decorators on each route -- not a
    dynamic per-role permission table. Creating a custom role here
    lets it exist and be assigned to users, but it will NOT
    automatically gain access to any endpoint; a developer still has
    to add it to the relevant route decorators in code. The 6 roles
    defined in Roles.ALL are therefore treated as "system" roles and
    protected from renaming/deletion, since routes depend on those
    exact name strings.
    """

    @staticmethod
    def _is_system_role(role_name: str) -> bool:
        return role_name in Roles.ALL

    @staticmethod
    def get_all_roles():
        roles = Role.query.order_by(Role.name.asc()).all()
        return {
            "success": True,
            "message": "Roles retrieved successfully.",
            "data": [
                {
                    **role.to_dict(),
                    "user_count": len(role.users),
                    "is_system_role": RoleService._is_system_role(role.name),
                }
                for role in roles
            ]
        }

    @staticmethod
    def get_role_by_id(role_id: int):
        role = Role.query.get(role_id)
        if not role:
            return {"success": False, "message": f"Role with ID {role_id} not found.", "data": None}

        return {
            "success": True,
            "message": "Role retrieved successfully.",
            "data": {
                **role.to_dict(),
                "user_count":     len(role.users),
                "is_system_role": RoleService._is_system_role(role.name),
                "users":          [{"id": u.id, "full_name": u.full_name, "username": u.username} for u in role.users],
            }
        }

    @staticmethod
    def create_role(data: dict, created_by: int):
        name = (data.get("name") or "").strip()
        if not name:
            return {"success": False, "message": "'name' is required.", "data": None}

        if Role.query.filter(db.func.lower(Role.name) == name.lower()).first():
            return {"success": False, "message": f"A role named '{name}' already exists.", "data": None}

        role = Role(name=name, description=(data.get("description") or "").strip() or None)
        db.session.add(role)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "CREATE_ROLE",
            entity_type = "Role",
            entity_id   = role.id,
            user_id     = created_by,
            new_value   = {"name": role.name}
        )
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"Role '{role.name}' created. Note: it has no route access until added to the relevant code-level permission checks.",
            "data": {**role.to_dict(), "user_count": 0, "is_system_role": False}
        }

    @staticmethod
    def update_role(role_id: int, data: dict, updated_by: int):
        role = Role.query.get(role_id)
        if not role:
            return {"success": False, "message": f"Role with ID {role_id} not found.", "data": None}

        is_system = RoleService._is_system_role(role.name)

        if data.get("name") and data["name"].strip() != role.name:
            if is_system:
                return {
                    "success": False,
                    "message": f"'{role.name}' is a system role and cannot be renamed — routes depend on this exact name.",
                    "data": None
                }
            new_name = data["name"].strip()
            if Role.query.filter(db.func.lower(Role.name) == new_name.lower(), Role.id != role_id).first():
                return {"success": False, "message": f"A role named '{new_name}' already exists.", "data": None}
            role.name = new_name

        if "description" in data:
            role.description = (data["description"] or "").strip() or None

        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "UPDATE_ROLE",
            entity_type = "Role",
            entity_id   = role_id,
            user_id     = updated_by,
            new_value   = {"name": role.name, "description": role.description}
        )
        # ───────────────────────────────────────────────────────

        return {
            "success": True,
            "message": f"Role '{role.name}' updated successfully.",
            "data": {**role.to_dict(), "user_count": len(role.users), "is_system_role": is_system}
        }

    @staticmethod
    def delete_role(role_id: int, deleted_by: int):
        role = Role.query.get(role_id)
        if not role:
            return {"success": False, "message": f"Role with ID {role_id} not found.", "data": None}

        if RoleService._is_system_role(role.name):
            return {
                "success": False,
                "message": f"'{role.name}' is a system role and cannot be deleted.",
                "data": None
            }

        if len(role.users) > 0:
            return {
                "success": False,
                "message": f"Cannot delete '{role.name}' — {len(role.users)} user(s) currently hold this role. Reassign them first.",
                "data": None
            }

        role_name = role.name
        db.session.delete(role)
        db.session.commit()

        # ── Audit log ──────────────────────────────────────────
        from app.services.audit_service import AuditService
        AuditService.log(
            action      = "DELETE_ROLE",
            entity_type = "Role",
            entity_id   = role_id,
            user_id     = deleted_by,
            old_value   = {"name": role_name}
        )
        # ───────────────────────────────────────────────────────

        return {"success": True, "message": f"Role '{role_name}' deleted successfully.", "data": None}