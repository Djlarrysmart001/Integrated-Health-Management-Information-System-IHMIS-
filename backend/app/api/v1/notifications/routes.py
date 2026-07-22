# app/api/v1/notifications/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.notification_service import NotificationService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

notifications_bp = Blueprint("notifications", __name__)

ALL_ROLES = (Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER, Roles.DOCTOR,
             Roles.NURSE, Roles.PHARMACIST, Roles.LAB_TECH)


# ─────────────────────────────────────────────────────────────
# GET /api/v1/notifications
# Returns notifications for the logged-in user
# ─────────────────────────────────────────────────────────────
@notifications_bp.route("", methods=["GET"])
@role_required(*ALL_ROLES)
def get_my_notifications():
    user_id     = int(get_jwt_identity())
    page        = request.args.get("page", 1, type=int)
    per_page    = request.args.get("per_page", 20, type=int)
    unread_only = request.args.get("unread_only", "false").lower() == "true"

    result = NotificationService.get_user_notifications(
        user_id, page, per_page, unread_only
    )
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/notifications/unread-count
# Returns unread count for the logged-in user
# ─────────────────────────────────────────────────────────────
@notifications_bp.route("/unread-count", methods=["GET"])
@role_required(*ALL_ROLES)
def get_unread_count():
    user_id = int(get_jwt_identity())
    result  = NotificationService.get_unread_count(user_id)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/notifications/<id>/read
# Mark a notification as read
# ─────────────────────────────────────────────────────────────
@notifications_bp.route("/<int:notification_id>/read", methods=["PATCH"])
@role_required(*ALL_ROLES)
def mark_as_read(notification_id):
    user_id = int(get_jwt_identity())
    result  = NotificationService.mark_as_read(notification_id, user_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/notifications/read-all
# Mark all notifications as read
# ─────────────────────────────────────────────────────────────
@notifications_bp.route("/read-all", methods=["PATCH"])
@role_required(*ALL_ROLES)
def mark_all_as_read():
    user_id = int(get_jwt_identity())
    result  = NotificationService.mark_all_as_read(user_id)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# DELETE /api/v1/notifications/<id>
# Delete a notification
# ─────────────────────────────────────────────────────────────
@notifications_bp.route("/<int:notification_id>", methods=["DELETE"])
@role_required(*ALL_ROLES)
def delete_notification(notification_id):
    user_id = int(get_jwt_identity())
    result  = NotificationService.delete_notification(notification_id, user_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"])


# ─────────────────────────────────────────────────────────────
# POST /api/v1/notifications/send
# Admin sends notification to user, role, or all
# ─────────────────────────────────────────────────────────────
@notifications_bp.route("/send", methods=["POST"])
@role_required(Roles.ADMIN)
def send_notification():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    result = NotificationService.send_system_notification(data)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)