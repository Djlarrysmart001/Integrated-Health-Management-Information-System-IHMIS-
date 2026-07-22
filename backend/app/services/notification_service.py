# app/services/notification_service.py

from datetime import datetime, timezone
from app.extensions import db
from app.models.notification import Notification
from app.models.user import User


class NotificationService:

    # ──────────────────────────────────────────────────────────
    # Create a Notification
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def create_notification(recipient_id: int, title: str,
                             message: str, notification_type: str = "general",
                             reference_id: int = None,
                             reference_type: str = None):
        """
        Creates a single notification for a user.
        Called internally by other services.

        notification_type options:
            patient_flow, lab_result, low_stock, system, general
        """
        # Verify recipient exists
        user = User.query.get(recipient_id)
        if not user:
            return None

        notification = Notification(
            recipient_id      = recipient_id,
            title             = title,
            message           = message,
            notification_type = notification_type,
            reference_id      = reference_id,
            reference_type    = reference_type,
            is_read           = False,
            created_at        = datetime.now(timezone.utc),
        )
        db.session.add(notification)
        db.session.commit()

        return notification

    # ──────────────────────────────────────────────────────────
    # Broadcast to All Users with a Role
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def broadcast_to_role(role_name: str, title: str,
                           message: str, notification_type: str = "system"):
        """
        Sends the same notification to all users with a specific role.
        Example: notify all Pharmacists about low stock.
        """
        from app.models.user import Role
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            return 0

        count = 0
        for user in role.users:
            if user.is_active:
                NotificationService.create_notification(
                    recipient_id      = user.id,
                    title             = title,
                    message           = message,
                    notification_type = notification_type,
                )
                count += 1

        return count

    # ──────────────────────────────────────────────────────────
    # Get User Notifications
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_user_notifications(user_id: int, page=1,
                                per_page=20, unread_only=False):
        """
        Returns notifications for a specific user.
        Optionally filter to unread only.
        """
        query = Notification.query.filter_by(recipient_id=user_id)

        if unread_only:
            query = query.filter_by(is_read=False)

        query = query.order_by(Notification.created_at.desc())
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Count unread
        unread_count = Notification.query.filter_by(
            recipient_id=user_id, is_read=False
        ).count()

        return {
            "success": True,
            "message": "Notifications retrieved successfully.",
            "data": {
                "notifications": [n.to_dict() for n in pagination.items],
                "total":         pagination.total,
                "unread_count":  unread_count,
                "pages":         pagination.pages,
                "current_page":  page,
                "per_page":      per_page,
                "has_next":      pagination.has_next,
                "has_prev":      pagination.has_prev,
            }
        }

    # ──────────────────────────────────────────────────────────
    # Mark as Read
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def mark_as_read(notification_id: int, user_id: int):
        """Marks a single notification as read."""
        notification = Notification.query.filter_by(
            id=notification_id,
            recipient_id=user_id
        ).first()

        if not notification:
            return {
                "success": False,
                "message": "Notification not found.",
                "data": None
            }

        notification.is_read = True
        db.session.commit()

        return {
            "success": True,
            "message": "Notification marked as read.",
            "data": notification.to_dict()
        }

    # ──────────────────────────────────────────────────────────
    # Mark All as Read
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def mark_all_as_read(user_id: int):
        """Marks all unread notifications for a user as read."""
        updated = Notification.query.filter_by(
            recipient_id=user_id,
            is_read=False
        ).update({"is_read": True})

        db.session.commit()

        return {
            "success": True,
            "message": f"{updated} notification(s) marked as read.",
            "data": {"updated_count": updated}
        }

    # ──────────────────────────────────────────────────────────
    # Delete Notification
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def delete_notification(notification_id: int, user_id: int):
        """Deletes a notification. Users can only delete their own."""
        notification = Notification.query.filter_by(
            id=notification_id,
            recipient_id=user_id
        ).first()

        if not notification:
            return {
                "success": False,
                "message": "Notification not found.",
                "data": None
            }

        db.session.delete(notification)
        db.session.commit()

        return {
            "success": True,
            "message": "Notification deleted.",
            "data": None
        }

    # ──────────────────────────────────────────────────────────
    # Get Unread Count
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def get_unread_count(user_id: int):
        """Returns the number of unread notifications for a user."""
        count = Notification.query.filter_by(
            recipient_id=user_id,
            is_read=False
        ).count()

        return {
            "success": True,
            "message": "Unread count retrieved.",
            "data": {"unread_count": count}
        }

    # ──────────────────────────────────────────────────────────
    # Send System Notification (Admin)
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def send_system_notification(data: dict):
        """
        Admin sends a notification to:
            - A specific user (recipient_id)
            - All users with a role (role_name)
            - All active users (broadcast=true)
        """
        title   = (data.get("title") or "").strip()
        message = (data.get("message") or "").strip()

        if not title or not message:
            return {
                "success": False,
                "message": "'title' and 'message' are required.",
                "data": None
            }

        # Send to specific user
        if data.get("recipient_id"):
            notification = NotificationService.create_notification(
                recipient_id      = data["recipient_id"],
                title             = title,
                message           = message,
                notification_type = "system",
            )
            if not notification:
                return {
                    "success": False,
                    "message": f"User with ID {data['recipient_id']} not found.",
                    "data": None
                }
            return {
                "success": True,
                "message": "Notification sent to user.",
                "data": notification.to_dict()
            }

        # Send to all users with a specific role
        if data.get("role_name"):
            count = NotificationService.broadcast_to_role(
                role_name         = data["role_name"],
                title             = title,
                message           = message,
                notification_type = "system",
            )
            return {
                "success": True,
                "message": f"Notification sent to {count} user(s) with role '{data['role_name']}'.",
                "data": {"recipients": count}
            }

        # Broadcast to ALL active users
        if data.get("broadcast"):
            users = User.query.filter_by(is_active=True).all()
            count = 0
            for user in users:
                NotificationService.create_notification(
                    recipient_id      = user.id,
                    title             = title,
                    message           = message,
                    notification_type = "system",
                )
                count += 1
            return {
                "success": True,
                "message": f"Notification broadcast to {count} user(s).",
                "data": {"recipients": count}
            }

        return {
            "success": False,
            "message": "Provide 'recipient_id', 'role_name', or set 'broadcast' to true.",
            "data": None
        }