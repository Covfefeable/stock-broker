import json
from datetime import datetime, timedelta, timezone
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


from app.extensions import db
from app.models.data_source_status import DataSourceStatus

from app.services.data_center.constants import *  # noqa: F403
from app.services.data_center.canghai_client import build_canghai_url, canghai_stock_daily_url
from app.services.data_center.errors import DataSyncError
from app.services.data_center.events import log_event
from app.services.data_center.tokens import get_any_canghai_token


def get_data_source_status_snapshot() -> dict:
    record = DataSourceStatus.query.filter_by(source_key=CANGHAI_SOURCE_KEY).first()
    if not record:
        return {
            "sourceKey": CANGHAI_SOURCE_KEY,
            "sourceName": CANGHAI_SOURCE_NAME,
            "status": "unknown",
            "latencyMs": None,
            "checkedAt": None,
            "httpStatus": None,
            "message": "尚未检测",
        }
    return record.to_dict()


def check_canghai_data_source_status(*, task_id: str | None = None) -> dict:
    started_at = datetime.now(timezone.utc)
    started_perf = perf_counter()
    status = "abnormal"
    http_status: int | None = None
    message = "状态检测失败"

    try:
        token = get_any_canghai_token()
        beijing_today = datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Shanghai")).date()
        check_date = beijing_today - timedelta(days=1)
        request_url = build_canghai_url(
            canghai_stock_daily_url("XNAS"),
            token,
            extra_params={
                "ticker": "TSLA",
                "start_date": check_date.isoformat(),
                "end_date": check_date.isoformat(),
            },
        )
        request = Request(request_url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=20) as response:
            http_status = response.status
            payload = json.loads(response.read().decode("utf-8"))
            status = (
                "normal"
                if http_status == 200 and int(payload.get("code") or 0) == 200
                else "abnormal"
            )
            message = str(payload.get("msg") or "Status check finished")
    except HTTPError as exc:
        http_status = exc.code
        message = f"HTTP {exc.code}"
    except URLError as exc:
        message = f"网络异常：{exc.reason}"
    except DataSyncError as exc:
        message = str(exc)
    except Exception as exc:
        message = f"检测异常：{exc}"

    checked_at = datetime.now(timezone.utc)
    latency_ms = int((perf_counter() - started_perf) * 1000)
    record = DataSourceStatus.query.filter_by(source_key=CANGHAI_SOURCE_KEY).first()
    if not record:
        record = DataSourceStatus(source_key=CANGHAI_SOURCE_KEY, source_name=CANGHAI_SOURCE_NAME)
        db.session.add(record)

    record.status = status
    record.latency_ms = latency_ms
    record.checked_at = checked_at
    record.http_status = http_status
    record.message = message
    db.session.commit()

    log_event(
        user=None,
        task_id=task_id,
        show_in_ui=False,
        event_type="data_source_check",
        event_name="check_canghai_data_source_status",
        source="canghai",
        target=CANGHAI_SOURCE_KEY,
        status="success" if status == "normal" else "failed",
        level="info" if status == "normal" else "warning",
        message=f"{CANGHAI_SOURCE_NAME}状态检测完成：{message}",
        http_status=http_status,
        started_at=started_at,
        finished_at=checked_at,
        duration_ms=latency_ms,
    )

    return record.to_dict()
