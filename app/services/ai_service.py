"""Prompt construction and AI-facing use cases.

This module owns *what* we ask the model; `ai_provider.py` owns *how* the call
is made. Every JSON call is constrained by an explicit JSON schema, and the
result is normalised by `itinerary_service` before it reaches a route.
"""

import json
import logging

from app.services.ai_provider import AIProviderError, get_provider
from app.services.itinerary_service import normalize_itinerary

log = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 12


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
def _obj(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": required if required is not None else list(properties),
        "additionalProperties": False,
    }


ITINERARY_SCHEMA = _obj(
    {
        "trip_summary": _obj(
            {
                "destination": {"type": "string"},
                "duration": {"type": "string"},
                "estimated_budget": {"type": "number"},
                "best_time": {"type": "string"},
                "overview": {"type": "string"},
            }
        ),
        "transportation": _obj(
            {
                "recommendation": {"type": "string"},
                "estimated_cost": {"type": "number"},
                "tips": {"type": "array", "items": {"type": "string"}},
            }
        ),
        "accommodation": _obj(
            {
                "recommendation": {"type": "string"},
                "estimated_cost": {"type": "number"},
                "suggestions": {
                    "type": "array",
                    "items": _obj(
                        {
                            "name": {"type": "string"},
                            "type": {"type": "string"},
                            "area": {"type": "string"},
                            "approx_cost_per_night": {"type": "number"},
                        }
                    ),
                },
            }
        ),
        "days": {
            "type": "array",
            "items": _obj(
                {
                    "day": {"type": "integer"},
                    "title": {"type": "string"},
                    "location": {"type": "string"},
                    "activities": {
                        "type": "array",
                        "items": _obj(
                            {
                                "period": {
                                    "type": "string",
                                    "enum": ["morning", "afternoon", "evening"],
                                },
                                "time": {"type": "string"},
                                "activity": {"type": "string"},
                                "description": {"type": "string"},
                                "estimated_cost": {"type": "number"},
                            }
                        ),
                    },
                    "food_recommendations": {
                        "type": "array",
                        "items": _obj(
                            {
                                "name": {"type": "string"},
                                "dish": {"type": "string"},
                                "approx_cost": {"type": "number"},
                            }
                        ),
                    },
                    "estimated_cost": {"type": "number"},
                }
            ),
        },
        "restaurants": {
            "type": "array",
            "items": _obj(
                {
                    "name": {"type": "string"},
                    "cuisine": {"type": "string"},
                    "area": {"type": "string"},
                    "price_range": {"type": "string"},
                    "must_try": {"type": "string"},
                }
            ),
        },
        "places_to_visit": {
            "type": "array",
            "items": _obj(
                {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "best_time_to_visit": {"type": "string"},
                    "entry_fee": {"type": "string"},
                    "map_query": {"type": "string"},
                }
            ),
        },
        "budget_breakdown": _obj(
            {
                "transport": {"type": "number"},
                "accommodation": {"type": "number"},
                "food": {"type": "number"},
                "activities": {"type": "number"},
                "miscellaneous": {"type": "number"},
                "total": {"type": "number"},
            }
        ),
        "travel_tips": {"type": "array", "items": {"type": "string"}},
        "packing_list": {"type": "array", "items": {"type": "string"}},
        "budget_alert": _obj(
            {
                "over_budget": {"type": "boolean"},
                "message": {"type": "string"},
                "cheaper_alternatives": {"type": "array", "items": {"type": "string"}},
            }
        ),
    }
)

PACKING_SCHEMA = _obj(
    {
        "packing_list": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    }
)

