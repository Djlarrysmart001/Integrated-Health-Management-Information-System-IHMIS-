# app/api/v1/immunizations/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.immunization_service import ImmunizationService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

immunizations_bp = Blueprint("immunizations", __name__)

# Nurse/Doctor administer and record; Admin oversees; MHO can view
# (schools often need to verify immunization status at registration).
RECORD_ROLES = (Roles.ADMIN, Roles.NURSE, Roles.DOCTOR)
VIEW_ROLES   = (Roles.ADMIN, Roles.NURSE, Roles.DOCTOR, Roles.MEDICAL_HEALTH_OFFICER)


@immunizations_bp.route("", methods=["POST"])
@role_required(*RECORD_ROLES)
def record_immunization():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    administered_by = int(get_jwt_identity())
    result = ImmunizationService.record_immunization(data, administered_by)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


@immunizations_bp.route("/<int:immunization_id>", methods=["GET"])
@role_required(*VIEW_ROLES)
def get_immunization(immunization_id):
    result = ImmunizationService.get_immunization_by_id(immunization_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@immunizations_bp.route("/patient/<int:patient_id>", methods=["GET"])
@role_required(*VIEW_ROLES)
def get_patient_immunizations(patient_id):
    result = ImmunizationService.get_patient_immunizations(patient_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@immunizations_bp.route("", methods=["GET"])
@role_required(Roles.ADMIN)
def get_all_immunizations():
    page         = request.args.get("page", 1, type=int)
    per_page     = request.args.get("per_page", 20, type=int)
    vaccine_name = request.args.get("vaccine_name")

    result = ImmunizationService.get_all_immunizations(page=page, per_page=per_page, vaccine_name=vaccine_name)
    return success_response(result["message"], data=result["data"])


@immunizations_bp.route("/due-soon", methods=["GET"])
@role_required(*RECORD_ROLES)
def get_due_soon():
    days = request.args.get("days", 30, type=int)
    result = ImmunizationService.get_due_soon(days)
    return success_response(result["message"], data=result["data"])


@immunizations_bp.route("/<int:immunization_id>", methods=["PUT"])
@role_required(Roles.ADMIN)
def update_immunization(immunization_id):
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    result = ImmunizationService.update_immunization(immunization_id, data)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])