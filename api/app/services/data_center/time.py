from datetime import date, datetime
from zoneinfo import ZoneInfo


def beijing_today() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()
