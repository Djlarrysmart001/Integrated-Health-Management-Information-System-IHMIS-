# app/api/v1/analytics/routes.py

from flask import Blueprint, request
from app.services.analytics_service import AnalyticsService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

analytics_bp = Blueprint("analytics", __name__)

# "View Analytics" is an Admin-only permission per the RBAC matrix.
@analytics_bp.route("/overview", methods=["GET"])
@role_required(Roles.ADMIN)
def get_overview():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")
    result = AnalyticsService.get_overview(date_from, date_to)
    return success_response(result["message"], data=result["data"])


@analytics_bp.route("/wait-times", methods=["GET"])
@role_required(Roles.ADMIN)
def get_wait_times():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")
    result = AnalyticsService.get_average_wait_times(date_from, date_to)
    return success_response(result["message"], data=result["data"])


@analytics_bp.route("/visit-outcomes", methods=["GET"])
@role_required(Roles.ADMIN)
def get_visit_outcomes():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")
    result = AnalyticsService.get_visit_outcomes(date_from, date_to)
    return success_response(result["message"], data=result["data"])


@analytics_bp.route("/demographics", methods=["GET"])
@role_required(Roles.ADMIN)
def get_demographics():
    result = AnalyticsService.get_demographics()
    return success_response(result["message"], data=result["data"])


@analytics_bp.route("/top-diagnoses", methods=["GET"])
@role_required(Roles.ADMIN)
def get_top_diagnoses():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")
    limit     = request.args.get("limit", 5, type=int)
    result = AnalyticsService.get_top_diagnoses(date_from, date_to, limit=limit)
    return success_response(result["message"], data=result["data"])


@analytics_bp.route("/visit-trend", methods=["GET"])
@role_required(Roles.ADMIN)
def get_visit_trend():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")
    result = AnalyticsService.get_visit_trend(date_from, date_to)
    return success_response(result["message"], data=result["data"])