BUDGET_SCHEMA = _obj(
    {
        "optimized_total": {"type": "number"},
        "savings": {"type": "number"},
        "suggestions": {
            "type": "array",
            "items": _obj(
                {
                    "area": {"type": "string"},
                    "change": {"type": "string"},
                    "saving": {"type": "number"},
                }
            ),
        },
        "summary": {"type": "string"},
    }
)


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
PLANNER_SYSTEM = (
    "You are an expert travel planner with deep, current knowledge of Indian and "
    "international destinations.\n"
    "Rules you always follow:\n"
    "- Respect the traveller's budget. Costs are in Indian Rupees (INR) and cover the "
    "whole group unless a field says otherwise.\n"
    "- Build realistic day-wise schedules: 3 to 5 activities per day, never more than "
    "one long-distance transfer in a day.\n"
    "- Never place two locations in the same day if they are more than about two hours "
    "apart by road, unless that day is explicitly a travel day.\n"
    "- Account for arrival and departure days: the first and last day carry less.\n"
    "- Match the traveller's stated interests and travel style; ignore attractions that "
    "clearly do not fit them.\n"
    "- Give an honest estimated cost for every activity, meal, stay and transfer.\n"
    "- If the plan cannot fit the stated budget, set budget_alert.over_budget to true, "
    "explain why, and list concrete cheaper alternatives.\n"
    "- Use real, well-known place names. Do not invent hotels or restaurants that are "
    "unlikely to exist; describe the type and area instead when unsure.\n"
    "Return only data that fits the requested JSON schema."
)

CHAT_SYSTEM = (
    "You are a friendly, concise travel assistant inside a trip-planning app. "
    "Answer in 2-5 short sentences or a compact bullet list. Use the traveller's "
    "itinerary context when it is relevant, admit when you are unsure, and give "
    "practical, specific advice with rough INR costs where useful. "
    "Plain text only - no markdown headings or code blocks."
)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------
def _line(label, value):
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(item) for item in value)
    return "- " + label + ": " + str(value) + "\n"


def build_itinerary_prompt(trip):
    """Turn the validated planner form into a single, explicit user prompt."""
    days = trip.get("duration_days") or 1
    budget_amount = trip.get("budget_amount")

    prompt = "Plan a trip with these requirements.\n\n"
    prompt += _line("Destination", trip.get("destination"))
    prompt += _line("Starting city", trip.get("start_location"))
    prompt += _line("Start date", trip.get("start_date"))
    prompt += _line("End date", trip.get("end_date"))
    prompt += _line("Trip duration", str(days) + " days")
    prompt += _line("Number of travellers", trip.get("travelers"))
    prompt += _line("Budget level", trip.get("budget_level"))
    if budget_amount:
        prompt += _line("Total budget for the group (INR)", int(budget_amount))
    prompt += _line("Travel style", trip.get("travel_style"))
    prompt += _line("Interests", trip.get("interests"))
    prompt += _line("Preferred transportation", trip.get("transportation"))
    prompt += _line("Accommodation preference", trip.get("accommodation"))
    prompt += _line("Additional requirements", trip.get("notes"))

    prompt += (
        "\nProduce exactly " + str(days) + " day objects, numbered 1 to " + str(days) + ", "
        "each with morning, afternoon and evening activities.\n"
    )
    if budget_amount:
        prompt += (
            "The budget_breakdown total must be a realistic estimate. If it exceeds "
            + str(int(budget_amount))
            + " INR, set budget_alert.over_budget to true and list cheaper alternatives.\n"
        )
    else:
        prompt += (
            "No exact budget was given - estimate sensible costs for the chosen budget "
            "level and set budget_alert.over_budget to false.\n"
        )
    prompt += (
        "Include at least 4 restaurants, at least 5 places_to_visit with a map_query "
        "usable in a map search, 5 travel tips and a packing list suited to the season."
    )
    return prompt


def _trip_context_text(trip, itinerary=None, limit=4000):
    """Compact context block reused by chat, packing and budget calls."""
    context = "Traveller's trip:\n"
    context += _line("Destination", trip.get("destination"))
    context += _line("From", trip.get("start_location"))
    context += _line("Dates", str(trip.get("start_date") or "?") + " to " + str(trip.get("end_date") or "?"))
    context += _line("Duration (days)", trip.get("duration_days"))
    context += _line("Travellers", trip.get("travelers"))
    context += _line("Budget (INR)", trip.get("budget_amount"))
    context += _line("Style", trip.get("travel_style"))
    context += _line("Interests", trip.get("interests"))

    if itinerary:
        summary = {
            "trip_summary": itinerary.get("trip_summary"),
            "budget_breakdown": itinerary.get("budget_breakdown"),
            "days": [
                {
                    "day": day.get("day"),
                    "title": day.get("title"),
                    "activities": [item.get("activity") for item in day.get("activities", [])],
                    "estimated_cost": day.get("estimated_cost"),
                }
                for day in itinerary.get("days", [])
            ],
        }
        context += "\nCurrent itinerary (condensed JSON):\n"
        context += json.dumps(summary, ensure_ascii=False)[:limit]
    return context


