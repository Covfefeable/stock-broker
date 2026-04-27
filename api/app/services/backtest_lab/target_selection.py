from __future__ import annotations

from datetime import date
import json
import random

from sqlalchemy import and_, func

from app.extensions import db
from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.models.strategy import Strategy
from app.models.user import User
from app.services.ai_client import AIClientError, call_chat_completion_json
from app.services.backtest_lab.errors import BacktestLabError
from app.services.backtest_lab.evaluation import load_bars_for_range
from app.services.settings_service import get_or_create_settings


def select_cross_asset_targets(strategy: Strategy, rng: random.Random) -> list[dict]:
    targets = list_cross_asset_candidates(strategy)
    rng.shuffle(targets)
    return targets[:10]


def list_cross_asset_candidates(strategy: Strategy) -> list[dict]:
    country_code = strategy_country_code(strategy)
    if strategy.asset_type == "stock":
        latest_dates = (
            db.session.query(
                StockDailyBar.exchange_code.label("exchange_code"),
                StockDailyBar.ticker.label("ticker"),
                func.max(StockDailyBar.trade_date).label("latest_date"),
            )
            .group_by(StockDailyBar.exchange_code, StockDailyBar.ticker)
            .subquery()
        )
        rows = (
            db.session.query(Stock, latest_dates.c.latest_date)
            .join(latest_dates, and_(Stock.exchange_code == latest_dates.c.exchange_code, Stock.ticker == latest_dates.c.ticker))
            .filter(Stock.country_code == country_code)
            .order_by(Stock.exchange_code.asc(), Stock.ticker.asc())
            .all()
        )
        targets = [
            {
                "assetType": "stock",
                "assetIdentifier": f"{stock.exchange_code}:{stock.ticker}",
                "assetName": stock.name,
                "countryCode": stock.country_code,
                "latestDate": latest_date.isoformat() if latest_date else None,
            }
            for stock, latest_date in rows
            if f"{stock.exchange_code}:{stock.ticker}" != strategy.asset_identifier
        ]
    else:
        latest_dates = (
            db.session.query(
                IndexDailyBar.country_code.label("country_code"),
                IndexDailyBar.ticker.label("ticker"),
                func.max(IndexDailyBar.trade_date).label("latest_date"),
            )
            .group_by(IndexDailyBar.country_code, IndexDailyBar.ticker)
            .subquery()
        )
        rows = (
            db.session.query(IndexAsset, latest_dates.c.latest_date)
            .join(latest_dates, and_(IndexAsset.country_code == latest_dates.c.country_code, IndexAsset.ticker == latest_dates.c.ticker))
            .filter(IndexAsset.country_code == country_code)
            .order_by(IndexAsset.ticker.asc())
            .all()
        )
        targets = [
            {
                "assetType": "index",
                "assetIdentifier": item.ticker,
                "assetName": item.name,
                "countryCode": item.country_code,
                "latestDate": latest_date.isoformat() if latest_date else None,
            }
            for item, latest_date in rows
            if item.ticker != strategy.asset_identifier
        ]
    return targets


def list_evaluation_candidate_assets(user: User, strategy_id: int) -> dict:
    strategy = Strategy.query.filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not strategy:
        raise BacktestLabError("未找到对应的策略。")
    from app.services.backtest_lab.serialization import backtest_lab_strategy_to_dict

    targets = list_cross_asset_candidates(strategy)
    return {
        "strategy": backtest_lab_strategy_to_dict(strategy, None),
        "countryCode": strategy_country_code(strategy),
        "assetType": strategy.asset_type,
        "items": [candidate_to_option(item) for item in targets],
    }


def select_candidate_assets_by_ai(user: User, strategy_id: int) -> dict:
    strategy = Strategy.query.filter(Strategy.id == strategy_id, Strategy.user_id == user.id).first()
    if not strategy:
        raise BacktestLabError("未找到对应的策略。")
    candidates = list_cross_asset_candidates(strategy)
    if not candidates:
        raise BacktestLabError("当前策略所在国家/地区没有其他已同步日线数据的同类型标的，无法执行跨标的评估。")
    model_config = get_default_ai_model_config(user)
    if not model_config:
        raise BacktestLabError("当前没有可用 AI 模型，请先在系统设置中配置默认模型。")
    targets = select_similar_assets_with_ai(strategy, candidates, model_config)
    if not targets:
        raise BacktestLabError("AI 未返回有效标的，请手动选择评估标的。")
    return {
        "items": [candidate_to_option(item) for item in targets],
        "selection": {"mode": "ai", "message": "已由默认 AI 模型选取风格类似的标的。"},
    }


