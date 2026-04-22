from flask import Blueprint, current_app
from sqlalchemy import text

from app.extensions import db

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    return {
        "status": "ok",
        "service": "stock-broker-api",
        "environment": current_app.config["APP_ENV"],
    }


@health_bp.get("/ready")
def ready():
    db.session.execute(text("SELECT 1"))
    return {"status": "ready"}
