# app/config/base.py

import os
from datetime import timedelta


class BaseConfig:
    """
    Base configuration shared across all environments.
    Never instantiate this directly — use Development, Production, or Testing.
    """

    # -----------------------------------------------------------
    # Core Flask settings
    # -----------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")
    APP_NAME = os.getenv("APP_NAME", "IHMIS")
    INSTITUTION_NAME = os.getenv("INSTITUTION_NAME", "My Institution")

    # -----------------------------------------------------------
    # Database — built from individual .env variables
    # -----------------------------------------------------------
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "ihmis_db")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Suppresses a noisy warning

    # Cloud MySQL providers (Aiven, AWS RDS, etc.) require an encrypted
    # connection since traffic travels over the public internet. Local
    # XAMPP development needs no SSL at all, so this stays fully inert
    # unless DB_SSL_CA is actually set in .env -- pointing DB_HOST at
    # a cloud host without setting this will fail to connect, which is
    # the correct/safe behavior (never silently connect unencrypted to
    # a database holding patient records over the public internet).
    DB_SSL_CA = os.getenv("DB_SSL_CA", "")
    SQLALCHEMY_ENGINE_OPTIONS = {}
    if DB_SSL_CA:
        SQLALCHEMY_ENGINE_OPTIONS["connect_args"] = {"ssl": {"ca": DB_SSL_CA}}

    # -----------------------------------------------------------
    # JWT settings
    # -----------------------------------------------------------
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", 15))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES_DAYS", 7))
    )

    # -----------------------------------------------------------
    # Mail settings
    # -----------------------------------------------------------
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")

    # -----------------------------------------------------------
    # Pagination defaults
    # -----------------------------------------------------------
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100