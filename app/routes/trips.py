"""Trip generation, storage and management."""

import json
import logging

from flask import Blueprint, current_app

from app.extensions import db
from app.models import Favorite, Trip
from app.services.ai_provider import AIProviderError
from app.services.ai_service import generate_itinerary
from app.utils import (
    ApiError,
    clean_list,
    current_user,
    get_payload,
    json_ok,
    login_required,
    optional_float,
    optional_str,
    parse_date,
    require_int,
    require_str,
    trip_duration,
)

log = logging.getLogger(__name__)

trips_bp = Blueprint("trips", __name__)

BUDGET_LEVELS = {"budget", "moderate", "luxury"}
TRANSPORT_OPTIONS = {"flight", "train", "bus", "car", "bike"}
ACCOMMODATION_OPTIONS = {"hotel", "hostel", "resort", "homestay", "budget stay"}
TRAVEL_STYLES = {
    "adventure", "relaxation", "family", "romantic", "solo",
    "backpacking", "luxury", "cultural", "food & travel",
}
INTERESTS = {
    "nature", "mountains", "beaches", "historical places", "food", "shopping",
    "nightlife", "trekking", "photography", "museums", "local culture",
}


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------
def parse_trip_input(data):
    """Validate the planner form and return a clean trip dict."""
    start_date = parse_date(data.get("start_date"), "Start date")
    end_date = parse_date(data.get("end_date"), "End date")
    duration = trip_duration(start_date, end_date, fallback=require_int(data, "duration_days", minimum=1, maximum=current_app.config["MAX_TRIP_DAYS"], default=3))

    budget_level = (data.get("budget_level") or "moderate").strip().lower()
    if budget_level not in BUDGET_LEVELS:
        raise ApiError("Choose a budget level: budget, moderate or luxury.", 422)

    transportation = (data.get("transportation") or "").strip().lower()
    if transportation and transportation not in TRANSPORT_OPTIONS:
        raise ApiError("That transportation option is not supported.", 422)

    accommodation = (data.get("accommodation") or "").strip().lower()
    if accommodation and accommodation not in ACCOMMODATION_OPTIONS:
        raise ApiError("That accommodation option is not supported.", 422)

    return {
        "destination": require_str(data, "destination", max_length=160, min_length=2),
        "start_location": require_str(data, "start_location", max_length=160, min_length=2),
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "duration_days": duration,
        "travelers": require_int(
            data, "travelers", minimum=1, maximum=current_app.config["MAX_TRAVELERS"], default=1
        ),
        "budget_level": budget_level,
        "budget_amount": optional_float(data, "budget_amount"),
        "travel_style": clean_list(data, "travel_style", allowed=TRAVEL_STYLES, max_items=5),
        "interests": clean_list(data, "interests", allowed=INTERESTS, max_items=8),
        "transportation": transportation,
        "accommodation": accommodation,
        "notes": optional_str(data, "notes", max_length=1200),
    }


def _persist(trip_input, itinerary, user):
    trip = Trip(
        user_id=user.id,
        destination=trip_input["destination"],
        start_location=trip_input["start_location"],
        start_date=parse_date(trip_input["start_date"], "Start date"),
        end_date=parse_date(trip_input["end_date"], "End date"),
        duration_days=trip_input["duration_days"],
        travelers=trip_input["travelers"],
        budget_level=trip_input["budget_level"],
        budget_amount=trip_input["budget_amount"],
        travel_style=json.dumps(trip_input["travel_style"]),
        interests=json.dumps(trip_input["interests"]),
        transportation=trip_input["transportation"],
        accommodation=trip_input["accommodation"],
        notes=trip_input["notes"],
    )
    trip.itinerary = itinerary
    db.session.add(trip)
    db.session.commit()
    return trip


def _owned_trip(trip_id):
    user = current_user()
    trip = Trip.query.filter_by(id=trip_id, user_id=user.id).first()
    if not trip:
        raise ApiError("That trip does not exist or is not yours.", 404)
    return trip


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@trips_bp.post("/generate")
def generate():
    """Generate an itinerary. Saved to the account when the user is signed in."""
    trip_input = parse_trip_input(get_payload())

    try:
        itinerary = generate_itinerary(trip_input)
    except AIProviderError as exc:
        raise ApiError(str(exc), 502)

    user = current_user()
    trip_id = None
    if user:
        trip_id = _persist(trip_input, itinerary, user).id

    return json_ok(
        {
            "trip_id": trip_id,
            "saved": bool(trip_id),
            "trip": trip_input,
            "itinerary": itinerary,
        },
        status=201,
    )


@trips_bp.get("")
@trips_bp.get("/")
@login_required
def list_trips():
    user = current_user()
    trips = (
        Trip.query.filter_by(user_id=user.id).order_by(Trip.created_at.desc()).limit(100).all()
    )
    return json_ok({"trips": [trip.to_dict(include_itinerary=False) for trip in trips]})


@trips_bp.get("/<int:trip_id>")
@login_required
def get_trip(trip_id):
    return json_ok({"trip": _owned_trip(trip_id).to_dict()})


@trips_bp.delete("/<int:trip_id>")
@login_required
def delete_trip(trip_id):
    trip = _owned_trip(trip_id)
    db.session.delete(trip)
    db.session.commit()
    return json_ok(message="Trip deleted.")


@trips_bp.post("/<int:trip_id>/favorite")
@login_required
def toggle_favorite(trip_id):
    trip = _owned_trip(trip_id)
    user = current_user()

    favorite = Favorite.query.filter_by(user_id=user.id, trip_id=trip.id).first()
    if favorite:
        db.session.delete(favorite)
        is_favorite = False
    else:
        db.session.add(Favorite(user_id=user.id, trip_id=trip.id))
        is_favorite = True
    db.session.commit()

    return json_ok({"is_favorite": is_favorite, "trip_id": trip.id})
