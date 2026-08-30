# app/api/v1/referrals/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.referral_service import ReferralService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles
from app.models.user import User

referrals_bp = Blueprint("referrals", __name__)

# Read-only viewing access for the wider clinical team, same shape as
# CLINICAL_ROLES in consultations/routes.py.
CLINICAL_ROLES = (Roles.ADMIN, Roles.DOCTOR, Roles.NURSE, Roles.MEDICAL_HEALTH_OFFICER)


# ─────────────────────────────────────────────────────────────
# GET /api/v1/referrals
# ─────────────────────────────────────────────────────────────
@referrals_bp.route("", methods=["GET"])
@role_required(*CLINICAL_ROLES)
def get_all_referrals():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status   = request.args.get("status")
    urgency  = request.args.get("urgency")

    # Same auto-scope pattern as the queue and lab requests: a Doctor
    # only sees referrals THEY issued. Admin, Nurse, MHO keep the full
    # view for oversight/continuity of care.
    doctor_id = None
    current_user = User.query.get(int(get_jwt_identity()))
    if current_user and current_user.has_role(Roles.DOCTOR) and not current_user.has_role(Roles.ADMIN):
        doctor_id = current_user.id

    result = ReferralService.get_all_referrals(
        page=page, per_page=per_page, status=status, urgency=urgency, doctor_id=doctor_id
    )
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/referrals/<id>
# ─────────────────────────────────────────────────────────────
@referrals_bp.route("/<int:referral_id>", methods=["GET"])
@role_required(*CLINICAL_ROLES)
def get_referral(referral_id):
    result = ReferralService.get_referral_by_id(referral_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/referrals/patients/<id>
# ─────────────────────────────────────────────────────────────
@referrals_bp.route("/patients/<int:patient_id>", methods=["GET"])
@role_required(*CLINICAL_ROLES)
def get_patient_referrals(patient_id):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    result   = ReferralService.get_patient_referrals(patient_id, page, per_page)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# POST /api/v1/referrals
# Issues a referral. Requires an existing consultation — ReferralService
# looks the consultation up itself to derive patient_id, so the request
# body only needs consultation_id, not patient_id.
# ─────────────────────────────────────────────────────────────
@referrals_bp.route("", methods=["POST"])
@role_required(Roles.DOCTOR)
def issue_referral():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    referred_by = int(get_jwt_identity())
    result      = ReferralService.issue_referral(data, referred_by)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/referrals/<id>/status
# Moves a referral through issued -> accepted -> completed, or cancels it.
# ReferralService enforces the valid transitions and rejects invalid jumps.
# ─────────────────────────────────────────────────────────────
@referrals_bp.route("/<int:referral_id>/status", methods=["PATCH"])
@role_required(Roles.DOCTOR, Roles.ADMIN)
def update_referral_status(referral_id):
    data = request.get_json()
    if not data or not data.get("status"):
        return error_response("'status' field is required.", status_code=400)

    updated_by = int(get_jwt_identity())
    result = ReferralService.update_referral_status(
        referral_id, data["status"], notes=data.get("notes"), updated_by=updated_by
    )
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])