def select_cross_asset_targets_for_auto(user: User, strategy: Strategy) -> tuple[list[dict], dict]:
    candidates = list_cross_asset_candidates(strategy)
    if not candidates:
        raise BacktestLabError("当前策略所在国家/地区没有其他已同步日线数据的同类型标的，无法执行跨标的评估。")
    if len(candidates) <= 10:
        return candidates, {"mode": "all", "message": "候选标的不足 10 个，已使用全部可用标的。"}

    model_config = get_default_ai_model_config(user)
    if not model_config:
        rng = random.Random(f"strategy-evaluation:fallback:{strategy.id}:{len(candidates)}")
        fallback = candidates[:]
        rng.shuffle(fallback)
        return fallback[:10], {"mode": "random", "message": "没有可用 AI 模型，已随机抽取 10 个有数据的标的。"}

    try:
        selected = select_similar_assets_with_ai(strategy, candidates, model_config)
        if selected:
            return selected[:10], {"mode": "ai", "message": "已由默认 AI 模型选取风格类似的 10 个标的。"}
    except BacktestLabError as exc:
        rng = random.Random(f"strategy-evaluation:ai-fallback:{strategy.id}:{len(candidates)}")
        fallback = candidates[:]
        rng.shuffle(fallback)
        return fallback[:10], {"mode": "random", "message": f"AI 选取失败，已随机抽取 10 个标的：{exc}"}

    rng = random.Random(f"strategy-evaluation:empty-ai:{strategy.id}:{len(candidates)}")
    fallback = candidates[:]
    rng.shuffle(fallback)
    return fallback[:10], {"mode": "random", "message": "AI 未返回有效标的，已随机抽取 10 个标的。"}


def resolve_selected_cross_asset_targets(strategy: Strategy, selected_asset_identifiers: list[str]) -> list[dict]:
    normalized = [str(item).strip() for item in selected_asset_identifiers if str(item).strip()]
    if not normalized:
        raise BacktestLabError("请选择至少一个用于重新评估的股票或指数。")
    candidates = {item["assetIdentifier"]: item for item in list_cross_asset_candidates(strategy)}
    missing = [item for item in normalized if item not in candidates]
    if missing:
        raise BacktestLabError("所选标的不存在或没有历史日线数据，请重新选择。")
    return [candidates[item] for item in normalized]


def candidate_to_option(item: dict) -> dict:
    latest_date = item.get("latestDate")
    return {
        "label": f"{item.get('assetIdentifier')} - {item.get('assetName') or '-'}"
        + (f"（同步至 {latest_date}）" if latest_date else ""),
        "value": item.get("assetIdentifier"),
        "name": item.get("assetName"),
        "assetIdentifier": item.get("assetIdentifier"),
        "latestDate": latest_date,
    }


def get_default_ai_model_config(user: User) -> dict | None:
    settings = get_or_create_settings(user)
    models = settings.ai_models or []
    if not models:
        return None
    first = models[0]
    model_config = {
        "name": str(first.get("name", "")).strip(),
        "model": str(first.get("model", "")).strip(),
        "baseUrl": str(first.get("baseUrl", "")).strip(),
        "apiKey": str(first.get("apiKey", "")).strip(),
    }
    if not model_config["model"] or not model_config["baseUrl"] or not model_config["apiKey"]:
        return None
    return model_config


def select_similar_assets_with_ai(strategy: Strategy, candidates: list[dict], model_config: dict) -> list[dict]:
    candidate_payload = [
        {
            "assetIdentifier": item["assetIdentifier"],
            "assetName": item.get("assetName"),
            "latestDate": item.get("latestDate"),
        }
        for item in candidates[:500]
    ]
    prompt = (
        "你是量化研究助理。请从候选标的里选择最多 10 个与原始策略标的风格尽可能类似、适合做跨标的评估的标的。"
        "只能从候选列表中选择，不要编造。返回 JSON：{\"assetIdentifiers\":[\"...\"]}。\n"
        f"原始标的：类型={strategy.asset_type}，代码={strategy.asset_identifier}，名称={strategy.asset_name or '-'}，"
        f"国家/地区={strategy.country_region}。\n"
        f"候选标的：{json.dumps(candidate_payload, ensure_ascii=False)}"
    )
    try:
        parsed = call_chat_completion_json(
            model_config,
            [
                {"role": "system", "content": "你只能返回合法 JSON，不要输出 markdown。"},
                {"role": "user", "content": prompt},
            ],
            timeout=120,
            temperature=0.2,
        )
    except AIClientError as exc:
        raise BacktestLabError(str(exc)) from exc

    identifiers = parsed.get("assetIdentifiers")
    if not isinstance(identifiers, list):
        return []
    candidate_map = {item["assetIdentifier"]: item for item in candidates}
    selected: list[dict] = []
    for identifier in identifiers:
        key = str(identifier).strip()
        if key in candidate_map and key not in {item["assetIdentifier"] for item in selected}:
            selected.append(candidate_map[key])
        if len(selected) >= 10:
            break
    return selected


def select_time_ranges(strategy: Strategy, rng: random.Random) -> list[dict]:
    bars = load_bars_for_range(strategy.asset_type or "", strategy.asset_identifier or "", strategy_country_code(strategy), strategy.strategy_config or {})
    if not bars:
        return []
    start_year = bars[0]["date"].year
    end_year = bars[-1]["date"].year
    recent_years = list(range(max(start_year, end_year - 4), end_year + 1))
    ranges: list[dict] = [
        {"label": f"{year} 年", "startDate": f"{year}-01-01", "endDate": f"{year}-12-31"}
        for year in recent_years
    ]

    for window, count in ((3, 3), (5, 2)):
        latest_start = end_year - window + 1
        earliest_start = max(start_year, latest_start - count + 1)
        for year in range(earliest_start, latest_start + 1):
            ranges.append(
                {
                    "label": f"{year}-{year + window - 1} 年",
                    "startDate": f"{year}-01-01",
                    "endDate": f"{year + window - 1}-12-31",
                }
            )
    return ranges


def strategy_country_code(strategy: Strategy) -> str:
    return str(strategy.country_region or "").split("-", 1)[0].strip().upper()
