# app/utils/decorators.py

from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.utils.response import error_response


def role_required(*allowed_roles):
    """
    Decorator that protects a route by role.

    Usage:
        @role_required("Admin")
        @role_required("Doctor", "Nurse")
        @role_required(*Roles.ALL)   # any logged-in user

    How it works:
        1. Verifies the JWT token is present and valid
        2. Loads the user from the database
        3. Checks if the user has one of the allowed roles
        4. If not, returns 403 Forbidden
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Step 1: verify JWT token exists and is valid
            verify_jwt_in_request()

            # Step 2: get user identity from token
            from app.models.user import User
            user_id = get_jwt_identity()
            user = User.query.get(user_id)

            # Step 3: check user exists and is active
            if not user or not user.is_active:
                return error_response(
                    "Account not found or deactivated.", status_code=401
                )

            # Step 4: check role
            if allowed_roles:
                user_roles = [r.name for r in user.roles]
                if not any(role in user_roles for role in allowed_roles):
                    return error_response(
                        f"Access denied. Required role: {' or '.join(allowed_roles)}",
                        status_code=403
                    )

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def jwt_required_custom():
    """
    Decorator that just verifies JWT without role checking.
    Use this for endpoints any logged-in user can access.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            from app.models.user import User
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return error_response(
                    "Account not found or deactivated.", status_code=401
                )
            return fn(*args, **kwargs)
        return wrapper
    return decorator