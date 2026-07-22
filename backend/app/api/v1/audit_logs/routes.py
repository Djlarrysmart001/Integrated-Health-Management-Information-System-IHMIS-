# app/api/v1/audit_logs/routes.py

from flask import Blueprint, request
from app.services.audit_service import AuditService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

audit_logs_bp = Blueprint("audit_logs", __name__)


# ─────────────────────────────────────────────────────────────
# GET /api/v1/audit-logs
# Returns all audit logs with filters (Admin only)
# ─────────────────────────────────────────────────────────────
@audit_logs_bp.route("", methods=["GET"])
@role_required(Roles.ADMIN)
def get_all_logs():
    page        = request.args.get("page", 1, type=int)
    per_page    = request.args.get("per_page", 50, type=int)
    user_id     = request.args.get("user_id", type=int)
    action      = request.args.get("action")
    entity_type = request.args.get("entity_type")
    date_from   = request.args.get("date_from")
    date_to     = request.args.get("date_to")

    result = AuditService.get_all_logs(
        page=page, per_page=per_page,
        user_id=user_id, action=action,
        entity_type=entity_type,
        date_from=date_from, date_to=date_to
    )
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/audit-logs/stats
# Returns audit activity statistics (Admin only)
# ─────────────────────────────────────────────────────────────
@audit_logs_bp.route("/stats", methods=["GET"])
@role_required(Roles.ADMIN)
def get_audit_stats():
    result = AuditService.get_audit_stats()
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/audit-logs/users/<id>
# Returns activity log for a specific user (Admin only)
# ─────────────────────────────────────────────────────────────
@audit_logs_bp.route("/users/<int:user_id>", methods=["GET"])
@role_required(Roles.ADMIN)
def get_user_activity(user_id):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    result   = AuditService.get_user_activity(user_id, page, per_page)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/audit-logs/entity/<type>/<id>
# Returns history for a specific record (Admin only)
# ─────────────────────────────────────────────────────────────
@audit_logs_bp.route("/entity/<string:entity_type>/<int:entity_id>",
                     methods=["GET"])
@role_required(Roles.ADMIN)
def get_entity_history(entity_type, entity_id):
    result = AuditService.get_entity_history(entity_type, entity_id)
    return success_response(result["message"], data=result["data"])