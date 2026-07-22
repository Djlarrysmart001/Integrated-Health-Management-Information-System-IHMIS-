# app/api/v1/roles/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.role_service import RoleService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

roles_bp = Blueprint("roles", __name__)


@roles_bp.route("", methods=["GET"])
@role_required(Roles.ADMIN)
def get_all_roles():
    result = RoleService.get_all_roles()
    return success_response(result["message"], data=result["data"])


@roles_bp.route("/<int:role_id>", methods=["GET"])
@role_required(Roles.ADMIN)
def get_role(role_id):
    result = RoleService.get_role_by_id(role_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@roles_bp.route("", methods=["POST"])
@role_required(Roles.ADMIN)
def create_role():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    created_by = int(get_jwt_identity())
    result = RoleService.create_role(data, created_by)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


@roles_bp.route("/<int:role_id>", methods=["PUT"])
@role_required(Roles.ADMIN)
def update_role(role_id):
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    updated_by = int(get_jwt_identity())
    result = RoleService.update_role(role_id, data, updated_by)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


@roles_bp.route("/<int:role_id>", methods=["DELETE"])
@role_required(Roles.ADMIN)
def delete_role(role_id):
    deleted_by = int(get_jwt_identity())
    result = RoleService.delete_role(role_id, deleted_by)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"])