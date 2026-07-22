# app/__init__.py

import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask
from dotenv import load_dotenv

from app.config import config_map
from app.extensions import db, migrate, jwt, bcrypt, mail, cors

load_dotenv()


def create_app(config_name: str = None) -> Flask:

    flask_app = Flask(__name__)

    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    config_class = config_map.get(config_name, config_map["development"])
    flask_app.config.from_object(config_class)

    db.init_app(flask_app)
    migrate.init_app(flask_app, db)
    jwt.init_app(flask_app)
    bcrypt.init_app(flask_app)
    mail.init_app(flask_app)
    cors.init_app(flask_app, resources={r"/api/*": {"origins": "*"}})

    import app.models  # noqa: F401

    from app.api import register_blueprints
    register_blueprints(flask_app)

    from app.middleware.error_handlers import register_error_handlers
    register_error_handlers(flask_app)

    _configure_logging(flask_app)

    from app.commands import register_commands
    register_commands(flask_app)

    @flask_app.route("/health")
    def health_check():
        return {"status": "ok", "app": flask_app.config.get("APP_NAME")}, 200

    flask_app.logger.info(f"IHMIS started in [{config_name.upper()}] mode")

    return flask_app


def _configure_logging(flask_app: Flask) -> None:
    if not os.path.exists("logs"):
        os.makedirs("logs")

    file_handler = RotatingFileHandler(
        "logs/ihmis.log", maxBytes=10_000_000, backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    ))
    file_handler.setLevel(logging.INFO)

    flask_app.logger.addHandler(file_handler)
    flask_app.logger.setLevel(logging.INFO)