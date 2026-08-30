# app/api/v1/medical_certificates/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.medical_certificate_service import MedicalCertificateService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles
from app.models.user import User

medical_certificates_bp = Blueprint("medical_certificates", __name__)

# View-only access for the wider clinical/admin team. Admin gets oversight
# (can see every certificate issued) but never gets a write route below —
# issuing and revoking are Doctor-only, matching "Admin should not be able
# to alter the medical content."
VIEWING_ROLES = (Roles.ADMIN, Roles.DOCTOR, Roles.MEDICAL_HEALTH_OFFICER)


# ─────────────────────────────────────────────────────────────
# GET /api/v1/medical-certificates
# ─────────────────────────────────────────────────────────────
@medical_certificates_bp.route("", methods=["GET"])
@role_required(*VIEWING_ROLES)
def get_all_certificates():
    page             = request.args.get("page", 1, type=int)
    per_page         = request.args.get("per_page", 20, type=int)
    certificate_type = request.args.get("certificate_type")
    status           = request.args.get("status")

    # Same auto-scope pattern as queue/lab/referrals: a Doctor only sees
    # certificates THEY issued. Admin and MHO keep the full view.
    doctor_id = None
    current_user = User.query.get(int(get_jwt_identity()))
    if current_user and current_user.has_role(Roles.DOCTOR) and not current_user.has_role(Roles.ADMIN):
        doctor_id = current_user.id

    result = MedicalCertificateService.get_all_certificates(
        page=page, per_page=per_page, certificate_type=certificate_type, status=status,
        doctor_id=doctor_id
    )
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/medical-certificates/<id>
# ─────────────────────────────────────────────────────────────
@medical_certificates_bp.route("/<int:certificate_id>", methods=["GET"])
@role_required(*VIEWING_ROLES)
def get_certificate(certificate_id):
    result = MedicalCertificateService.get_certificate_by_id(certificate_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/medical-certificates/patients/<id>
# ─────────────────────────────────────────────────────────────
@medical_certificates_bp.route("/patients/<int:patient_id>", methods=["GET"])
@role_required(*VIEWING_ROLES)
def get_patient_certificates(patient_id):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    result   = MedicalCertificateService.get_patient_certificates(patient_id, page, per_page)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/medical-certificates/verify/<certificate_number>
# Deliberately public (no role_required) — this is the lookup a third
# party (e.g. a department checking a submitted sick note) uses to confirm
# a certificate is genuine and still active, without needing an IHMIS login.
# ─────────────────────────────────────────────────────────────
@medical_certificates_bp.route("/verify/<string:certificate_number>", methods=["GET"])
def verify_certificate(certificate_number):
    result = MedicalCertificateService.get_certificate_by_number(certificate_number)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# POST /api/v1/medical-certificates
# Issues a certificate — Doctor only.
# ─────────────────────────────────────────────────────────────
@medical_certificates_bp.route("", methods=["POST"])
@role_required(Roles.DOCTOR)
def issue_certificate():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    issued_by = int(get_jwt_identity())
    result    = MedicalCertificateService.issue_certificate(data, issued_by)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/medical-certificates/<id>/revoke
# Voids a certificate — Doctor only. Never deleted, only flagged.
# ─────────────────────────────────────────────────────────────
@medical_certificates_bp.route("/<int:certificate_id>/revoke", methods=["PATCH"])
@role_required(Roles.DOCTOR)
def revoke_certificate(certificate_id):
    data = request.get_json()
    if not data or not (data.get("reason") or "").strip():
        return error_response("'reason' is required to revoke a certificate.", status_code=400)

    revoked_by = int(get_jwt_identity())
    result     = MedicalCertificateService.revoke_certificate(certificate_id, revoked_by, data["reason"])

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])