# app/api/v1/prescriptions/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.prescription_service import PrescriptionService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles


prescriptions_bp = Blueprint("prescriptions", __name__)


# MHO added -- read-only viewing of past prescriptions for the Patient
# File page. Not granted on /pending (Pharmacist's working queue), or
# on write/dispense/cancel actions below.
@prescriptions_bp.route("", methods=["GET"])
@role_required(Roles.ADMIN, Roles.DOCTOR, Roles.PHARMACIST, Roles.MEDICAL_HEALTH_OFFICER)
def get_all_prescriptions():
    page            = request.args.get("page", 1, type=int)
    per_page        = request.args.get("per_page", 20, type=int)
    patient_id      = request.args.get("patient_id", type=int)
    status          = request.args.get("status")
    consultation_id = request.args.get("consultation_id", type=int)
    result = PrescriptionService.get_all_prescriptions(
        page=page, per_page=per_page,
        patient_id=patient_id, status=status,
        consultation_id=consultation_id
    )
    return success_response(result["message"], data=result["data"])


@prescriptions_bp.route("/pending", methods=["GET"])
@role_required(Roles.ADMIN, Roles.PHARMACIST)
def get_pending_prescriptions():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    result   = PrescriptionService.get_pending_prescriptions(page, per_page)
    return success_response(result["message"], data=result["data"])


@prescriptions_bp.route("/<int:prescription_id>", methods=["GET"])
@role_required(Roles.ADMIN, Roles.DOCTOR, Roles.PHARMACIST, Roles.MEDICAL_HEALTH_OFFICER)
def get_prescription(prescription_id):
    result = PrescriptionService.get_prescription_by_id(prescription_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@prescriptions_bp.route("/patients/<int:patient_id>", methods=["GET"])
@role_required(Roles.ADMIN, Roles.DOCTOR, Roles.PHARMACIST, Roles.MEDICAL_HEALTH_OFFICER)
def get_patient_prescriptions(patient_id):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    result   = PrescriptionService.get_patient_prescriptions(patient_id, page, per_page)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@prescriptions_bp.route("", methods=["POST"])
@role_required(Roles.DOCTOR)
def write_prescription():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    prescribed_by = int(get_jwt_identity())
    result        = PrescriptionService.write_prescription(data, prescribed_by)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


@prescriptions_bp.route("/<int:prescription_id>/dispense", methods=["PATCH"])
@role_required(Roles.PHARMACIST)
def dispense_prescription(prescription_id):
    dispensed_by = int(get_jwt_identity())
    result       = PrescriptionService.dispense_prescription(prescription_id, dispensed_by)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


@prescriptions_bp.route("/<int:prescription_id>/cancel", methods=["PATCH"])
@role_required(Roles.DOCTOR, Roles.ADMIN)
def cancel_prescription(prescription_id):
    result = PrescriptionService.cancel_prescription(prescription_id)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])