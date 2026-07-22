# app/utils/response.py

from flask import jsonify


def success_response(message: str, data=None, status_code: int = 200):
    """
    Returns a standardised success JSON response.

    Example output:
    {
        "success": true,
        "message": "Patient retrieved successfully.",
        "data": { ... }
    }
    """
    response = {
        "success": True,
        "message": message,
    }
    if data is not None:
        response["data"] = data

    return jsonify(response), status_code


def error_response(message: str, errors=None, status_code: int = 400):
    """
    Returns a standardised error JSON response.

    Example output:
    {
        "success": false,
        "message": "Validation failed.",
        "errors": { "email": ["Not a valid email address."] }
    }
    """
    response = {
        "success": False,
        "message": message,
    }
    if errors is not None:
        response["errors"] = errors

    return jsonify(response), status_code