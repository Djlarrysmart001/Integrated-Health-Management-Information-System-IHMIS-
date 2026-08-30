# app/api/v1/consultations/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.consultation_service import ConsultationService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles
from app.models.user import User

consultations_bp = Blueprint("consultations", __name__)

# NOTE: this tuple is only ever used on the four GET (read-only) routes
# below -- every write action (open/update/close consultation, add/delete
# diagnosis) uses Roles.DOCTOR directly, so adding MHO here only grants
# read access, never write.
CLINICAL_ROLES = (Roles.ADMIN, Roles.DOCTOR, Roles.NURSE, Roles.MEDICAL_HEALTH_OFFICER)


# ─────────────────────────────────────────────────────────────
# GET /api/v1/consultations
# ─────────────────────────────────────────────────────────────
@consultations_bp.route("", methods=["GET"])
@role_required(*CLINICAL_ROLES)
def get_all_consultations():
    page       = request.args.get("page", 1, type=int)
    per_page   = request.args.get("per_page", 20, type=int)
    doctor_id  = request.args.get("doctor_id", type=int)
    patient_id = request.args.get("patient_id", type=int)
    status     = request.args.get("status")

    # A Doctor's "Consultations" page only ever shows THEIR OWN
    # consultations. This deliberately overrides -- not just defaults --
    # any client-supplied doctor_id: without this, a Doctor could pass
    # ?doctor_id=<another doctor's id> and read someone else's
    # consultation list directly. Admin and Nurse/MHO keep full control
    # over the doctor_id filter for oversight / continuity-of-care use.
    current_user = User.query.get(int(get_jwt_identity()))
    if current_user and current_user.has_role(Roles.DOCTOR) and not current_user.has_role(Roles.ADMIN):
        doctor_id = current_user.id

    result = ConsultationService.get_all_consultations(
        page=page, per_page=per_page,
        doctor_id=doctor_id, patient_id=patient_id,
        status=status
    )
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/consultations/<id>
# ─────────────────────────────────────────────────────────────
@consultations_bp.route("/<int:consultation_id>", methods=["GET"])
@role_required(*CLINICAL_ROLES)
def get_consultation(consultation_id):
    result = ConsultationService.get_consultation_by_id(consultation_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/consultations/patients/<id>
# ─────────────────────────────────────────────────────────────
@consultations_bp.route("/patients/<int:patient_id>", methods=["GET"])
@role_required(*CLINICAL_ROLES)
def get_patient_consultations(patient_id):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    result   = ConsultationService.get_patient_consultations(
        patient_id, page, per_page
    )
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# POST /api/v1/consultations
# Opens a new consultation
# ─────────────────────────────────────────────────────────────
@consultations_bp.route("", methods=["POST"])
@role_required(Roles.DOCTOR)
def open_consultation():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    doctor_id = int(get_jwt_identity())
    result    = ConsultationService.open_consultation(data, doctor_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


# ─────────────────────────────────────────────────────────────
# PUT /api/v1/consultations/<id>
# Updates consultation notes
# ─────────────────────────────────────────────────────────────
@consultations_bp.route("/<int:consultation_id>", methods=["PUT"])
@role_required(Roles.DOCTOR)
def update_consultation(consultation_id):
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    result = ConsultationService.update_consultation(consultation_id, data)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/consultations/<id>/close
# Closes a consultation
# ─────────────────────────────────────────────────────────────
@consultations_bp.route("/<int:consultation_id>/close", methods=["PATCH"])
@role_required(Roles.DOCTOR)
def close_consultation(consultation_id):
    doctor_id = int(get_jwt_identity())
    result = ConsultationService.close_consultation(consultation_id, doctor_id)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# POST /api/v1/consultations/<id>/diagnoses
# Adds a diagnosis to a consultation
# ─────────────────────────────────────────────────────────────
@consultations_bp.route("/<int:consultation_id>/diagnoses", methods=["POST"])
@role_required(Roles.DOCTOR)
def add_diagnosis(consultation_id):
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    created_by = int(get_jwt_identity())
    result     = ConsultationService.add_diagnosis(
        consultation_id, data, created_by
    )

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


# ─────────────────────────────────────────────────────────────
# GET /api/v1/consultations/<id>/diagnoses
# Returns all diagnoses for a consultation
# ─────────────────────────────────────────────────────────────
@consultations_bp.route("/<int:consultation_id>/diagnoses", methods=["GET"])
@role_required(*CLINICAL_ROLES)
def get_diagnoses(consultation_id):
    result = ConsultationService.get_diagnoses(consultation_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# DELETE /api/v1/consultations/diagnoses/<id>
# Removes a diagnosis
# ─────────────────────────────────────────────────────────────
@consultations_bp.route("/diagnoses/<int:diagnosis_id>", methods=["DELETE"])
@role_required(Roles.DOCTOR)
def delete_diagnosis(diagnosis_id):
    result = ConsultationService.delete_diagnosis(diagnosis_id)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"])