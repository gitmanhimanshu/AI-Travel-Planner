"""HTML page routes. All data loading happens over the JSON API."""

from flask import Blueprint, redirect, render_template, request, url_for

from app.services.destinations_data import all_destinations, popular
from app.utils import current_user

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    return render_template("index.html", destinations=popular(6))


@pages_bp.route("/planner")
def planner():
    return render_template("planner.html", destinations=all_destinations())


@pages_bp.route("/itinerary")
def itinerary():
    # ?trip=<id> loads a saved trip; without it the page reads the freshly
    # generated itinerary from sessionStorage.
    return render_template("itinerary.html", trip_id=request.args.get("trip", type=int))


@pages_bp.route("/explore")
def explore():
    return render_template("explore.html", destinations=all_destinations())


@pages_bp.route("/trips")
def trips():
    if not current_user():
        return redirect(url_for("pages.login", next="/trips"))
    return render_template("trips.html")


@pages_bp.route("/login")
def login():
    if current_user():
        return redirect(url_for("pages.trips"))
    return render_template("login.html")


@pages_bp.route("/register")
def register():
    if current_user():
        return redirect(url_for("pages.trips"))
    return render_template("register.html")


@pages_bp.route("/healthz")
def healthz():
    return {"status": "ok"}
