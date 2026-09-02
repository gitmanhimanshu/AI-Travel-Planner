"""Session-based authentication API."""

from flask import Blueprint

from app.extensions import db
from app.models import User
from app.utils import (
    ApiError,
    current_user,
    get_csrf_token,
    get_payload,
    json_ok,
    login_required,
    login_user,
    logout_user,
    require_str,
    validate_email,
    validate_password,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    data = get_payload()
    name = require_str(data, "name", max_length=120, min_length=2)
    email = validate_email(data.get("email"))
    password = validate_password(data.get("password"))

    if User.query.filter_by(email=email).first():
        raise ApiError("An account with that email already exists.", 409)

    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user)
    return json_ok({"user": user.to_dict(), "csrf_token": get_csrf_token()}, status=201)


@auth_bp.post("/login")
def login():
    data = get_payload()
    email = validate_email(data.get("email"))
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    # One message for both cases so the endpoint cannot enumerate accounts.
    if not user or not user.check_password(password):
        raise ApiError("Incorrect email or password.", 401)

    login_user(user)
    return json_ok({"user": user.to_dict(), "csrf_token": get_csrf_token()})


@auth_bp.post("/logout")
def logout():
    logout_user()
    return json_ok({"csrf_token": get_csrf_token()}, message="Signed out.")


@auth_bp.get("/me")
def me():
    user = current_user()
    return json_ok({"user": user.to_dict() if user else None, "csrf_token": get_csrf_token()})


@auth_bp.get("/session")
@login_required
def session_info():
    return json_ok({"user": current_user().to_dict()})
