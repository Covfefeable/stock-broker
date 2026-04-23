from flask import Blueprint, g, request

from app.routes.auth import auth_required
from app.services.data_center_service import (
    DataSyncError,
    SYNC_ITEM_EXCHANGE_LIST,
    SYNC_ITEM_COUNTRY_LIST,
    list_recent_event_logs,
    sync_exchange_list,
    sync_country_list,
    sync_item_label,
)

data_center_bp = Blueprint("data_center", __name__)


@data_center_bp.get("/data-center/event-logs")
@auth_required
def event_logs():
    return {"items": list_recent_event_logs(limit=20)}


@data_center_bp.post("/data-center/sync")
@auth_required
def sync_data():
    payload = request.get_json(silent=True) or {}
    sync_item = str(payload.get("syncItem") or "").strip()

    if sync_item not in {SYNC_ITEM_COUNTRY_LIST, SYNC_ITEM_EXCHANGE_LIST}:
        return {
            "message": f"暂不支持同步项：{sync_item_label(sync_item or 'unknown')}",
        }, 400

    try:
        if sync_item == SYNC_ITEM_COUNTRY_LIST:
            result = sync_country_list(g.current_user)
        else:
            result = sync_exchange_list(g.current_user)
    except DataSyncError as exc:
        return {"message": str(exc)}, 400

    return {
        "message": f"{result['syncItemLabel']}同步成功",
        "result": result,
    }
