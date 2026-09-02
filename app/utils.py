"""Shared helpers: JSON responses, auth guards, CSRF and input validation."""

import re
import secrets
from datetime import date, datetime
from functools import wraps

from flask import current_app, jsonify, request, session

from app.models import User

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class ApiError(Exception):
    """Raised anywhere in a request to return a clean JSON error."""

    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details or {}


# --------------------------------------------------------------------------
# Responses
# --------------------------------------------------------------------------
def json_ok(payload=None, status=200, **extra):
    body = {"success": True}
    if payload:
        body.update(payload)
    body.update(extra)
    return jsonify(body), status


def json_error(message, status=400, **extra):
    body = {"success": False, "error": message}
    body.update(extra)
    return jsonify(body), status


# --------------------------------------------------------------------------
# CSRF (double-submit token stored in the session)
# --------------------------------------------------------------------------
def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def verify_csrf():
    """Reject state-changing API calls without a matching CSRF token."""
    if request.method in SAFE_METHODS:
        return
    if not request.path.startswith("/api/"):
        return
    expected = session.get("csrf_token")
    provided = request.headers.get(CSRF_HEADER) or (
        request.get_json(silent=True) or {}
    ).get("csrf_token")
    if not expected or not provided or not secrets.compare_digest(str(expected), str(provided)):
        raise ApiError("Your session expired. Please refresh the page and try again.", 403)


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def login_user(user):
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    get_csrf_token()


def logout_user():
    session.clear()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            raise ApiError("Please log in to continue.", 401)
        return view(*args, **kwargs)

    return wrapper


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def get_payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Expected a JSON request body.", 400)
    return data


def require_str(data, key, label=None, max_length=200, min_length=1):
    value = (data.get(key) or "").strip() if isinstance(data.get(key), str) else ""
    label = label or key.replace("_", " ")
    if len(value) < min_length:
        raise ApiError(f"{label.capitalize()} is required.", 422)
    if len(value) > max_length:
        raise ApiError(f"{label.capitalize()} must be under {max_length} characters.", 422)
    return value


def optional_str(data, key, max_length=2000):
    value = data.get(key)
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def require_int(data, key, minimum=1, maximum=None, default=None):
    raw = data.get(key, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError(f"{key.replace('_', ' ').capitalize()} must be a number.", 422)
    if value < minimum:
        raise ApiError(f"{key.replace('_', ' ').capitalize()} must be at least {minimum}.", 422)
    if maximum is not None and value > maximum:
        raise ApiError(f"{key.replace('_', ' ').capitalize()} cannot exceed {maximum}.", 422)
    return value


def optional_float(data, key, minimum=0):
    raw = data.get(key)
    if raw in (None, "", []):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ApiError(f"{key.replace('_', ' ').capitalize()} must be a number.", 422)
    if value < minimum:
        raise ApiError(f"{key.replace('_', ' ').capitalize()} cannot be negative.", 422)
    return value


def parse_date(value, label):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        raise ApiError(f"{label} must be a valid date (YYYY-MM-DD).", 422)


def clean_list(data, key, allowed=None, max_items=15):
    """Normalise a list field coming from the form (list or CSV string)."""
    raw = data.get(key) or []
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",")]
    if not isinstance(raw, list):
        raise ApiError(f"{key.replace('_', ' ').capitalize()} must be a list.", 422)

    values, seen = [], set()
    for item in raw:
        item = str(item).strip()
        if not item or item.lower() in seen:
            continue
        if allowed and item.lower() not in allowed:
            continue
        seen.add(item.lower())
        values.append(item)
    return values[:max_items]


def validate_email(value):
    value = (value or "").strip().lower()
    if not EMAIL_RE.match(value) or len(value) > 255:
        raise ApiError("Please enter a valid email address.", 422)
    return value


def validate_password(value):
    if not isinstance(value, str) or len(value) < 8:
        raise ApiError("Password must be at least 8 characters long.", 422)
    if len(value) > 128:
        raise ApiError("Password must be under 128 characters.", 422)
    return value


def trip_duration(start, end, fallback=1):
    """Inclusive day count between two dates."""
    if not start or not end:
        return fallback
    days = (end - start).days + 1
    if days < 1:
        raise ApiError("End date must be on or after the start date.", 422)
    return min(days, current_app.config["MAX_TRIP_DAYS"])
