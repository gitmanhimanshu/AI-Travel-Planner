"""Flask extension instances, kept separate to avoid circular imports."""

from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
cors = CORS()
