"""SQLAlchemy models: User, Trip and Favorite."""

import json
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    trips = db.relationship(
        "Trip", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    favorites = db.relationship(
        "Favorite", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<User {self.email}>"


class Trip(db.Model):
    __tablename__ = "trips"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    destination = db.Column(db.String(160), nullable=False)
    start_location = db.Column(db.String(160), nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    duration_days = db.Column(db.Integer, nullable=False, default=1)
    travelers = db.Column(db.Integer, nullable=False, default=1)

    budget_level = db.Column(db.String(30), nullable=True)      # budget | moderate | luxury
    budget_amount = db.Column(db.Float, nullable=True)          # optional exact amount
    travel_style = db.Column(db.Text, nullable=True)            # JSON list
    interests = db.Column(db.Text, nullable=True)               # JSON list
    transportation = db.Column(db.String(60), nullable=True)
    accommodation = db.Column(db.String(60), nullable=True)
    notes = db.Column(db.Text, nullable=True)                   # additional requirements

    itinerary_json = db.Column(db.Text, nullable=False)         # AI response as JSON text
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    user = db.relationship("User", back_populates="trips")
    favorites = db.relationship(
        "Favorite", back_populates="trip", cascade="all, delete-orphan", lazy="selectin"
    )

    # -- JSON column helpers -------------------------------------------------
    @property
    def itinerary(self):
        try:
            return json.loads(self.itinerary_json or "{}")
        except (TypeError, ValueError):
            return {}

    @itinerary.setter
    def itinerary(self, value):
        self.itinerary_json = json.dumps(value, ensure_ascii=False)

    @property
    def style_list(self):
        return _load_list(self.travel_style)

    @property
    def interest_list(self):
        return _load_list(self.interests)

    def is_favorited(self):
        return bool(self.favorites)

    def to_dict(self, include_itinerary=True):
        data = {
            "id": self.id,
            "destination": self.destination,
            "start_location": self.start_location,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "duration_days": self.duration_days,
            "travelers": self.travelers,
            "budget_level": self.budget_level,
            "budget_amount": self.budget_amount,
            "travel_style": self.style_list,
            "interests": self.interest_list,
            "transportation": self.transportation,
            "accommodation": self.accommodation,
            "notes": self.notes,
            "is_favorite": self.is_favorited(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_itinerary:
            data["itinerary"] = self.itinerary
        return data

    def __repr__(self):
        return f"<Trip {self.id} {self.destination}>"


class Favorite(db.Model):
    __tablename__ = "favorites"
    __table_args__ = (db.UniqueConstraint("user_id", "trip_id", name="uq_favorite_user_trip"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trip_id = db.Column(
        db.Integer, db.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User", back_populates="favorites")
    trip = db.relationship("Trip", back_populates="favorites")

    def __repr__(self):
        return f"<Favorite user={self.user_id} trip={self.trip_id}>"


def _load_list(raw):
    """Decode a JSON list column, tolerating legacy comma-separated values."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else [str(value)]
    except (TypeError, ValueError):
        return [part.strip() for part in str(raw).split(",") if part.strip()]
