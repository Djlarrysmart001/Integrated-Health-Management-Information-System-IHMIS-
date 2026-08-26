# app/api/v1/vitals/routes.py

from datetime import datetime, timezone, timedelta
from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.vitals_service import VitalsService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles
from app.utils.dates import resolve_date_range


vitals_bp = Blueprint("vitals", __name__)


@vitals_bp.route("", methods=["GET"])
@role_required(Roles.ADMIN, Roles.DOCTOR, Roles.NURSE, Roles.MEDICAL_HEALTH_OFFICER)
def get_vitals():
    from app.models.user import User

    patient_id      = request.args.get("patient_id", type=int)
    health_file_id  = request.args.get("health_file_id", type=int)
    recorded_by_arg = request.args.get("recorded_by")          # "me" | numeric id | omitted
    range_key       = request.args.get("range")                # "today" | "this_week" | "this_month" | "this_year"
    date_from_arg   = request.args.get("date_from")             # ISO date, used if range not set
    date_to_arg     = request.args.get("date_to")
    search          = request.args.get("search")                # patient name / patient number
    page            = request.args.get("page", 1, type=int)
    per_page        = request.args.get("per_page", 20, type=int)

    current_user_id = int(get_jwt_identity())

    recorded_by = None
    if recorded_by_arg == "me":
        recorded_by = current_user_id
    elif recorded_by_arg:
        recorded_by = int(recorded_by_arg)

    # ── RBAC: browse-everything guard ───────────────────────────
    # A Nurse hitting the general list (no specific patient_id or
    # health_file_id -- i.e. not looking at a record already reached via
    # their own queue) may only ever see vitals THEY recorded, never a
    # system-wide dump. Same principle as the /patients list restriction
    # (patients/routes.py LIST_SEARCH_ROLES) -- role-scoped browsing, not
    # unrestricted access, regardless of what recorded_by the client sends.
    current_user  = User.query.get(current_user_id)
    current_roles = [r.name for r in current_user.roles] if current_user else []
    nurse_only    = Roles.NURSE in current_roles and not any(
        r in current_roles for r in (Roles.ADMIN, Roles.DOCTOR, Roles.MEDICAL_HEALTH_OFFICER)
    )
    if nurse_only and not patient_id and not health_file_id:
        recorded_by = current_user_id

    date_from, date_to = resolve_date_range(range_key, date_from_arg, date_to_arg)

    result = VitalsService.get_vitals(
        patient_id=patient_id, health_file_id=health_file_id,
        recorded_by=recorded_by, date_from=date_from, date_to=date_to,
        search=search, page=page, per_page=per_page,
    )
    return success_response(result["message"], data=result["data"])


@vitals_bp.route("/<int:vitals_id>", methods=["GET"])
@role_required(Roles.ADMIN, Roles.DOCTOR, Roles.NURSE, Roles.MEDICAL_HEALTH_OFFICER)
def get_vitals_by_id(vitals_id):
    result = VitalsService.get_vitals_by_id(vitals_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@vitals_bp.route("/patients/<int:patient_id>", methods=["GET"])
@role_required(Roles.ADMIN, Roles.DOCTOR, Roles.NURSE, Roles.MEDICAL_HEALTH_OFFICER)
def get_patient_vitals_history(patient_id):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    result   = VitalsService.get_patient_vitals_history(patient_id, page, per_page)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@vitals_bp.route("", methods=["POST"])
@role_required(Roles.NURSE, Roles.ADMIN)
def record_vitals():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    recorded_by = int(get_jwt_identity())
    result      = VitalsService.record_vitals(data, recorded_by)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)