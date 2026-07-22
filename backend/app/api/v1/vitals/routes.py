# app/api/v1/vitals/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.vitals_service import VitalsService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles


vitals_bp = Blueprint("vitals", __name__)


@vitals_bp.route("", methods=["GET"])
@role_required(Roles.ADMIN, Roles.DOCTOR, Roles.NURSE, Roles.MEDICAL_HEALTH_OFFICER)
def get_vitals():
    patient_id     = request.args.get("patient_id", type=int)
    health_file_id = request.args.get("health_file_id", type=int)
    page            = request.args.get("page", 1, type=int)
    per_page        = request.args.get("per_page", 20, type=int)
    result = VitalsService.get_vitals(
        patient_id=patient_id, health_file_id=health_file_id,
        page=page, per_page=per_page
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