"""AI features: travel assistant chat, packing list and budget optimiser."""

import logging

from flask import Blueprint

from app.models import Trip
from app.services.ai_provider import AIProviderError
from app.services.ai_service import chat as ai_chat
from app.services.ai_service import optimize_budget as ai_optimize_budget
from app.services.ai_service import packing_list as ai_packing_list
from app.utils import ApiError, current_user, get_payload, json_ok, require_str

log = logging.getLogger(__name__)

ai_bp = Blueprint("ai", __name__)

MAX_HISTORY = 12
MAX_ITINERARY_DAYS = 21


def _trip_context(data):
    """Resolve trip context from a saved trip id, or from the client payload.

    Anonymous users keep their generated itinerary in sessionStorage, so the
    browser may send it back with the request. Anything that arrives that way is
    treated as untrusted input and trimmed before it reaches a prompt.
    """
    trip_id = data.get("trip_id")
    user = current_user()

    if trip_id and user:
        trip = Trip.query.filter_by(id=trip_id, user_id=user.id).first()
        if not trip:
            raise ApiError("That trip does not exist or is not yours.", 404)
        return trip.to_dict(include_itinerary=False), trip.itinerary

    trip = data.get("trip") if isinstance(data.get("trip"), dict) else {}
    itinerary = data.get("itinerary") if isinstance(data.get("itinerary"), dict) else {}

    safe_trip = {
        key: trip.get(key)
        for key in (
            "destination", "start_location", "start_date", "end_date",
            "duration_days", "travelers", "budget_amount", "budget_level",
            "travel_style", "interests", "transportation", "accommodation",
        )
        if trip.get(key) not in (None, "", [])
    }
    if itinerary.get("days"):
        itinerary = dict(itinerary, days=itinerary["days"][:MAX_ITINERARY_DAYS])
    return safe_trip, itinerary


def _clean_history(raw):
    history = []
    if not isinstance(raw, list):
        return history
    for entry in raw[-MAX_HISTORY:]:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        content = str(entry.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            history.append({"role": role, "content": content[:2000]})
    return history


@ai_bp.post("/chat")
def chat():
    data = get_payload()
    message = require_str(data, "message", label="message", max_length=1000, min_length=2)
    trip, itinerary = _trip_context(data)

    try:
        reply = ai_chat(
            message=message,
            history=_clean_history(data.get("history")),
            trip=trip or None,
            itinerary=itinerary or None,
        )
    except AIProviderError as exc:
        raise ApiError(str(exc), 502)

    return json_ok({"reply": reply})


@ai_bp.post("/packing-list")
def packing_list():
    data = get_payload()
    trip, itinerary = _trip_context(data)
    if not trip.get("destination"):
        raise ApiError("Generate or open a trip first.", 422)

    try:
        result = ai_packing_list(trip=trip, itinerary=itinerary or None)
    except AIProviderError as exc:
        raise ApiError(str(exc), 502)

    return json_ok(result)


@ai_bp.post("/optimize-budget")
def optimize_budget():
    data = get_payload()
    trip, itinerary = _trip_context(data)
    if not itinerary:
        raise ApiError("Generate a trip before optimising its budget.", 422)

    target = data.get("target_budget") or trip.get("budget_amount")
    try:
        target = float(target)
    except (TypeError, ValueError):
        raise ApiError("Enter the budget you want to stay within.", 422)
    if target <= 0:
        raise ApiError("Enter a budget greater than zero.", 422)

    try:
        result = ai_optimize_budget(trip=trip, itinerary=itinerary, target_budget=target)
    except AIProviderError as exc:
        raise ApiError(str(exc), 502)

    return json_ok(result)
