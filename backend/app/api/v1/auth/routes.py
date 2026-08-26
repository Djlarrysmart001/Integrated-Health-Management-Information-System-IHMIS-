from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.auth_service import AuthService
from app.utils.response import success_response, error_response

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return error_response("Username and password are required.", status_code=400)
    result = AuthService.login(username, password)
    if not result["success"]:
        return error_response(result["message"], status_code=401)
    return success_response(result["message"], data=result["data"], status_code=200)


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    result = AuthService.refresh_token()
    if not result["success"]:
        return error_response(result["message"], status_code=401)
    return success_response(result["message"], data=result["data"])


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    result = AuthService.get_current_user(int(user_id))
    if not result["success"]:
        return error_response(result["message"], status_code=404)
    return success_response(result["message"], data=result["data"])


@auth_bp.route("/me", methods=["PUT"])
@jwt_required()
def update_me():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    user_id = get_jwt_identity()
    result = AuthService.update_current_user(int(user_id), data)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"], data=result["data"])


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    return success_response("Logged out successfully.")


@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    data = request.get_json()
    if not data:
        return error_response("Request body must be JSON.", status_code=400)
    current_password = data.get("current_password", "").strip()
    new_password = data.get("new_password", "").strip()
    if not current_password or not new_password:
        return error_response("current_password and new_password are required.", status_code=400)
    user_id = get_jwt_identity()
    result = AuthService.change_password(int(user_id), current_password, new_password)
    if not result["success"]:
        return error_response(result["message"], status_code=400)
    return success_response(result["message"])