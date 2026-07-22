# app/api/v1/health_files/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.health_file_service import HealthFileService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

health_files_bp = Blueprint("health_files", __name__)

# Any clinical role can read a health file / a patient's history —
# needed for continuity of care (Doctor viewing history, Lab viewing
# the request context, etc).
ALL_CLINICAL_ROLES = (Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER, Roles.NURSE,
                       Roles.DOCTOR, Roles.LAB_TECH, Roles.PHARMACIST)


# ─────────────────────────────────────────────────────────────
# POST /api/v1/health-files
# MHO opens a new health file for a patient
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("", methods=["POST"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)
def open_health_file():
    data = request.get_json()
    if not data or not data.get("patient_id"):
        return error_response("'patient_id' is required.", status_code=400)

    opened_by = int(get_jwt_identity())
    result = HealthFileService.open_health_file(data["patient_id"], opened_by)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/forward-to-nurse
# MHO forwards the file to the Nurse queue
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/forward-to-nurse", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)
def forward_to_nurse(health_file_id):
    user_id = int(get_jwt_identity())
    result = HealthFileService.forward_to_nurse(health_file_id, user_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/forward-to-doctor
# Nurse forwards the file to the Doctor queue (after recording vitals)
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/forward-to-doctor", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.NURSE)
def forward_to_doctor(health_file_id):
    user_id = int(get_jwt_identity())
    result = HealthFileService.forward_to_doctor(health_file_id, user_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/forward-to-lab
# Doctor sends the file to the Lab queue
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/forward-to-lab", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.DOCTOR)
def forward_to_lab(health_file_id):
    user_id = int(get_jwt_identity())
    result = HealthFileService.forward_to_lab(health_file_id, user_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/return-from-lab
# Lab sends the file back to the Doctor once results are ready
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/return-from-lab", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.LAB_TECH)
def return_from_lab(health_file_id):
    user_id = int(get_jwt_identity())
    result = HealthFileService.return_from_lab(health_file_id, user_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/forward-to-pharmacy
# Doctor sends the file to the Pharmacy queue
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/forward-to-pharmacy", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.DOCTOR)
def forward_to_pharmacy(health_file_id):
    user_id = int(get_jwt_identity())
    result = HealthFileService.forward_to_pharmacy(health_file_id, user_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/close
# Pharmacist closes the file once medicine is dispensed
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/close", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.PHARMACIST)
def close_health_file(health_file_id):
    user_id = int(get_jwt_identity())
    result = HealthFileService.close_health_file(health_file_id, user_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/mho-close
# MHO manual override — closes a visit from any non-closed state,
# for edge cases like a patient leaving before treatment completes.
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/mho-close", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)
def mho_manual_close(health_file_id):
    data    = request.get_json() or {}
    user_id = int(get_jwt_identity())
    result  = HealthFileService.mho_manual_close(health_file_id, user_id, reason=data.get("reason"))

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/health-files/queue/<status>
# Each role's queue: with_mho, with_nurse, with_doctor, with_lab, with_pharmacy
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/queue/<string:status>", methods=["GET"])
@role_required(*ALL_CLINICAL_ROLES)
def get_queue(status):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    result = HealthFileService.get_queue(status, page=page, per_page=per_page)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/health-files/<id>
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>", methods=["GET"])
@role_required(*ALL_CLINICAL_ROLES)
def get_health_file(health_file_id):
    result = HealthFileService.get_health_file(health_file_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/health-files/patient/<patient_id>
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/patient/<int:patient_id>", methods=["GET"])
@role_required(*ALL_CLINICAL_ROLES)
def get_patient_health_files(patient_id):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    result = HealthFileService.get_patient_health_files(patient_id, page=page, per_page=per_page)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/health-files/<id>/care-trail
# Admin-only: full accountability trail for investigations
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/care-trail", methods=["GET"])
@role_required(Roles.ADMIN)
def get_care_trail(health_file_id):
    result = HealthFileService.get_care_trail(health_file_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])