# app/api/v1/mho/routes.py

from flask import Blueprint
from app.services.health_file_service import HealthFileService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

mho_bp = Blueprint("mho", __name__)

# Admin included for oversight/testing, same convention as admissions_bp's
# VIEW_ROLES -- MHO is the primary user, Admin can view but this route
# has no write action so no separate "action" role list is needed.
DASHBOARD_ROLES = (Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)


@mho_bp.route("/dashboard", methods=["GET"])
@role_required(*DASHBOARD_ROLES)
def get_mho_dashboard():
    """
    Aggregated KPI stats for the MHO dashboard cards: patients
    registered today, checked-in today, waiting for nurse, active
    visits, completed today, new vs returning, average check-in time.
    """
    result = HealthFileService.get_mho_dashboard_stats()

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])