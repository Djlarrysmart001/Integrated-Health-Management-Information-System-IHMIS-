# app/api/v1/documents/routes.py

from flask import Blueprint, request, Response
from flask_jwt_extended import get_jwt_identity
from app.services.patient_document_service import PatientDocumentService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

documents_bp = Blueprint("documents", __name__)

# Same clinical-role set as patients_bp.ALL_ROLES -- any role that can
# view a patient's file can view their documents too.
VIEW_ROLES = (Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER, Roles.DOCTOR,
              Roles.NURSE, Roles.PHARMACIST, Roles.LAB_TECH)

# Upload/delete restricted to MHO + Admin -- documents (ID cards,
# referral letters, consent forms) are MHO's records-custody
# responsibility, not general clinical staff's.
MANAGE_ROLES = (Roles.ADMIN, Roles.MEDICAL_HEALTH_OFFICER)


# ─────────────────────────────────────────────────────────────
# POST /api/v1/documents/patients/<patient_id>
# ─────────────────────────────────────────────────────────────
@documents_bp.route("/patients/<int:patient_id>", methods=["POST"])
@role_required(*MANAGE_ROLES)
def upload_document(patient_id):
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    uploaded_by = int(get_jwt_identity())
    result = PatientDocumentService.upload_document(patient_id, data, uploaded_by)

    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


# ─────────────────────────────────────────────────────────────
# GET /api/v1/documents/patients/<patient_id>
# ─────────────────────────────────────────────────────────────
@documents_bp.route("/patients/<int:patient_id>", methods=["GET"])
@role_required(*VIEW_ROLES)
def get_patient_documents(patient_id):
    result = PatientDocumentService.get_patient_documents(patient_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/documents/<document_id>/download
# Serves the raw file bytes -- not JSON.
# ─────────────────────────────────────────────────────────────
@documents_bp.route("/<int:document_id>/download", methods=["GET"])
@role_required(*VIEW_ROLES)
def download_document(document_id):
    result = PatientDocumentService.get_document_file(document_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)

    file_data = result["data"]
    response = Response(file_data["file_data"], mimetype=file_data["file_mime"])
    response.headers["Content-Disposition"] = f'inline; filename="{file_data["file_name"]}"'
    return response


# ─────────────────────────────────────────────────────────────
# DELETE /api/v1/documents/<document_id>
# ─────────────────────────────────────────────────────────────
@documents_bp.route("/<int:document_id>", methods=["DELETE"])
@role_required(*MANAGE_ROLES)
def delete_document(document_id):
    deleted_by = int(get_jwt_identity())
    result = PatientDocumentService.delete_document(document_id, deleted_by)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"])