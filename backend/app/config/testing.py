# app/config/testing.py

from .base import BaseConfig


class TestingConfig(BaseConfig):
    """
    Testing configuration.
    Uses a separate test database so tests never touch real data.
    """
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:@localhost:3306/ihmis_test_db"
    JWT_ACCESS_TOKEN_EXPIRES = False  # Tokens don't expire during tests