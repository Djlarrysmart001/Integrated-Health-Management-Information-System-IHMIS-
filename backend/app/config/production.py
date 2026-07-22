# app/config/production.py

from .base import BaseConfig


class ProductionConfig(BaseConfig):
    """
    Production configuration.
    Debug is OFF — never expose stack traces to end users in production.
    """
    DEBUG = False
    TESTING = False