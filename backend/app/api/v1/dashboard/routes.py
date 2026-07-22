# app/api/v1/dashboard/routes.py

from flask import Blueprint
from flask_jwt_extended import get_jwt_identity
from app.services.dashboard_service import DashboardService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles
from app.models.user import User

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("", methods=["GET"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER, Roles.NURSE,
               Roles.DOCTOR, Roles.PHARMACIST, Roles.LAB_TECH)
def get_my_dashboard():
    user_id = int(get_jwt_identity())
    user    = User.query.get(user_id)

    if not user:
        return error_response("User not found.", status_code=404)

    role_names = user.get_role_names()

    if Roles.ADMIN in role_names:
        result = DashboardService.get_admin_dashboard()
    elif Roles.MEDICAL_HEALTH_OFFICER in role_names:
        result = DashboardService.get_mho_dashboard()
    elif Roles.DOCTOR in role_names:
        result = DashboardService.get_doctor_dashboard(user_id)
    elif Roles.NURSE in role_names:
        result = DashboardService.get_nurse_dashboard()
    elif Roles.PHARMACIST in role_names:
        result = DashboardService.get_pharmacist_dashboard()
    elif Roles.LAB_TECH in role_names:
        result = DashboardService.get_lab_dashboard()
    else:
        return error_response("No dashboard available for your role.", status_code=403)

    return success_response(result["message"], data=result["data"])


@dashboard_bp.route("/admin", methods=["GET"])
@role_required(Roles.ADMIN)
def admin_dashboard():
    result = DashboardService.get_admin_dashboard()
    return success_response(result["message"], data=result["data"])


@dashboard_bp.route("/mho", methods=["GET"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)
def mho_dashboard():
    result = DashboardService.get_mho_dashboard()
    return success_response(result["message"], data=result["data"])


@dashboard_bp.route("/doctor", methods=["GET"])
@role_required(Roles.ADMIN, Roles.DOCTOR)
def doctor_dashboard():
    user_id = int(get_jwt_identity())
    result  = DashboardService.get_doctor_dashboard(user_id)
    return success_response(result["message"], data=result["data"])


@dashboard_bp.route("/nurse", methods=["GET"])
@role_required(Roles.ADMIN, Roles.NURSE)
def nurse_dashboard():
    result = DashboardService.get_nurse_dashboard()
    return success_response(result["message"], data=result["data"])


@dashboard_bp.route("/pharmacist", methods=["GET"])
@role_required(Roles.ADMIN, Roles.PHARMACIST)
def pharmacist_dashboard():
    result = DashboardService.get_pharmacist_dashboard()
    return success_response(result["message"], data=result["data"])


@dashboard_bp.route("/lab", methods=["GET"])
@role_required(Roles.ADMIN, Roles.LAB_TECH)
def lab_dashboard():
    result = DashboardService.get_lab_dashboard()
    return success_response(result["message"], data=result["data"])