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
# LAB TEST CATEGORIES
# ─────────────────────────────────────────────────────────────

@laboratory_bp.route("/categories", methods=["GET"])
@role_required(*VIEWING_ROLES)
def get_all_categories():
    # Powers the Doctor's Category dropdown (select category, then the
    # Test dropdown filters to that category_id) and the grouped view on
    # the Lab Test Catalogue page.
    result = LaboratoryService.get_all_categories()
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# LAB TEST CATALOGUE
# ─────────────────────────────────────────────────────────────

@laboratory_bp.route("/tests", methods=["GET"])
@role_required(*VIEWING_ROLES)
def get_all_lab_tests():
    search       = request.args.get("search")
    category     = request.args.get("category")
    category_id  = request.args.get("category_id", type=int)
    pending_only = request.args.get("pending_setup", "false").lower() == "true"
    result       = LaboratoryService.get_all_lab_tests(search, category, category_id, pending_only)
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


@laboratory_bp.route("/tests/bulk", methods=["POST"])
@role_required(Roles.ADMIN, Roles.LAB_TECH)
def bulk_create_lab_tests():
    # Lab Tech included here (unlike single-test POST /tests, which stays
    # Admin-only) since this is the intended path for loading a whole
    # category's worth of tests at once, e.g. { "category": "Haematology",
    # "names": ["Full Blood Count (FBC)", "Haemoglobin (Hb)", ...] }.
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    result = LaboratoryService.bulk_create_lab_tests(
        category=data.get("category"),
        names=data.get("names") or [],
        defaults=data.get("defaults") or {},
    )
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


@laboratory_bp.route("/tests/<int:test_id>", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.LAB_TECH)
def update_lab_test(test_id):
    # Lab Tech is included here specifically so whoever is running the
    # bench can finish setting up a test that a Doctor auto-created by
    # typing a name not yet in the catalogue (is_pending_setup=True),
    # without having to go find an Admin first. They can only fill in
    # normal_range/unit/turnaround_hours — creating brand-new catalogue
    # entries from scratch is still Admin-only via POST /tests above.
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    result = LaboratoryService.update_lab_test(test_id, data)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


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
    search     = request.args.get("search")
    result     = LaboratoryService.get_all_requests(
        page=page, per_page=per_page,
        status=status, patient_id=patient_id, priority=priority, search=search
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


@laboratory_bp.route("/requests/<int:request_id>/send-to-doctor", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.LAB_TECH)
def send_results_to_doctor(request_id):
    sent_by = int(get_jwt_identity())
    result  = LaboratoryService.send_results_to_doctor(request_id, sent_by)
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