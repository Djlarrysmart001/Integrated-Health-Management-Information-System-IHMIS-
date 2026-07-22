# app/api/v1/medical_records/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.medical_record_service import MedicalRecordService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

medical_records_bp = Blueprint("medical_records", __name__)


# ─────────────────────────────────────────────────────────────
# GET /api/v1/medical-records/patients/<id>
# Returns the medical record for a patient
# MHO added -- read-only access to allergies/chronic conditions/
# medications is required for the Patient File view.
# ─────────────────────────────────────────────────────────────
@medical_records_bp.route("/patients/<int:patient_id>", methods=["GET"])
@role_required(Roles.ADMIN, Roles.DOCTOR, Roles.NURSE, Roles.MEDICAL_HEALTH_OFFICER)
def get_medical_record(patient_id):
    result = MedicalRecordService.get_medical_record(patient_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PUT /api/v1/medical-records/patients/<id>
# Updates a patient's medical record
# NOT granted to MHO -- editing clinical background info stays a
# Doctor/Nurse action, matching "MHO must not edit diagnoses,
# prescriptions, or lab results".
# ─────────────────────────────────────────────────────────────
@medical_records_bp.route("/patients/<int:patient_id>", methods=["PUT"])
@role_required(Roles.ADMIN, Roles.DOCTOR, Roles.NURSE)
def update_medical_record(patient_id):
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    updated_by = int(get_jwt_identity())
    result = MedicalRecordService.update_medical_record(patient_id, data, updated_by)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/medical-records/patients/<id>/summary
# Returns full patient summary for doctors
# MHO added -- same reasoning as get_medical_record above.
# ─────────────────────────────────────────────────────────────
@medical_records_bp.route("/patients/<int:patient_id>/summary", methods=["GET"])
@role_required(Roles.ADMIN, Roles.DOCTOR, Roles.NURSE, Roles.MEDICAL_HEALTH_OFFICER)
def get_patient_summary(patient_id):
    result = MedicalRecordService.get_patient_summary(patient_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# POST /api/v1/medical-records/patients/<id>/vitals
# Records new vital signs for a patient
# NOT granted to MHO -- recording vitals is Nurse/Doctor territory,
# outside MHO's role boundary.
# ─────────────────────────────────────────────────────────────
@medical_records_bp.route("/patients/<int:patient_id>/vitals", methods=["POST"])
@role_required(Roles.ADMIN, Roles.NURSE, Roles.DOCTOR)
def record_vital_signs(patient_id):
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    recorded_by = int(get_jwt_identity())
    result = MedicalRecordService.record_vital_signs(patient_id, data, recorded_by)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


# ─────────────────────────────────────────────────────────────
# GET /api/v1/medical-records/patients/<id>/vitals
# Returns vital signs history for a patient
# ─────────────────────────────────────────────────────────────
@medical_records_bp.route("/patients/<int:patient_id>/vitals", methods=["GET"])
@role_required(Roles.ADMIN, Roles.DOCTOR, Roles.NURSE)
def get_vital_signs(patient_id):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    result   = MedicalRecordService.get_vital_signs(patient_id, page, per_page)

    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/medical-records/patients/<id>/vitals/latest
# Returns only the latest vital signs
# ─────────────────────────────────────────────────────────────
@medical_records_bp.route("/patients/<int:patient_id>/vitals/latest", methods=["GET"])
@role_required(Roles.ADMIN, Roles.DOCTOR, Roles.NURSE)
def get_latest_vitals(patient_id):
    result = MedicalRecordService.get_latest_vitals(patient_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])