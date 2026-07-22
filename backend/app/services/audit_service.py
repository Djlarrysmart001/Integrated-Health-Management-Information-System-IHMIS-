# app/services/audit_service.py

from datetime import datetime, timezone
from flask import request as flask_request
from app.extensions import db
from app.models.audit_log import AuditLog


class AuditService:

    # ──────────────────────────────────────────────────────────
    # Log an Action
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def log(action: str, entity_type: str = None,
            entity_id: int = None, user_id: int = None,
            old_value: dict = None, new_value: dict = None):
        """
        Records an audit log entry.

        Called from service methods after any important action.

        Parameters:
            action      — What happened: CREATE_PATIENT, UPDATE_USER, etc.
            entity_type — What was affected: Patient, User, Prescription, etc.
            entity_id   — The ID of the affected record
            user_id     — Who performed the action (None for system actions)
            old_value   — The state BEFORE the change (for updates)
            new_value   — The state AFTER the change (for creates/updates)

        Examples:
            AuditService.log("LOGIN", user_id=2)
            AuditService.log("CREATE_PATIENT", "Patient", 1, user_id=2,
                             new_value={"name": "John"})
            AuditService.log("UPDATE_USER", "User", 3, user_id=2,
                             old_value={"is_active": True},
                             new_value={"is_active": False})
        """
        try:
            # Get IP address and user agent from the current request
            ip_address = None
            user_agent = None

            try:
                ip_address = flask_request.remote_addr
                user_agent = flask_request.headers.get("User-Agent", "")[:500]
            except RuntimeError:
                # Outside of request context (e.g. during seeding)
                pass

            log_entry = AuditLog(
                user_id     = user_id,
                action      = action,
                entity_type = entity_type,
                entity_id   = entity_id,
                old_value   = old_value,
                new_value   = new_value,
                ip_address  = ip_address,
                user_agent  = user_agent,
                created_at  = datetime.now(timezone.utc),
            )

            db.session.add(log_entry)
            db.session.commit()

            return log_entry

        except Exception as e:
            # Never let audit logging break the main application
            db.session.rollback()
            print(f"Audit log error: {e}")
            return None

    # ──────────────────────────────────────────────────────────
    # Get All Logs
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_all_logs(page=1, per_page=50, user_id=None,
                     action=None, entity_type=None,
                     date_from=None, date_to=None):
        """
        Returns paginated audit logs with optional filters.
        Only Admin can access this.
        """
        from datetime import datetime
        query = AuditLog.query

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        if action:
            query = query.filter(
                AuditLog.action.ilike(f"%{action}%")
            )

        if entity_type:
            query = query.filter(
                AuditLog.entity_type.ilike(f"%{entity_type}%")
            )

        if date_from:
            try:
                start = datetime.strptime(date_from, "%Y-%m-%d")
                query = query.filter(AuditLog.created_at >= start)
            except ValueError:
                pass

        if date_to:
            try:
                end = datetime.strptime(date_to, "%Y-%m-%d")
                query = query.filter(AuditLog.created_at <= end)
            except ValueError:
                pass

        query = query.order_by(AuditLog.created_at.desc())
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return {
            "success": True,
            "message": "Audit logs retrieved successfully.",
            "data": {
                "logs":         [log.to_dict() for log in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
                "per_page":     per_page,
                "has_next":     pagination.has_next,
                "has_prev":     pagination.has_prev,
            }
        }

    # ──────────────────────────────────────────────────────────
    # Get Logs for a Specific User
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_user_activity(user_id: int, page=1, per_page=20):
        """Returns all audit logs for a specific user."""
        from app.models.user import User
        user = User.query.get(user_id)
        if not user:
            return {
                "success": False,
                "message": f"User with ID {user_id} not found.",
                "data": None
            }

        pagination = AuditLog.query.filter_by(
            user_id=user_id
        ).order_by(
            AuditLog.created_at.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        return {
            "success": True,
            "message": f"Activity log for {user.full_name} retrieved.",
            "data": {
                "user_id":      user_id,
                "user_name":    user.full_name,
                "logs":         [log.to_dict() for log in pagination.items],
                "total":        pagination.total,
                "pages":        pagination.pages,
                "current_page": page,
            }
        }

    # ──────────────────────────────────────────────────────────
    # Get Logs for a Specific Entity
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_entity_history(entity_type: str, entity_id: int):
        """
        Returns all audit logs for a specific record.
        Example: all changes made to Patient ID 5.
        """
        logs = AuditLog.query.filter_by(
            entity_type=entity_type,
            entity_id=entity_id
        ).order_by(AuditLog.created_at.desc()).all()

        return {
            "success": True,
            "message": f"History for {entity_type} ID {entity_id} retrieved.",
            "data": {
                "entity_type": entity_type,
                "entity_id":   entity_id,
                "logs":        [log.to_dict() for log in logs],
                "total":       len(logs),
            }
        }

    # ──────────────────────────────────────────────────────────
    # Get Audit Summary Stats
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_audit_stats():
        """Returns summary statistics of system activity."""
        from sqlalchemy import func
        from datetime import date

        today = date.today()

        total_logs    = AuditLog.query.count()
        today_logs    = AuditLog.query.filter(
            func.date(AuditLog.created_at) == today
        ).count()

        # Most active users
        active_users = db.session.query(
            AuditLog.user_id,
            func.count(AuditLog.id).label("action_count")
        ).filter(
            AuditLog.user_id != None
        ).group_by(
            AuditLog.user_id
        ).order_by(
            func.count(AuditLog.id).desc()
        ).limit(5).all()

        # Most common actions
        common_actions = db.session.query(
            AuditLog.action,
            func.count(AuditLog.id).label("count")
        ).group_by(
            AuditLog.action
        ).order_by(
            func.count(AuditLog.id).desc()
        ).limit(10).all()

        return {
            "success": True,
            "message": "Audit statistics retrieved.",
            "data": {
                "total_logs":    total_logs,
                "logs_today":    today_logs,
                "active_users":  [
                    {"user_id": uid, "action_count": count}
                    for uid, count in active_users
                ],
                "common_actions": [
                    {"action": action, "count": count}
                    for action, count in common_actions
                ],
            }
        }