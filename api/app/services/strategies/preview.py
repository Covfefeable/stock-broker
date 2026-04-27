from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.extensions import db
from app.models.user import User
from app.services.performance_score import calculate_performance_score
from app.services.settings_service import get_performance_score_weights
from app.services.strategies.assets import _load_asset_bars
from app.services.strategies.dsl import _validate_strategy_config
from app.services.strategies.engine import _run_strategy_backtest
from app.services.strategies.errors import StrategyError
from app.services.strategies.queries import get_strategy


def _parse_optional_metric(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception as exc:  # noqa: BLE001
        raise StrategyError("收益预览结果格式无效。") from exc


def preview_strategy(user: User, payload: dict) -> dict:
    asset_type = str(payload.get("assetType", "")).strip()
    asset_identifier = str(payload.get("assetIdentifier", "")).strip()
    country_code = str(payload.get("countryCode", "")).strip().upper()
    strategy_config = payload.get("strategyConfig") or {}
    strategy_id = payload.get("strategyId")

    if asset_type not in {"stock", "index"}:
        raise StrategyError("请选择股票或指数。")
    if not asset_identifier:
        raise StrategyError("请选择具体标的。")
    if asset_type == "index" and not country_code:
        raise StrategyError("请选择国家/地区。")
    if not isinstance(strategy_config, dict):
        raise StrategyError("规则配置格式无效。")
    _validate_strategy_config(strategy_config)

    bars = _load_asset_bars(asset_type, asset_identifier, country_code, strategy_config)
    if not bars:
        raise StrategyError("当前标的没有可用于预览收益的历史日线数据。")

    preview = _run_strategy_backtest(bars, strategy_config)

    if strategy_id:
        strategy = get_strategy(user, int(strategy_id))
        strategy.annual_return = Decimal(str(preview["annualReturn"]))
        strategy.max_drawdown = Decimal(str(preview["maxDrawdown"]))
        strategy.updated_at = datetime.now(timezone.utc)
        db.session.commit()

    return preview
