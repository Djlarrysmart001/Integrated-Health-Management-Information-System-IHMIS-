# app/api/v1/reports/routes.py

from flask import Blueprint, request
from app.services.report_service import ReportService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

reports_bp = Blueprint("reports", __name__)

REPORT_ROLES = (Roles.ADMIN, Roles.DOCTOR)


# ─────────────────────────────────────────────────────────────
# GET /api/v1/reports/summary
# ─────────────────────────────────────────────────────────────
@reports_bp.route("/summary", methods=["GET"])
@role_required(*REPORT_ROLES)
def summary_report():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")
    result    = ReportService.summary_report(date_from, date_to)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/reports/patient-registrations
# ─────────────────────────────────────────────────────────────
@reports_bp.route("/patient-registrations", methods=["GET"])
@role_required(*REPORT_ROLES)
def patient_registration_report():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")
    result    = ReportService.patient_registration_report(date_from, date_to)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/reports/patient-visits
# ─────────────────────────────────────────────────────────────
@reports_bp.route("/patient-visits", methods=["GET"])
@role_required(*REPORT_ROLES)
def patient_visits_report():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")
    result    = ReportService.patient_visits_report(date_from, date_to)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/reports/disease-burden
# ─────────────────────────────────────────────────────────────
@reports_bp.route("/disease-burden", methods=["GET"])
@role_required(*REPORT_ROLES)
def disease_burden_report():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")
    top_n     = request.args.get("top_n", 10, type=int)
    result    = ReportService.disease_burden_report(date_from, date_to, top_n)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/reports/drug-consumption
# ─────────────────────────────────────────────────────────────
@reports_bp.route("/drug-consumption", methods=["GET"])
@role_required(*REPORT_ROLES)
def drug_consumption_report():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")
    result    = ReportService.drug_consumption_report(date_from, date_to)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/reports/lab-turnaround
# ─────────────────────────────────────────────────────────────
@reports_bp.route("/lab-turnaround", methods=["GET"])
@role_required(*REPORT_ROLES)
def lab_turnaround_report():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")
    result    = ReportService.lab_turnaround_report(date_from, date_to)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/reports/inventory-status
# ─────────────────────────────────────────────────────────────
@reports_bp.route("/inventory-status", methods=["GET"])
@role_required(Roles.ADMIN, Roles.PHARMACIST)
def inventory_status_report():
    result = ReportService.inventory_status_report()
    return success_response(result["message"], data=result["data"])