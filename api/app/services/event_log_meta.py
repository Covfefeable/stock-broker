from app.models.event_log import EventLog

EVENT_CATEGORY_SYNC = "sync"
EVENT_CATEGORY_AGENT = "agent"

SYNC_ITEM_META = {
    "country_list": {"label": "国家/地区清单", "eventName": "sync_country_list"},
    "exchange_list": {"label": "交易所清单", "eventName": "sync_exchange_list"},
    "stock_list": {"label": "股票清单", "eventName": "sync_stock_list"},
    "index_list": {"label": "指数清单", "eventName": "sync_index_list"},
    "trading_calendar": {"label": "交易日历", "eventName": "sync_trading_calendar"},
    "stock_daily_history": {"label": "股票历史日线", "eventName": "sync_stock_daily_history"},
    "index_daily_history": {"label": "指数历史日线", "eventName": "sync_index_daily_history"},
}

EVENT_TYPE_META = {
    "data_sync": {"label": "数据同步", "category": EVENT_CATEGORY_SYNC},
    "data_sync_batch": {"label": "批量数据同步", "category": EVENT_CATEGORY_SYNC},
    "agent": {"label": "AI Agent", "category": EVENT_CATEGORY_AGENT},
    "backtest": {"label": "回测评估", "category": EVENT_CATEGORY_AGENT},
}

EVENT_NAME_META = {
    "enqueue_sync_task": {"label": "同步任务已提交", "category": EVENT_CATEGORY_SYNC},
    "enqueue_batch_sync_stock_daily_history": {"label": "批量同步股票日线已提交", "category": EVENT_CATEGORY_SYNC},
    "enqueue_batch_sync_stock_and_index_daily_history": {
        "label": "批量同步股票/指数日线已提交",
        "category": EVENT_CATEGORY_SYNC,
    },
    "batch_sync_stock_daily_history": {"label": "批量同步股票日线", "category": EVENT_CATEGORY_SYNC},
    "batch_sync_stock_and_index_daily_history": {
        "label": "批量同步股票/指数日线",
        "category": EVENT_CATEGORY_SYNC,
    },
    "agent_task_enqueued": {"label": "Agent 任务已入队", "category": EVENT_CATEGORY_AGENT},
    "agent_task_running": {"label": "Agent 任务开始执行", "category": EVENT_CATEGORY_AGENT},
    "agent_iteration": {"label": "Agent 迭代完成", "category": EVENT_CATEGORY_AGENT},
    "agent_task_stop_requested": {"label": "Agent 任务停止中", "category": EVENT_CATEGORY_AGENT},
    "agent_task_stopped": {"label": "Agent 任务已停止", "category": EVENT_CATEGORY_AGENT},
    "agent_task_finished": {"label": "Agent 任务完成", "category": EVENT_CATEGORY_AGENT},
    "agent_task_failed": {"label": "Agent 任务执行失败", "category": EVENT_CATEGORY_AGENT},
    "strategy_evaluation_enqueued": {"label": "策略评估已入队", "category": EVENT_CATEGORY_AGENT},
    "strategy_evaluation_running": {"label": "策略评估开始执行", "category": EVENT_CATEGORY_AGENT},
    "strategy_evaluation_finished": {"label": "策略评估完成", "category": EVENT_CATEGORY_AGENT},
    "strategy_evaluation_failed": {"label": "策略评估失败", "category": EVENT_CATEGORY_AGENT},
    **{
        meta["eventName"]: {"label": f"{meta['label']}同步", "category": EVENT_CATEGORY_SYNC}
        for meta in SYNC_ITEM_META.values()
    },
}


def sync_item_label(sync_item: str | None) -> str:
    if not sync_item:
        return "-"
    return str(SYNC_ITEM_META.get(sync_item, {}).get("label") or sync_item)


def sync_event_name(sync_item: str) -> str:
    return str(SYNC_ITEM_META.get(sync_item, {}).get("eventName") or sync_item)


def event_type_label(event_type: str) -> str:
    return str(EVENT_TYPE_META.get(event_type, {}).get("label") or event_type)


def event_name_label(event_name: str) -> str:
    return str(EVENT_NAME_META.get(event_name, {}).get("label") or event_name)


def event_types_for_category(category: str) -> list[str]:
    return [
        event_type
        for event_type, meta in EVENT_TYPE_META.items()
        if meta.get("category") == category
    ]


def event_log_to_dict(row: EventLog) -> dict:
    payload = row.to_dict()
    event_type_meta = EVENT_TYPE_META.get(row.event_type, {})
    event_name_meta = EVENT_NAME_META.get(row.event_name, {})
    payload["eventCategory"] = event_name_meta.get("category") or event_type_meta.get("category") or row.event_type
    payload["eventTypeLabel"] = event_type_label(row.event_type)
    payload["eventNameLabel"] = event_name_label(row.event_name)
    payload["targetLabel"] = sync_item_label(row.target) if row.target else None
    return payload
