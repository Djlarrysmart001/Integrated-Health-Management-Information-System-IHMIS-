# app/api/v1/ai/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.inventory_forecast_service import InventoryForecastService
from app.services.triage_assistant_service import TriageAssistantService
from app.services.clinical_decision_support_service import ClinicalDecisionSupportService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

ai_bp = Blueprint("ai", __name__)

INVENTORY_FORECAST_ROLES = (Roles.ADMIN, Roles.PHARMACIST)
TRIAGE_SCORE_ROLES = (Roles.ADMIN, Roles.NURSE)
TRIAGE_VIEW_ROLES = (Roles.ADMIN, Roles.NURSE, Roles.DOCTOR)
RECOMMENDATION_REVIEW_ROLES = (Roles.ADMIN, Roles.PHARMACIST, Roles.NURSE)

# Doctor/Admin only -- Clinical Decision Support runs during consultation.
CDS_ROLES = (Roles.ADMIN, Roles.DOCTOR)


# ------------------------------------------------------------
# INVENTORY FORECAST
# ------------------------------------------------------------

@ai_bp.route("/inventory-forecast/run", methods=["POST"])
@role_required(*INVENTORY_FORECAST_ROLES)
def run_inventory_forecast():
    triggered_by = int(get_jwt_identity())
    result = InventoryForecastService.run_forecast(triggered_by)
    return success_response(result["message"], data=result["data"])


@ai_bp.route("/inventory-forecast", methods=["GET"])
@role_required(*INVENTORY_FORECAST_ROLES)
def get_inventory_forecast():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    result   = InventoryForecastService.get_active_recommendations(page, per_page)
    return success_response(result["message"], data=result["data"])


# ------------------------------------------------------------
# TRIAGE ASSISTANT
# ------------------------------------------------------------

@ai_bp.route("/triage-score/<int:vitals_id>/run", methods=["POST"])
@role_required(*TRIAGE_SCORE_ROLES)
def run_triage_score(vitals_id):
    triggered_by = int(get_jwt_identity())
    result = TriageAssistantService.run_triage_score(vitals_id, triggered_by)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@ai_bp.route("/triage-score/<int:vitals_id>", methods=["GET"])
@role_required(*TRIAGE_VIEW_ROLES)
def get_triage_score(vitals_id):
    result = TriageAssistantService.get_score_for_vitals(vitals_id)
    return success_response(result["message"], data=result["data"])


# ------------------------------------------------------------
# CLINICAL DECISION SUPPORT (drug interaction warnings)
# ------------------------------------------------------------

@ai_bp.route("/drug-interactions/check", methods=["POST"])
@role_required(*CDS_ROLES)
def check_drug_interactions():
    """Live, stateless check -- called automatically as a Doctor adds
    2+ drugs to a prescription during consultation.
    Body: { "drug_ids": [1,2,3], "consultation_id": 7 }  (consultation_id optional)"""
    data = request.get_json() or {}
    drug_ids = data.get("drug_ids", [])
    if not isinstance(drug_ids, list):
        return error_response("'drug_ids' must be a list.", status_code=400)

    doctor_id = int(get_jwt_identity())
    result = ClinicalDecisionSupportService.check_and_log(
        drug_ids, doctor_id, data.get("consultation_id")
    )
    return success_response(result["message"], data=result["data"])


# ------------------------------------------------------------
# SHARED: accept/dismiss any pending AIRecommendation
# ------------------------------------------------------------

@ai_bp.route("/recommendations/<int:recommendation_id>/review", methods=["POST"])
@role_required(*RECOMMENDATION_REVIEW_ROLES)
def review_recommendation(recommendation_id):
    data = request.get_json()
    if not data or not data.get("decision"):
        return error_response("'decision' is required.", status_code=400)

    reviewed_by = int(get_jwt_identity())
    result = InventoryForecastService.review_recommendation(
        recommendation_id, data["decision"], reviewed_by
    )
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])