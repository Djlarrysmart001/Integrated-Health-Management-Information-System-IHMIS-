# app/api/v1/laboratory/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.laboratory_service import LaboratoryService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

laboratory_bp = Blueprint("laboratory", __name__)

LAB_ROLES     = (Roles.ADMIN, Roles.DOCTOR, Roles.LAB_TECH)
# MHO added -- only used on read-only (GET) routes below, so this grants
# view access to lab tests/requests/results, never the ability to raise
# a request or record results.
VIEWING_ROLES = (Roles.ADMIN, Roles.DOCTOR, Roles.NURSE, Roles.LAB_TECH, Roles.MEDICAL_HEALTH_OFFICER)


# ─────────────────────────────────────────────────────────────
# LAB TEST CATALOGUE
# ─────────────────────────────────────────────────────────────

@laboratory_bp.route("/tests", methods=["GET"])
@role_required(*VIEWING_ROLES)
def get_all_lab_tests():
    search   = request.args.get("search")
    category = request.args.get("category")
    result   = LaboratoryService.get_all_lab_tests(search, category)
    return success_response(result["message"], data=result["data"])


@laboratory_bp.route("/tests", methods=["POST"])
@role_required(Roles.ADMIN)
def create_lab_test():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    result = LaboratoryService.create_lab_test(data)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


# ─────────────────────────────────────────────────────────────
# LAB REQUESTS
# ─────────────────────────────────────────────────────────────

@laboratory_bp.route("/requests", methods=["GET"])
@role_required(*VIEWING_ROLES)
def get_all_requests():
    page       = request.args.get("page", 1, type=int)
    per_page   = request.args.get("per_page", 20, type=int)
    status     = request.args.get("status")
    patient_id = request.args.get("patient_id", type=int)
    priority   = request.args.get("priority")
    result     = LaboratoryService.get_all_requests(
        page=page, per_page=per_page,
        status=status, patient_id=patient_id, priority=priority
    )
    return success_response(result["message"], data=result["data"])


@laboratory_bp.route("/requests/pending", methods=["GET"])
@role_required(Roles.ADMIN, Roles.LAB_TECH)
def get_pending_requests():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    result   = LaboratoryService.get_pending_requests(page, per_page)
    return success_response(result["message"], data=result["data"])


@laboratory_bp.route("/requests/<int:request_id>", methods=["GET"])
@role_required(*VIEWING_ROLES)
def get_request(request_id):
    result = LaboratoryService.get_request_by_id(request_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@laboratory_bp.route("/requests/patients/<int:patient_id>", methods=["GET"])
@role_required(*VIEWING_ROLES)
def get_patient_lab_history(patient_id):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    result   = LaboratoryService.get_patient_lab_history(patient_id, page, per_page)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@laboratory_bp.route("/requests", methods=["POST"])
@role_required(Roles.DOCTOR)
def raise_lab_request():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    requested_by = int(get_jwt_identity())
    result       = LaboratoryService.raise_lab_request(data, requested_by)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


@laboratory_bp.route("/requests/<int:request_id>/status", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.LAB_TECH)
def update_request_status(request_id):
    data = request.get_json()
    if not data or not data.get("status"):
        return error_response("'status' field is required.", status_code=400)
    result = LaboratoryService.update_request_status(request_id, data["status"])
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# LAB RESULTS
# ─────────────────────────────────────────────────────────────

@laboratory_bp.route("/requests/<int:request_id>/results", methods=["POST"])
@role_required(Roles.ADMIN, Roles.LAB_TECH)
def record_results(request_id):
    data = request.get_json()
    if not data or not data.get("results"):
        return error_response("'results' list is required.", status_code=400)
    performed_by = int(get_jwt_identity())
    result       = LaboratoryService.record_results(
        request_id, data["results"], performed_by
    )
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


@laboratory_bp.route("/requests/<int:request_id>/results", methods=["GET"])
@role_required(*VIEWING_ROLES)
def get_results(request_id):
    result = LaboratoryService.get_request_by_id(request_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])