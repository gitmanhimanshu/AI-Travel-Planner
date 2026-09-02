"""Validation and normalisation of AI-generated itineraries.

The model is schema-constrained, but this layer is what lets the frontend stay
simple: every key it renders is guaranteed to exist, numbers are numbers, days
are numbered and dated, and the budget maths is recomputed server-side.
"""

from datetime import date, datetime, timedelta

PERIODS = ("morning", "afternoon", "evening")
BUDGET_KEYS = ("transport", "accommodation", "food", "activities", "miscellaneous")


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------
def as_number(value, default=0.0):
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
        return default
    return round(max(number, 0.0), 2)


def as_text(value, default="", limit=2000):
    if value is None:
        return default
    text = str(value).strip()
    return (text or default)[:limit]


def as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, (str, int, float)) and str(value).strip():
        return [value]
    return []


def as_str_list(value, limit=30):
    return [as_text(item, limit=300) for item in as_list(value) if as_text(item)][:limit]


def _dicts(value, limit=30):
    return [item for item in as_list(value) if isinstance(item, dict)][:limit]


def _parse_date(value):
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Section normalisers
# ---------------------------------------------------------------------------
def _normalize_activity(raw, fallback_period="morning"):
    period = as_text(raw.get("period")).lower()
    if period not in PERIODS:
        period = fallback_period
    return {
        "period": period,
        "time": as_text(raw.get("time"), "", limit=30),
        "activity": as_text(raw.get("activity"), "Free time", limit=300),
        "description": as_text(raw.get("description"), "", limit=1200),
        "estimated_cost": as_number(raw.get("estimated_cost")),
    }


def _normalize_day(raw, index, start_date, destination):
    activities = []
    for position, item in enumerate(_dicts(raw.get("activities"), limit=12)):
        activities.append(_normalize_activity(item, PERIODS[min(position, 2)]))

    foods = []
    for item in _dicts(raw.get("food_recommendations"), limit=6):
        foods.append(
            {
                "name": as_text(item.get("name"), "Local restaurant", limit=160),
                "dish": as_text(item.get("dish"), "", limit=160),
                "approx_cost": as_number(item.get("approx_cost")),
            }
        )

    day_cost = as_number(raw.get("estimated_cost"))
    if not day_cost:
        day_cost = round(sum(item["estimated_cost"] for item in activities), 2)

    day_date = start_date + timedelta(days=index - 1) if start_date else None

    return {
        "day": index,
        "date": day_date.isoformat() if day_date else None,
        "date_label": day_date.strftime("%a, %d %b %Y") if day_date else "",
        "title": as_text(raw.get("title"), "Day " + str(index), limit=200),
        "location": as_text(raw.get("location"), destination, limit=160),
        "activities": activities,
        "morning": [item for item in activities if item["period"] == "morning"],
        "afternoon": [item for item in activities if item["period"] == "afternoon"],
        "evening": [item for item in activities if item["period"] == "evening"],
        "food_recommendations": foods,
        "estimated_cost": day_cost,
    }


def _placeholder_day(index, start_date, destination):
    return _normalize_day(
        {
            "title": "Day " + str(index) + " - flexible day",
            "location": destination,
            "activities": [
                {
                    "period": "morning",
                    "time": "",
                    "activity": "Open day",
                    "description": (
                        "The AI did not return a plan for this day. Use the assistant "
                        "below to fill it in, or regenerate the trip."
                    ),
                    "estimated_cost": 0,
                }
            ],
            "food_recommendations": [],
            "estimated_cost": 0,
        },
        index,
        start_date,
        destination,
    )


def _normalize_budget(raw, days, transport_cost, stay_cost):
    breakdown = raw if isinstance(raw, dict) else {}
    values = {key: as_number(breakdown.get(key)) for key in BUDGET_KEYS}

    # Fall back to the section-level estimates when the breakdown is missing them.
    if not values["transport"]:
        values["transport"] = transport_cost
    if not values["accommodation"]:
        values["accommodation"] = stay_cost
    if not values["food"] and days:
        values["food"] = round(sum(day["estimated_cost"] for day in days) * 0.3, 2)

    parts_total = round(sum(values.values()), 2)
    stated_total = as_number(breakdown.get("total"))
    # Trust the parts: a stated total that disagrees is a model slip.
    total = parts_total if parts_total else stated_total
    values["total"] = total
    return values