# ---------------------------------------------------------------------------
# Use cases
# ---------------------------------------------------------------------------
def generate_itinerary(trip):
    """Generate and normalise a full itinerary for a validated trip dict."""
    provider = get_provider()
    raw = provider.complete_json(
        system=PLANNER_SYSTEM,
        prompt=build_itinerary_prompt(trip),
        schema=ITINERARY_SCHEMA,
        context=dict(trip, kind="itinerary"),
    )
    if not isinstance(raw, dict):
        raise AIProviderError("The AI response had an unexpected shape.")
    return normalize_itinerary(raw, trip)


def chat(message, history=None, trip=None, itinerary=None):
    """Answer a travel-assistant question, optionally grounded in a trip."""
    provider = get_provider()
    system = CHAT_SYSTEM
    if trip:
        system = CHAT_SYSTEM + "\n\n" + _trip_context_text(trip, itinerary)

    messages = []
    for entry in (history or [])[-MAX_HISTORY_MESSAGES:]:
        role = entry.get("role")
        content = str(entry.get("content") or "").strip()[:2000]
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    # The API requires the conversation to start with a user turn.
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    messages.append({"role": "user", "content": message})

    reply = provider.complete_text(
        system=system, messages=messages, context={"kind": "chat"}, max_tokens=1200
    )
    return reply.strip()


def packing_list(trip, itinerary=None):
    """Generate a packing list tailored to destination, season and activities."""
    provider = get_provider()
    prompt = (
        "Create a practical packing list for this trip. Group nothing - return a flat "
        "list of 12-20 specific items, each short enough to read at a glance. "
        "Consider the season at the destination, the trip length, the planned "
        "activities and the number of travellers.\n\n"
        + _trip_context_text(trip, itinerary, limit=1500)
    )
    data = provider.complete_json(
        system=PLANNER_SYSTEM,
        prompt=prompt,
        schema=PACKING_SCHEMA,
        context=dict(trip, kind="packing"),
        max_tokens=4000,
    )
    items = [str(item).strip() for item in (data.get("packing_list") or []) if str(item).strip()]
    return {"packing_list": items[:30], "notes": str(data.get("notes") or "")}


def optimize_budget(trip, itinerary, target_budget):
    """Suggest concrete ways to bring a trip under the traveller's budget."""
    provider = get_provider()
    prompt = (
        "This itinerary costs more than the traveller can spend. Suggest 3-6 specific, "
        "realistic changes that reduce the total without ruining the trip. Keep the "
        "destination and the number of days the same. Target total: "
        + str(int(target_budget))
        + " INR.\n\n"
        + _trip_context_text(trip, itinerary, limit=3000)
    )
    data = provider.complete_json(
        system=PLANNER_SYSTEM,
        prompt=prompt,
        schema=BUDGET_SCHEMA,
        context=dict(trip, kind="budget", target_budget=target_budget),
        max_tokens=6000,
    )
    suggestions = []
    for item in (data.get("suggestions") or [])[:8]:
        if not isinstance(item, dict):
            continue
        suggestions.append(
            {
                "area": str(item.get("area") or "General"),
                "change": str(item.get("change") or ""),
                "saving": _number(item.get("saving")),
            }
        )
    return {
        "optimized_total": _number(data.get("optimized_total")),
        "savings": _number(data.get("savings")),
        "suggestions": suggestions,
        "summary": str(data.get("summary") or ""),
    }


def _number(value, default=0):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return default
