# app/config/__init__.py

from .development import DevelopmentConfig
from .production import ProductionConfig
from .testing import TestingConfig

# This dictionary lets create_app() pick the right config
# by passing a simple string like "development" or "production"
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}