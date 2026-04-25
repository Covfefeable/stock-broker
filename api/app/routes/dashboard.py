from flask import Blueprint, g

from app.routes.auth import auth_required
from app.services.dashboard_service import get_dashboard_overview

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/dashboard/overview")
@auth_required
def dashboard_overview():
    return get_dashboard_overview(g.current_user)
