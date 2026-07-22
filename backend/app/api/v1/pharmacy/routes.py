# app/api/v1/pharmacy/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.pharmacy_service import PharmacyService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

pharmacy_bp = Blueprint("pharmacy", __name__)

PHARMACY_ROLES = (Roles.ADMIN, Roles.PHARMACIST)
VIEWING_ROLES  = (Roles.ADMIN, Roles.DOCTOR, Roles.PHARMACIST, Roles.NURSE)


# ─────────────────────────────────────────────────────────────
# DRUG CATALOGUE
# ─────────────────────────────────────────────────────────────

@pharmacy_bp.route("/drugs", methods=["GET"])
@role_required(*VIEWING_ROLES)
def get_all_drugs():
    page      = request.args.get("page", 1, type=int)
    per_page  = request.args.get("per_page", 20, type=int)
    search    = request.args.get("search")
    category  = request.args.get("category")
    is_active = request.args.get("is_active")

    if is_active is not None:
        is_active = is_active.lower() == "true"

    result = PharmacyService.get_all_drugs(
        page=page, per_page=per_page,
        search=search, category=category, is_active=is_active
    )
    return success_response(result["message"], data=result["data"])


@pharmacy_bp.route("/drugs/<int:drug_id>", methods=["GET"])
@role_required(*VIEWING_ROLES)
def get_drug(drug_id):
    result = PharmacyService.get_drug_by_id(drug_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@pharmacy_bp.route("/drugs", methods=["POST"])
@role_required(*PHARMACY_ROLES)
def create_drug():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    result = PharmacyService.create_drug(data)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(
        result["message"], data=result["data"], status_code=201
    )


@pharmacy_bp.route("/drugs/<int:drug_id>", methods=["PUT"])
@role_required(*PHARMACY_ROLES)
def update_drug(drug_id):
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    result = PharmacyService.update_drug(drug_id, data)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# INVENTORY
# ─────────────────────────────────────────────────────────────

@pharmacy_bp.route("/inventory", methods=["GET"])
@role_required(*PHARMACY_ROLES)
def get_inventory():
    page           = request.args.get("page", 1, type=int)
    per_page       = request.args.get("per_page", 20, type=int)
    low_stock_only = request.args.get("low_stock_only", "false").lower() == "true"
    expired_only   = request.args.get("expired_only", "false").lower() == "true"

    result = PharmacyService.get_inventory(
        page=page, per_page=per_page,
        low_stock_only=low_stock_only,
        expired_only=expired_only
    )
    return success_response(result["message"], data=result["data"])


@pharmacy_bp.route("/inventory/low-stock", methods=["GET"])
@role_required(*PHARMACY_ROLES)
def get_low_stock():
    result = PharmacyService.get_low_stock_drugs()
    return success_response(result["message"], data=result["data"])


@pharmacy_bp.route("/inventory/expiring", methods=["GET"])
@role_required(*PHARMACY_ROLES)
def get_expiring_soon():
    days   = request.args.get("days", 90, type=int)
    result = PharmacyService.get_expiring_soon(days)
    return success_response(result["message"], data=result["data"])


@pharmacy_bp.route("/drugs/<int:drug_id>/receive", methods=["POST"])
@role_required(*PHARMACY_ROLES)
def receive_stock(drug_id):
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    received_by = int(get_jwt_identity())
    result      = PharmacyService.receive_stock(drug_id, data, received_by)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(
        result["message"], data=result["data"], status_code=201
    )


@pharmacy_bp.route("/drugs/<int:drug_id>/adjust", methods=["POST"])
@role_required(*PHARMACY_ROLES)
def adjust_stock(drug_id):
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    if not data.get("batch_id"):
        return error_response("'batch_id' is required.", status_code=400)
    if "quantity_delta" not in data:
        return error_response("'quantity_delta' is required.", status_code=400)

    performed_by = int(get_jwt_identity())
    result = PharmacyService.adjust_stock(
        drug_id, data["batch_id"], int(data["quantity_delta"]),
        data.get("reason", ""), performed_by
    )
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# DRUG TRANSACTION LEDGER
# ─────────────────────────────────────────────────────────────

@pharmacy_bp.route("/transactions", methods=["GET"])
@role_required(*PHARMACY_ROLES)
def get_drug_transactions():
    page              = request.args.get("page", 1, type=int)
    per_page          = request.args.get("per_page", 20, type=int)
    drug_id           = request.args.get("drug_id", type=int)
    transaction_type  = request.args.get("transaction_type")

    result = PharmacyService.get_drug_transactions(
        drug_id=drug_id, transaction_type=transaction_type,
        page=page, per_page=per_page
    )
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# DISPENSATION HISTORY
# ─────────────────────────────────────────────────────────────

@pharmacy_bp.route("/dispensation-history", methods=["GET"])
@role_required(*PHARMACY_ROLES)
def get_dispensation_history():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    drug_id  = request.args.get("drug_id", type=int)
    result   = PharmacyService.get_dispensation_history(page, per_page, drug_id)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PHARMACY DASHBOARD STATS
# ─────────────────────────────────────────────────────────────

@pharmacy_bp.route("/stats", methods=["GET"])
@role_required(*PHARMACY_ROLES)
def get_pharmacy_stats():
    result = PharmacyService.get_pharmacy_stats()
    return success_response(result["message"], data=result["data"])