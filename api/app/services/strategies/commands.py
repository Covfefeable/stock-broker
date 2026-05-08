from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.extensions import db
from app.models.strategy import Strategy
from app.models.strategy_evaluation import StrategyEvaluation
from app.models.user import User
from app.services.strategies.dsl import _validate_strategy_config
from app.services.strategies.errors import StrategyError
from app.services.strategies.queries import _normalize_country_region, get_strategy


def _parse_optional_metric(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception as exc:  # noqa: BLE001
        raise StrategyError("策略指标格式无效。") from exc


def favorite_strategy(user: User, strategy_id: int) -> Strategy:
    strategy = get_strategy(user, strategy_id)
    if strategy.status == "已收藏":
        strategy.status = "草稿"
    else:
        strategy.status = "已收藏"
    strategy.archived_at = None
    strategy.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return strategy


def archive_strategy(user: User, strategy_id: int) -> Strategy:
    return favorite_strategy(user, strategy_id)


def delete_strategy(user: User, strategy_id: int) -> None:
    strategy = get_strategy(user, strategy_id)
    if strategy.status == "已收藏":
        raise StrategyError("已收藏的策略禁止删除，请先取消收藏。")
    StrategyEvaluation.query.filter_by(user_id=user.id, strategy_id=strategy.id).delete(synchronize_session=False)
    db.session.delete(strategy)
    db.session.commit()


def update_strategy(user: User, strategy_id: int, payload: dict) -> Strategy:
    strategy = get_strategy(user, strategy_id)
    _apply_strategy_payload(strategy, payload)
    strategy.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return strategy


def create_strategy(user: User, payload: dict) -> Strategy:
    strategy = Strategy(user_id=user.id)
    _apply_strategy_payload(strategy, payload, is_create=True)
    strategy.status = strategy.status or "草稿"
    db.session.add(strategy)
    db.session.commit()
    return strategy


def _apply_strategy_payload(strategy: Strategy, payload: dict, *, is_create: bool = False) -> None:
    name = str(payload.get("name", "")).strip()
    strategy_type = str(payload.get("type", "")).strip()
    source = str(payload.get("source", "")).strip()
    country_region = _normalize_country_region(str(payload.get("countryRegion", "")).strip())
    asset_type = str(payload.get("assetType", "")).strip()
    asset_identifier = str(payload.get("assetIdentifier", "")).strip()
    asset_name = str(payload.get("assetName", "")).strip()
    strategy_config = payload.get("strategyConfig") or {}
    annual_return = _parse_optional_metric(payload.get("annualReturn"))
    max_drawdown = _parse_optional_metric(payload.get("maxDrawdown"))

    if not name:
        raise StrategyError("请输入策略名称。")
    if not strategy_type:
        raise StrategyError("请选择策略类型。")
    if source not in {"人工创建", "计划任务"}:
        raise StrategyError("请选择有效的来源。")
    if not country_region:
        raise StrategyError("请选择国家/地区。")
    if asset_type not in {"stock", "index"}:
        raise StrategyError("请选择股票或指数。")
    if not asset_identifier:
        raise StrategyError("请选择具体标的。")

    strategy.name = name
    strategy.type = strategy_type
    strategy.source = source
    strategy.country_region = country_region
    strategy.asset_type = asset_type
    strategy.asset_identifier = asset_identifier
    strategy.asset_name = asset_name or None
    if not isinstance(strategy_config, dict):
        raise StrategyError("规则配置格式无效。")
    _validate_strategy_config(strategy_config)

    strategy.strategy_config = strategy_config
    strategy.annual_return = annual_return
    strategy.max_drawdown = max_drawdown
    if is_create and not strategy.status:
        strategy.status = "草稿"
