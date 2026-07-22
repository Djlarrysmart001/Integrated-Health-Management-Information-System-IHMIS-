# app/api/v1/admissions/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.admission_service import AdmissionService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

admissions_bp = Blueprint("admissions", __name__)

# Doctor admits/discharges; Admin has oversight; Nurse can view for
# ward-monitoring continuity of care.
ADMISSION_ROLES = (Roles.ADMIN, Roles.DOCTOR)
VIEW_ROLES      = (Roles.ADMIN, Roles.DOCTOR, Roles.NURSE)


@admissions_bp.route("", methods=["POST"])
@role_required(*ADMISSION_ROLES)
def admit_patient():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    admitted_by = int(get_jwt_identity())
    result = AdmissionService.admit_patient(data, admitted_by)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


@admissions_bp.route("/<int:admission_id>/discharge", methods=["PATCH"])
@role_required(*ADMISSION_ROLES)
def discharge_patient(admission_id):
    data = request.get_json() or {}
    discharged_by = int(get_jwt_identity())

    result = AdmissionService.discharge_patient(admission_id, discharged_by, data.get("discharge_summary"))
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


@admissions_bp.route("/<int:admission_id>", methods=["GET"])
@role_required(*VIEW_ROLES)
def get_admission(admission_id):
    result = AdmissionService.get_admission_by_id(admission_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@admissions_bp.route("/patient/<int:patient_id>", methods=["GET"])
@role_required(*VIEW_ROLES)
def get_patient_admissions(patient_id):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    result = AdmissionService.get_patient_admissions(patient_id, page=page, per_page=per_page)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@admissions_bp.route("/active", methods=["GET"])
@role_required(*VIEW_ROLES)
def get_active_admissions():
    ward = request.args.get("ward")
    result = AdmissionService.get_active_admissions(ward=ward)
    return success_response(result["message"], data=result["data"])


@admissions_bp.route("", methods=["GET"])
@role_required(Roles.ADMIN)
def get_all_admissions():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    status   = request.args.get("status")
    ward     = request.args.get("ward")

    result = AdmissionService.get_all_admissions(page=page, per_page=per_page, status=status, ward=ward)
    return success_response(result["message"], data=result["data"])