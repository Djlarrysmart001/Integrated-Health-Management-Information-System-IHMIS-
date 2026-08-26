# app/api/v1/health_files/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.health_file_service import HealthFileService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles
from app.utils.dates import resolve_date_range

health_files_bp = Blueprint("health_files", __name__)

# Any clinical role can read a health file / a patient's history —
# needed for continuity of care (Doctor viewing history, Lab viewing
# the request context, etc).
ALL_CLINICAL_ROLES = (Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER, Roles.NURSE,
                       Roles.DOCTOR, Roles.LAB_TECH, Roles.PHARMACIST)


# ─────────────────────────────────────────────────────────────
# POST /api/v1/health-files
# MHO opens a new health file for a patient
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("", methods=["POST"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)
def open_health_file():
    data = request.get_json()
    if not data or not data.get("patient_id"):
        return error_response("'patient_id' is required.", status_code=400)

    opened_by = int(get_jwt_identity())
    result = HealthFileService.open_health_file(data["patient_id"], opened_by)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/forward-to-nurse
# MHO forwards the file to the Nurse queue
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/forward-to-nurse", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)
def forward_to_nurse(health_file_id):
    user_id = int(get_jwt_identity())
    result = HealthFileService.forward_to_nurse(health_file_id, user_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/forward-to-doctor
# Nurse forwards the file to the Doctor queue (after recording vitals)
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/forward-to-doctor", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.NURSE)
def forward_to_doctor(health_file_id):
    user_id = int(get_jwt_identity())
    result = HealthFileService.forward_to_doctor(health_file_id, user_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/forward-to-lab
# Doctor sends the file to the Lab queue
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/forward-to-lab", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.DOCTOR)
def forward_to_lab(health_file_id):
    user_id = int(get_jwt_identity())
    result = HealthFileService.forward_to_lab(health_file_id, user_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/return-from-lab
# Lab sends the file back to the Doctor once results are ready
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/return-from-lab", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.LAB_TECH)
def return_from_lab(health_file_id):
    user_id = int(get_jwt_identity())
    result = HealthFileService.return_from_lab(health_file_id, user_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/forward-to-pharmacy
# Doctor sends the file to the Pharmacy queue
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/forward-to-pharmacy", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.DOCTOR)
def forward_to_pharmacy(health_file_id):
    user_id = int(get_jwt_identity())
    result = HealthFileService.forward_to_pharmacy(health_file_id, user_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/close
# Pharmacist closes the file once medicine is dispensed
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/close", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.PHARMACIST)
def close_health_file(health_file_id):
    user_id = int(get_jwt_identity())
    result = HealthFileService.close_health_file(health_file_id, user_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/mho-close
# MHO manual override — closes a visit from any non-closed state,
# for edge cases like a patient leaving before treatment completes.
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/mho-close", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)
def mho_manual_close(health_file_id):
    data    = request.get_json() or {}
    user_id = int(get_jwt_identity())
    result  = HealthFileService.mho_manual_close(health_file_id, user_id, reason=data.get("reason"))

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/admit
# Doctor admits the patient for inpatient monitoring -- the file goes
# to the Nurse's care (status "admitted"), NOT to "closed". See
# HealthFileService.admit_patient for why this is distinct from a
# referral-close.
#
# This also creates the real Admission record (ward, admission_reason)
# via AdmissionService -- that model already existed with proper
# ward/bed/discharge-summary fields but was never wired to any route
# before now. AdmissionService.admit_patient is the one that actually
# creates the row AND triggers this same HealthFileService transition
# internally, so the two stay in sync from a single call here.
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/admit", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.DOCTOR)
def admit_patient(health_file_id):
    from app.services.admission_service import AdmissionService

    from app.models.health_file import HealthFile

    data    = request.get_json() or {}
    user_id = int(get_jwt_identity())

    health_file = HealthFile.query.get(health_file_id)
    if not health_file:
        return error_response(f"Health file with ID {health_file_id} not found.", status_code=404)

    result = AdmissionService.admit_patient(
        data={
            "patient_id":       health_file.patient_id,
            "health_file_id":   health_file_id,
            "ward":             data.get("ward"),
            "admission_reason": data.get("admission_reason"),
        },
        admitted_by=user_id,
    )

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/health-files/<id>/discharge
# Doctor discharges a patient after an admission -- only reachable
# from "with_doctor", i.e. only after the Nurse has forwarded an
# admitted patient back for a final review. There is deliberately no
# direct "admitted -> closed" shortcut.
#
# Finds the matching active Admission record and discharges it too
# (via AdmissionService, which syncs the health file closure
# internally). Falls back to closing the health file directly if no
# Admission record is linked -- shouldn't normally happen given the
# only path to "admitted" now goes through AdmissionService above,
# but this keeps the button from hard-failing on an edge case.
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/discharge", methods=["PATCH"])
@role_required(Roles.ADMIN, Roles.DOCTOR)
def discharge_patient(health_file_id):
    from app.services.admission_service import AdmissionService
    from app.models.admission import Admission

    data    = request.get_json() or {}
    user_id = int(get_jwt_identity())

    active_admission = Admission.query.filter_by(
        health_file_id=health_file_id, status="admitted"
    ).order_by(Admission.admission_date.desc()).first()

    if active_admission:
        result = AdmissionService.discharge_patient(
            active_admission.id, user_id, discharge_summary=data.get("discharge_summary")
        )
    else:
        result = HealthFileService.discharge_patient(health_file_id, user_id)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/health-files/queue/<status>
# Each role's queue: with_mho, with_nurse, with_doctor, with_lab, with_pharmacy
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/queue/<string:status>", methods=["GET"])
@role_required(*ALL_CLINICAL_ROLES)
def get_queue(status):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    result = HealthFileService.get_queue(status, page=page, per_page=per_page)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/health-files/<id>
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>", methods=["GET"])
@role_required(*ALL_CLINICAL_ROLES)
def get_health_file(health_file_id):
    result = HealthFileService.get_health_file(health_file_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/health-files/patient/<patient_id>
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/patient/<int:patient_id>", methods=["GET"])
@role_required(*ALL_CLINICAL_ROLES)
def get_patient_health_files(patient_id):
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    result = HealthFileService.get_patient_health_files(patient_id, page=page, per_page=per_page)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/health-files/<id>/care-trail
# Admin-only: full accountability trail for investigations
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/<int:health_file_id>/care-trail", methods=["GET"])
@role_required(Roles.ADMIN)
def get_care_trail(health_file_id):
    result = HealthFileService.get_care_trail(health_file_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/health-files/stats/forwards/<action>
# Personal work-log count -- "how many did I forward today/this week".
#
# Deliberately backed by AuditLog, not HealthFile.status -- see
# HealthFileService.count_forwards() docstring for why the live queue
# would undercount. <action> must be one of the known forward actions
# (ACTION_MESSAGES keys) to keep this from becoming a free-text audit
# log query endpoint.
# ─────────────────────────────────────────────────────────────
@health_files_bp.route("/stats/forwards/<string:action>", methods=["GET"])
@role_required(*ALL_CLINICAL_ROLES)
def get_forward_count(action):
    from app.services.health_file_service import ACTION_MESSAGES

    if action not in ACTION_MESSAGES:
        return error_response(
            f"'{action}' is not a recognised forward action. "
            f"Must be one of: {', '.join(ACTION_MESSAGES.keys())}.",
            status_code=400,
        )

    from app.models.user import User

    current_user_id = int(get_jwt_identity())
    current_user    = User.query.get(current_user_id)
    current_roles   = [r.name for r in current_user.roles] if current_user else []
    is_admin        = Roles.ADMIN in current_roles

    by_arg = request.args.get("by")
    if is_admin:
        # Admin may view any user's count, or the clinic-wide total if
        # `by` is omitted entirely.
        user_id = current_user_id if by_arg == "me" else (int(by_arg) if by_arg else None)
    else:
        # Every other role can only ever see their OWN count -- same
        # "no browsing other people's work" principle as the vitals fix.
        user_id = current_user_id

    range_key     = request.args.get("range")
    date_from_arg = request.args.get("date_from")
    date_to_arg   = request.args.get("date_to")
    date_from, date_to = resolve_date_range(range_key, date_from_arg, date_to_arg)

    count = HealthFileService.count_forwards(
        action=action, user_id=user_id, date_from=date_from, date_to=date_to
    )
    return success_response(
        f"{count} '{action}' event(s) found.",
        data={"action": action, "user_id": user_id, "count": count},
    )