def _normalize_alert(raw, total, user_budget):
    alert = raw if isinstance(raw, dict) else {}
    alternatives = as_str_list(alert.get("cheaper_alternatives"), limit=8)
    message = as_text(alert.get("message"), limit=600)

    if user_budget:
        over = total > user_budget
        if over and not message:
            message = (
                "This plan is about "
                + str(int(total - user_budget))
                + " INR over your budget."
            )
        if not over and not message:
            message = "This plan fits inside your budget."
    else:
        over = bool(alert.get("over_budget"))

    return {
        "over_budget": bool(over),
        "message": message,
        "cheaper_alternatives": alternatives,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def normalize_itinerary(raw, trip):
    """Return a render-ready itinerary dict, whatever the model sent back."""
    raw = raw if isinstance(raw, dict) else {}
    destination = trip.get("destination") or "your destination"
    expected_days = max(1, int(trip.get("duration_days") or 1))
    start_date = _parse_date(trip.get("start_date"))

    summary_raw = raw.get("trip_summary") if isinstance(raw.get("trip_summary"), dict) else {}
    transport_raw = raw.get("transportation") if isinstance(raw.get("transportation"), dict) else {}
    stay_raw = raw.get("accommodation") if isinstance(raw.get("accommodation"), dict) else {}

    # --- days ------------------------------------------------------------
    days = []
    for index, item in enumerate(_dicts(raw.get("days"), limit=expected_days), start=1):
        days.append(_normalize_day(item, index, start_date, destination))
    while len(days) < expected_days:
        days.append(_placeholder_day(len(days) + 1, start_date, destination))

    transport_cost = as_number(transport_raw.get("estimated_cost"))
    stay_cost = as_number(stay_raw.get("estimated_cost"))
    budget = _normalize_budget(raw.get("budget_breakdown"), days, transport_cost, stay_cost)

    user_budget = as_number(trip.get("budget_amount")) or None
    total = budget["total"]

    itinerary = {
        "trip_summary": {
            "destination": as_text(summary_raw.get("destination"), destination, limit=160),
            "duration": as_text(summary_raw.get("duration"), str(expected_days) + " Days", limit=60),
            "estimated_budget": as_number(summary_raw.get("estimated_budget")) or total,
            "best_time": as_text(summary_raw.get("best_time"), "Year-round", limit=120),
            "overview": as_text(summary_raw.get("overview"), "", limit=1200),
            "start_location": as_text(trip.get("start_location"), limit=160),
            "travelers": int(trip.get("travelers") or 1),
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": as_text(trip.get("end_date")) or None,
            "travel_style": as_str_list(trip.get("travel_style")),
            "interests": as_str_list(trip.get("interests")),
        },
        "transportation": {
            "recommendation": as_text(transport_raw.get("recommendation"), "", limit=1200),
            "estimated_cost": transport_cost or budget["transport"],
            "tips": as_str_list(transport_raw.get("tips"), limit=8),
        },
        "accommodation": {
            "recommendation": as_text(stay_raw.get("recommendation"), "", limit=1200),
            "estimated_cost": stay_cost or budget["accommodation"],
            "suggestions": [
                {
                    "name": as_text(item.get("name"), "Recommended stay", limit=160),
                    "type": as_text(item.get("type"), "", limit=60),
                    "area": as_text(item.get("area"), "", limit=120),
                    "approx_cost_per_night": as_number(item.get("approx_cost_per_night")),
                }
                for item in _dicts(stay_raw.get("suggestions"), limit=6)
            ],
        },
        "days": days,
        "restaurants": [
            {
                "name": as_text(item.get("name"), "Local restaurant", limit=160),
                "cuisine": as_text(item.get("cuisine"), "", limit=80),
                "area": as_text(item.get("area"), "", limit=120),
                "price_range": as_text(item.get("price_range"), "", limit=40),
                "must_try": as_text(item.get("must_try"), "", limit=200),
            }
            for item in _dicts(raw.get("restaurants"), limit=12)
        ],
        "places_to_visit": [
            {
                "name": as_text(item.get("name"), "Point of interest", limit=160),
                "description": as_text(item.get("description"), "", limit=600),
                "best_time_to_visit": as_text(item.get("best_time_to_visit"), "", limit=120),
                "entry_fee": as_text(item.get("entry_fee"), "", limit=80),
                "map_query": as_text(item.get("map_query"), limit=200)
                or as_text(item.get("name"), destination, limit=200) + ", " + destination,
            }
            for item in _dicts(raw.get("places_to_visit"), limit=15)
        ],
        "budget_breakdown": budget,
        "travel_tips": as_str_list(raw.get("travel_tips"), limit=12),
        "packing_list": as_str_list(raw.get("packing_list"), limit=30),
        "budget_alert": _normalize_alert(raw.get("budget_alert"), total, user_budget),
        "budget_status": budget_status(total, user_budget),
    }
    return itinerary


def budget_status(total, user_budget):
    """Numbers the budget card renders: estimate vs. what the user can spend."""
    total = as_number(total)
    if not user_budget:
        return {
            "has_budget": False,
            "estimated": total,
            "user_budget": None,
            "remaining": None,
            "over_budget": False,
            "usage_percent": None,
        }
    user_budget = as_number(user_budget)
    remaining = round(user_budget - total, 2)
    percent = round((total / user_budget) * 100, 1) if user_budget else None
    return {
        "has_budget": True,
        "estimated": total,
        "user_budget": user_budget,
        "remaining": remaining,
        "over_budget": remaining < 0,
        "usage_percent": percent,
    }
