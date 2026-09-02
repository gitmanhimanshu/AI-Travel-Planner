"""Destination catalogue and weather endpoints."""

from flask import Blueprint

from app.services.destinations_data import all_destinations, get_destination
from app.services.weather_service import get_weather
from app.utils import ApiError, json_ok

destinations_bp = Blueprint("destinations", __name__)


@destinations_bp.get("/destinations")
def list_destinations():
    return json_ok({"destinations": all_destinations()})


@destinations_bp.get("/destinations/<slug>")
def destination_detail(slug):
    destination = get_destination(slug)
    if not destination:
        raise ApiError("We do not have that destination yet.", 404)
    return json_ok({"destination": destination})


@destinations_bp.get("/weather/<path:destination>")
def weather(destination):
    # Never fatal: an unavailable service returns available=false, not an error.
    return json_ok({"weather": get_weather(destination)})
