"""Application factory, blueprint registration and global error handling."""

import logging
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from app.extensions import cors, db
from config import env, get_config


def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(get_config(config_name))

    _ensure_instance_folder(app)
    _configure_logging(app)

    db.init_app(app)
    # Same-origin by default; set CORS_ORIGINS to expose the API elsewhere.
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": env("CORS_ORIGINS", "*")}},
        supports_credentials=True,
    )

    _register_blueprints(app)
    _register_hooks(app)
    _register_error_handlers(app)

    with app.app_context():
        db.create_all()

    return app


def _ensure_instance_folder(app):
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite:///"):
        Path(uri.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)


def _configure_logging(app):
    level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=level, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    )
    app.logger.setLevel(level)

    # HTTP client debug logs would dump full prompts (and user trip details)
    # into the console. Opt in explicitly with VERBOSE_HTTP_LOGS=true.
    if (env("VERBOSE_HTTP_LOGS", "") or "").lower() not in {"1", "true", "yes"}:
        for name in ("anthropic", "httpx", "httpx2", "httpcore", "httpcore2", "urllib3"):
            logging.getLogger(name).setLevel(logging.WARNING)


def _register_blueprints(app):
    from app.routes.ai import ai_bp
    from app.routes.auth import auth_bp
    from app.routes.destinations import destinations_bp
    from app.routes.pages import pages_bp
    from app.routes.trips import trips_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(trips_bp, url_prefix="/api/trips")
    app.register_blueprint(ai_bp, url_prefix="/api/ai")
    app.register_blueprint(destinations_bp, url_prefix="/api")


def _register_hooks(app):
    from app.utils import get_csrf_token, verify_csrf

    @app.before_request
    def _csrf_guard():
        verify_csrf()

    @app.context_processor
    def _inject_globals():
        from app.services.ai_provider import provider_is_live
        from app.utils import current_user

        return {
            "csrf_token": get_csrf_token(),
            "current_user": current_user(),
            "ai_is_live": provider_is_live(),
        }


def _register_error_handlers(app):
    from app.utils import ApiError

    def wants_json():
        return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"

    @app.errorhandler(ApiError)
    def _handle_api_error(error):
        payload = {"success": False, "error": error.message}
        if error.details:
            payload["details"] = error.details
        return jsonify(payload), error.status

    @app.errorhandler(SQLAlchemyError)
    def _handle_db_error(error):
        db.session.rollback()
        app.logger.exception("Database error")
        message = "We could not reach the database. Please try again."
        if wants_json():
            return jsonify({"success": False, "error": message}), 500
        return render_template("errors/500.html", message=message), 500

    @app.errorhandler(404)
    def _handle_404(error):
        if wants_json():
            return jsonify({"success": False, "error": "Not found."}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(405)
    def _handle_405(error):
        return jsonify({"success": False, "error": "Method not allowed."}), 405

    @app.errorhandler(413)
    def _handle_413(error):
        return jsonify({"success": False, "error": "That request was too large."}), 413

    @app.errorhandler(Exception)
    def _handle_unexpected(error):
        # Let Flask's own HTTP errors (abort(...), routing failures) keep their
        # status code and message instead of becoming a generic 500.
        if isinstance(error, HTTPException):
            if wants_json():
                return (
                    jsonify({"success": False, "error": error.description}),
                    error.code or 500,
                )
            return error
        db.session.rollback()
        app.logger.exception("Unhandled error")
        message = "Something went wrong on our side. Please try again."
        if wants_json():
            return jsonify({"success": False, "error": message}), 500
        return render_template("errors/500.html", message=message), 500
