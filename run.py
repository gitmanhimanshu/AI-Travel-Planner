"""Entry point: `python run.py` starts the development server."""

from app import create_app
from config import env, env_int

app = create_app()

if __name__ == "__main__":
    app.run(
        host=env("HOST", "127.0.0.1"),
        port=env_int("PORT", 5000),
        debug=app.config.get("DEBUG", False),
    )
