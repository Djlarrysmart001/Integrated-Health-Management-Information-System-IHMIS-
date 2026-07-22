# app/api/v1/staff_attendance/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.staff_attendance_service import StaffAttendanceService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

staff_attendance_bp = Blueprint("staff_attendance", __name__)

# Any authenticated staff member can clock themselves in/out.
# Recording/marking on someone else's behalf, or managing/correcting
# records, is Nurse (record) + Admin (manage) per the RBAC matrix.
ALL_STAFF_ROLES = (Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER, Roles.NURSE,
                    Roles.DOCTOR, Roles.LAB_TECH, Roles.PHARMACIST)
MANAGE_ROLES    = (Roles.ADMIN, Roles.NURSE)


@staff_attendance_bp.route("/clock-in", methods=["POST"])
@role_required(*ALL_STAFF_ROLES)
def clock_in():
    from app.models.user import User

    data           = request.get_json() or {}
    requester_id   = int(get_jwt_identity())
    target_user_id = data.get("user_id", requester_id)

    if target_user_id != requester_id:
        requester = User.query.get(requester_id)
        requester_roles = [r.name for r in requester.roles] if requester else []
        if not any(role in requester_roles for role in MANAGE_ROLES):
            return error_response("You can only clock yourself in.", status_code=403)
        recorded_by = requester_id
    else:
        recorded_by = None

    result = StaffAttendanceService.clock_in(target_user_id, recorded_by)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


@staff_attendance_bp.route("/clock-out", methods=["POST"])
@role_required(*ALL_STAFF_ROLES)
def clock_out():
    from app.models.user import User

    data           = request.get_json() or {}
    requester_id   = int(get_jwt_identity())
    target_user_id = data.get("user_id", requester_id)

    if target_user_id != requester_id:
        requester = User.query.get(requester_id)
        requester_roles = [r.name for r in requester.roles] if requester else []
        if not any(role in requester_roles for role in MANAGE_ROLES):
            return error_response("You can only clock yourself out.", status_code=403)
        recorded_by = requester_id
    else:
        recorded_by = None

    result = StaffAttendanceService.clock_out(target_user_id, recorded_by)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


@staff_attendance_bp.route("/mark", methods=["POST"])
@role_required(*MANAGE_ROLES)
def mark_status():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    for field in ["user_id", "date", "status"]:
        if not data.get(field):
            return error_response(f"'{field}' is required.", status_code=400)

    recorded_by = int(get_jwt_identity())
    result = StaffAttendanceService.mark_status(
        data["user_id"], data["date"], data["status"], recorded_by, data.get("notes")
    )
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


@staff_attendance_bp.route("/user/<int:user_id>", methods=["GET"])
@role_required(*ALL_STAFF_ROLES)
def get_staff_attendance(user_id):
    from app.models.user import User

    requester_id = int(get_jwt_identity())
    if user_id != requester_id:
        requester = User.query.get(requester_id)
        requester_roles = [r.name for r in requester.roles] if requester else []
        if not any(role in requester_roles for role in MANAGE_ROLES):
            return error_response("You can only view your own attendance history.", status_code=403)

    page      = request.args.get("page", 1, type=int)
    per_page  = request.args.get("per_page", 30, type=int)
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")

    result = StaffAttendanceService.get_staff_attendance(user_id, date_from, date_to, page=page, per_page=per_page)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@staff_attendance_bp.route("/roster", methods=["GET"])
@role_required(*MANAGE_ROLES)
def get_daily_roster():
    target_date = request.args.get("date")
    result = StaffAttendanceService.get_daily_roster(target_date)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


@staff_attendance_bp.route("", methods=["GET"])
@role_required(Roles.ADMIN)
def get_all_attendance():
    page      = request.args.get("page", 1, type=int)
    per_page  = request.args.get("per_page", 30, type=int)
    status    = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")

    result = StaffAttendanceService.get_all_attendance(
        page=page, per_page=per_page, status=status, date_from=date_from, date_to=date_to
    )
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


@staff_attendance_bp.route("/<int:attendance_id>", methods=["PUT"])
@role_required(Roles.ADMIN)
def update_attendance(attendance_id):
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    result = StaffAttendanceService.update_attendance(attendance_id, data)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])