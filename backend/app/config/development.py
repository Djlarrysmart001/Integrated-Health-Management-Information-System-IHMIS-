# app/config/development.py

from .base import BaseConfig


class DevelopmentConfig(BaseConfig):
    """
    Development configuration.
    Debug mode ON — shows detailed error pages and auto-reloads on code changes.
    """
    DEBUG = True
    TESTING = False

    # Longer token expiry during development so you don't have to re-login constantly
    from datetime import timedelta
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=2)