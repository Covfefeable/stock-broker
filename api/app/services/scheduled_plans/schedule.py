from __future__ import annotations

import calendar
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.scheduled_plan import ScheduledPlan
from app.services.scheduled_plans.errors import ScheduledPlanError


PLAN_TIMEZONE = "Asia/Shanghai"


def calculate_next_run_at(plan: ScheduledPlan, *, after: datetime | None = None) -> datetime:
    base_utc = after or datetime.now(timezone.utc)
    tz = ZoneInfo(plan.timezone or PLAN_TIMEZONE)
    base_local = base_utc.astimezone(tz).replace(second=0, microsecond=0)
    frequency = plan.frequency_type

    if frequency == "hourly":
        minute = int(plan.minute_of_hour or 0)
        candidate = base_local.replace(minute=minute)
        if candidate <= base_local:
            candidate = candidate + timedelta(hours=1)
        return candidate.astimezone(timezone.utc)

    run_time = plan.time_of_day or time(hour=0, minute=0)
    if frequency == "daily":
        candidate = base_local.replace(hour=run_time.hour, minute=run_time.minute, second=0, microsecond=0)
        if candidate <= base_local:
            candidate = candidate + timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    if frequency == "weekly":
        weekdays = sorted({int(item) for item in (plan.weekdays or []) if 1 <= int(item) <= 7})
        if not weekdays:
            raise ScheduledPlanError("请选择每周执行的星期。")
        for day_offset in range(0, 8):
            date_value = (base_local + timedelta(days=day_offset)).date()
            if date_value.isoweekday() not in weekdays:
                continue
            candidate = datetime.combine(date_value, run_time, tzinfo=tz)
            if candidate > base_local:
                return candidate.astimezone(timezone.utc)
        raise ScheduledPlanError("无法计算下一次每周执行时间。")

    if frequency == "monthly":
        month_days = sorted({int(item) for item in (plan.month_days or []) if 1 <= int(item) <= 31})
        use_last_day = bool(plan.use_last_day)
        if not month_days and not use_last_day:
            raise ScheduledPlanError("请选择每月执行的日期。")
        current_month_start = base_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        for month_offset in range(0, 15):
            month_start = _shift_month(current_month_start, month_offset)
            last_day = calendar.monthrange(month_start.year, month_start.month)[1]
            days = [day for day in month_days if day <= last_day]
            if use_last_day:
                days.append(last_day)
            for day in sorted(set(days)):
                candidate = datetime.combine(month_start.replace(day=day).date(), run_time, tzinfo=tz)
                if candidate > base_local:
                    return candidate.astimezone(timezone.utc)
        raise ScheduledPlanError("无法计算下一次每月执行时间。")

    raise ScheduledPlanError("计划频率无效。")


def _shift_month(value: datetime, month_offset: int) -> datetime:
    month_index = value.month - 1 + month_offset
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return value.replace(year=year, month=month, day=1)
