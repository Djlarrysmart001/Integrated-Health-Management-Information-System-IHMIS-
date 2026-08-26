# app/api/v1/users/routes.py

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from app.services.user_service import UserService
from app.utils.response import success_response, error_response
from app.utils.decorators import role_required
from app.utils.constants import Roles

users_bp = Blueprint("users", __name__)


# ─────────────────────────────────────────────────────────────
# GET /api/v1/users
# Returns paginated list of all users (Admin only)
# ─────────────────────────────────────────────────────────────
@users_bp.route("", methods=["GET"])
@role_required(Roles.ADMIN)
def get_all_users():
    page       = request.args.get("page", 1, type=int)
    per_page   = request.args.get("per_page", 20, type=int)
    search     = request.args.get("search", None)
    role       = request.args.get("role", None)
    is_active  = request.args.get("is_active", None)

    # Convert is_active string to boolean
    if is_active is not None:
        is_active = is_active.lower() == "true"

    result = UserService.get_all_users(
        page=page, per_page=per_page,
        search=search, role=role, is_active=is_active
    )
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/users/roles
# Returns all available roles (Admin only)
# ─────────────────────────────────────────────────────────────
@users_bp.route("/roles", methods=["GET"])
@role_required(Roles.ADMIN)
def get_roles():
    result = UserService.get_all_roles()
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# GET /api/v1/users/<id>
# Returns a single user by ID (Admin only)
# ─────────────────────────────────────────────────────────────
@users_bp.route("/<int:user_id>", methods=["GET"])
@role_required(Roles.ADMIN)
def get_user(user_id):
    result = UserService.get_user_by_id(user_id)
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# POST /api/v1/users
# Creates a new user account (Admin only)
# ─────────────────────────────────────────────────────────────
@users_bp.route("", methods=["POST"])
@role_required(Roles.ADMIN)
def create_user():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    performed_by = int(get_jwt_identity())
    result = UserService.create_user(data, performed_by)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"], status_code=201)


# ─────────────────────────────────────────────────────────────
# PUT /api/v1/users/<id>
# Updates a user's details (Admin only)
# ─────────────────────────────────────────────────────────────
@users_bp.route("/<int:user_id>", methods=["PUT"])
@role_required(Roles.ADMIN)
def update_user(user_id):
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)

    performed_by = int(get_jwt_identity())
    result = UserService.update_user(user_id, data, performed_by)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/users/<id>/deactivate
# Deactivates a user account (Admin only)
# ─────────────────────────────────────────────────────────────
@users_bp.route("/<int:user_id>/deactivate", methods=["PATCH"])
@role_required(Roles.ADMIN)
def deactivate_user(user_id):
    requesting_user_id = int(get_jwt_identity())
    result = UserService.deactivate_user(user_id, requesting_user_id)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/users/<id>/reactivate
# Reactivates a user account (Admin only)
# ─────────────────────────────────────────────────────────────
@users_bp.route("/<int:user_id>/reactivate", methods=["PATCH"])
@role_required(Roles.ADMIN)
def reactivate_user(user_id):
    result = UserService.reactivate_user(user_id)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


# ─────────────────────────────────────────────────────────────
# PATCH /api/v1/users/<id>/roles
# Assigns roles to a user (Admin only)
# ─────────────────────────────────────────────────────────────
@users_bp.route("/<int:user_id>/roles", methods=["PATCH"])
@role_required(Roles.ADMIN)
def assign_roles(user_id):
    data = request.get_json()
    if not data or not data.get("roles"):
        return error_response("'roles' field is required.", status_code=400)

    result = UserService.assign_roles(user_id, data["roles"])
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])