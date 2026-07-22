# app/api/v1/patients/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.patient_service import PatientService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

patients_bp = Blueprint("patients", __name__)

# All clinical roles can read patient records (needed for continuity of care)
ALL_ROLES = (Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER, Roles.DOCTOR,
             Roles.NURSE, Roles.PHARMACIST, Roles.LAB_TECH)


# ─────────────────────────────────────────────────────────────
# GET /api/v1/patients
# ─────────────────────────────────────────────────────────────
@patients_bp.route("", methods=["GET"])
@role_required(*ALL_ROLES)
def get_all_patients():
    page         = request.args.get("page", 1, type=int)
    per_page     = request.args.get("per_page", 20, type=int)
    search       = request.args.get("search", None)
    patient_type = request.args.get("type", None)
    is_active    = request.args.get("is_active", None)

    if is_active is not None:
        is_active = is_active.lower() == "true"

    result = PatientService.get_all_patients(
        page=page, per_page=per_page,
        search=search, patient_type=patient_type,
        is_active=is_active
    )
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/patients/statistics
# ─────────────────────────────────────────────────────────────
@patients_bp.route("/statistics", methods=["GET"])
@role_required(Roles.ADMIN, Roles.DOCTOR)
def get_statistics():
    result = PatientService.get_statistics()
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/patients/search?id_number=MAT123
# ─────────────────────────────────────────────────────────────
@patients_bp.route("/search", methods=["GET"])
@role_required(*ALL_ROLES)
def search_by_id():
    id_number = request.args.get("id_number", "").strip()
    if not id_number:
        return error_response("'id_number' query parameter is required.", status_code=400)

    result = PatientService.search_by_id_number(id_number)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/patients/check-duplicate?first_name=&last_name=&date_of_birth=
# Non-blocking soft check used by the MHO registration form -- fires on
# blur once first name, last name, and DOB are all filled in.
# ─────────────────────────────────────────────────────────────
@patients_bp.route("/check-duplicate", methods=["GET"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)
def check_duplicate():
    first_name    = request.args.get("first_name", "").strip()
    last_name     = request.args.get("last_name", "").strip()
    date_of_birth = request.args.get("date_of_birth", "").strip()

    result = PatientService.check_potential_duplicate(first_name, last_name, date_of_birth)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/patients/<id>
# ─────────────────────────────────────────────────────────────
@patients_bp.route("/<int:patient_id>", methods=["GET"])
@role_required(*ALL_ROLES)
def get_patient(patient_id):
    result = PatientService.get_patient_by_id(patient_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# POST /api/v1/patients/students
# ─────────────────────────────────────────────────────────────
@patients_bp.route("/students", methods=["POST"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)
def register_student():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    registered_by = int(get_jwt_identity())
    result = PatientService.register_student(data, registered_by)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


# ─────────────────────────────────────────────────────────────
# POST /api/v1/patients/staff
# ─────────────────────────────────────────────────────────────
@patients_bp.route("/staff", methods=["POST"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)
def register_staff():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    registered_by = int(get_jwt_identity())
    result = PatientService.register_staff(data, registered_by)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


# ─────────────────────────────────────────────────────────────
# POST /api/v1/patients/others
# ─────────────────────────────────────────────────────────────
@patients_bp.route("/others", methods=["POST"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)
def register_other():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    registered_by = int(get_jwt_identity())
    result = PatientService.register_other(data, registered_by)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


# ─────────────────────────────────────────────────────────────
# POST /api/v1/patients/<id>/photo
# Uploads/replaces a patient's passport photo (base64-encoded)
# ─────────────────────────────────────────────────────────────
@patients_bp.route("/<int:patient_id>/photo", methods=["POST"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)
def upload_photo(patient_id):
    data = request.get_json()
    if not data or not data.get("photo_data"):
        return error_response("'photo_data' (base64) is required.", status_code=400)

    result = PatientService.upload_photo(patient_id, data["photo_data"], data.get("photo_mime"))
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/patients/<id>/photo
# Serves the raw photo bytes (not JSON) -- used as an <img src="...">
# target directly, e.g. in the Patient File header.
# ─────────────────────────────────────────────────────────────
@patients_bp.route("/<int:patient_id>/photo", methods=["GET"])
@role_required(*ALL_ROLES)
def get_photo(patient_id):
    from flask import Response

    result = PatientService.get_photo(patient_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)

    return Response(result["data"]["photo_data"], mimetype=result["data"]["photo_mime"])


# ─────────────────────────────────────────────────────────────
# PUT /api/v1/patients/<id>
# ─────────────────────────────────────────────────────────────
@patients_bp.route("/<int:patient_id>", methods=["PUT"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)
def update_patient(patient_id):
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    result = PatientService.update_patient(patient_id, data)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/patients/<id>/deactivate
# ─────────────────────────────────────────────────────────────
@patients_bp.route("/<int:patient_id>/deactivate", methods=["PATCH"])
@role_required(Roles.ADMIN)
def deactivate_patient(patient_id):
    result = PatientService.deactivate_patient(patient_id)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])