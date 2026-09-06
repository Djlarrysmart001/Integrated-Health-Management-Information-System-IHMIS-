# app/__init__.py

import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, send_from_directory, abort
from dotenv import load_dotenv

from app.config import config_map
from app.extensions import db, migrate, jwt, bcrypt, mail, cors

load_dotenv()

# The frontend lives as a sibling directory to backend/, i.e.
# repo_root/frontend, repo_root/backend/app/__init__.py (this file).
# Resolved as an absolute path so this works the same whether Flask is
# started from backend/ (local dev) or from the repo root (Render, whose
# working directory depends on the configured Root Directory setting).
FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
)


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

    # ─────────────────────────────────────────────────────────
    # Serve the frontend directly from this same Flask app/origin.
    # Registered last and deliberately excludes anything under "api/"
    # (belt-and-braces on top of Werkzeug's own static-route-priority
    # behavior) so it can never shadow a real API endpoint. Falls back
    # to index.html for any unmatched path rather than a bare 404, so a
    # stale/mistyped link still lands the user on the sign-in page
    # instead of an ugly error screen.
    # ─────────────────────────────────────────────────────────
    @flask_app.route("/", defaults={"req_path": "index.html"})
    @flask_app.route("/<path:req_path>")
    def serve_frontend(req_path):
        if req_path.startswith("api/"):
            abort(404)
        full_path = os.path.join(FRONTEND_DIR, req_path)
        if os.path.isfile(full_path):
            return send_from_directory(FRONTEND_DIR, req_path)
        return send_from_directory(FRONTEND_DIR, "index.html")

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