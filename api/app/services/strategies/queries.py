from __future__ import annotations

from datetime import date

from sqlalchemy import asc, desc, func, or_

from app.extensions import db
from app.models.country import Country
from app.models.exchange import Exchange
from app.models.index_asset import IndexAsset
from app.models.index_daily_bar import IndexDailyBar
from app.models.stock import Stock
from app.models.stock_daily_bar import StockDailyBar
from app.models.strategy import Strategy
from app.models.strategy_evaluation import StrategyEvaluation
from app.models.user import User
from app.services.strategies.errors import StrategyError


def list_strategy_asset_options(country_code: str, asset_type: str) -> dict:
    normalized_country_code = country_code.strip().upper()
    if not normalized_country_code:
        raise StrategyError("请先选择国家/地区。")
    if asset_type not in {"stock", "index"}:
        raise StrategyError("请选择股票或指数。")

    if asset_type == "stock":
        exchanges = (
            Exchange.query.filter(Exchange.country_code == normalized_country_code)
            .order_by(Exchange.exchange_name.asc())
            .all()
        )
        if not exchanges:
            return {
                "items": [],
                "syncHint": "exchange_list",
                "message": "当前国家/地区还没有交易所清单，请先同步交易所数据。",
            }

        latest_date_subquery = (
            db.session.query(
                StockDailyBar.exchange_code.label("exchange_code"),
                StockDailyBar.ticker.label("ticker"),
                func.max(StockDailyBar.trade_date).label("latest_date"),
            )
            .group_by(StockDailyBar.exchange_code, StockDailyBar.ticker)
            .subquery()
        )

        rows = (
            db.session.query(Stock, latest_date_subquery.c.latest_date)
            .outerjoin(
                latest_date_subquery,
                (Stock.exchange_code == latest_date_subquery.c.exchange_code)
                & (Stock.ticker == latest_date_subquery.c.ticker),
            )
            .filter(Stock.country_code == normalized_country_code)
            .order_by(Stock.exchange_code.asc(), Stock.ticker.asc())
            .all()
        )
        if not rows:
            return {
                "items": [],
                "syncHint": "stock_list",
                "message": "当前国家/地区还没有股票清单，请先在数据中心同步对应交易所的股票数据。",
            }

        return {
            "items": [strategy_stock_option(row, latest_date) for row, latest_date in rows],
            "syncHint": None,
            "message": None,
        }

    latest_date_subquery = (
        db.session.query(
            IndexDailyBar.country_code.label("country_code"),
            IndexDailyBar.ticker.label("ticker"),
            func.max(IndexDailyBar.trade_date).label("latest_date"),
        )
        .group_by(IndexDailyBar.country_code, IndexDailyBar.ticker)
        .subquery()
    )

    rows = (
        db.session.query(IndexAsset, latest_date_subquery.c.latest_date)
        .outerjoin(
            latest_date_subquery,
            (IndexAsset.country_code == latest_date_subquery.c.country_code)
            & (IndexAsset.ticker == latest_date_subquery.c.ticker),
        )
        .filter(IndexAsset.country_code == normalized_country_code)
        .order_by(IndexAsset.ticker.asc())
        .all()
    )
    if not rows:
        return {
            "items": [],
            "syncHint": "index_list",
            "message": "当前国家/地区还没有指数清单，请先同步指数数据。",
        }

    return {
        "items": [strategy_index_option(row, latest_date) for row, latest_date in rows],
        "syncHint": None,
        "message": None,
    }


def strategy_stock_option(stock: Stock, latest_date: date | None) -> dict:
    latest_date_text = latest_date.isoformat() if latest_date else None
    label = f"{stock.ticker} - {stock.name}"
    if latest_date_text:
        label = f"{label}（同步至 {latest_date_text}）"
    return {
        "label": label,
        "value": f"{stock.exchange_code}:{stock.ticker}",
        "ticker": stock.ticker,
        "exchangeCode": stock.exchange_code,
        "name": stock.name,
        "latestDate": latest_date_text,
    }


def strategy_index_option(index_asset: IndexAsset, latest_date: date | None) -> dict:
    latest_date_text = latest_date.isoformat() if latest_date else None
    label = f"{index_asset.ticker} - {index_asset.name}"
    if latest_date_text:
        label = f"{label}（同步至 {latest_date_text}）"
    return {
        "label": label,
        "value": index_asset.ticker,
        "ticker": index_asset.ticker,
        "name": index_asset.name,
        "latestDate": latest_date_text,
    }


def list_strategies(
    user: User,
    *,
    keyword: str = "",
    country_region: str = "",
    source: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 10,
    sort_field: str = "updatedAt",
    sort_order: str = "descend",
) -> dict:
    _normalize_user_strategy_country_regions(user.id)
    query = Strategy.query.filter(Strategy.user_id == user.id)

    normalized_keyword = keyword.strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.filter(
            or_(
                Strategy.name.ilike(pattern),
                Strategy.type.ilike(pattern),
                Strategy.country_region.ilike(pattern),
            )
        )

    if country_region:
        query = query.filter(Strategy.country_region == _normalize_country_region(country_region))
    if source:
        query = query.filter(Strategy.source == source)
    if status:
        query = query.filter(Strategy.status == status)

    if sort_field == "annualReturn":
        order_column = Strategy.annual_return
        query = query.order_by(
            asc(order_column).nullslast() if sort_order == "ascend" else desc(order_column).nullslast()
        )
    else:
        order_column = Strategy.updated_at
        query = query.order_by(asc(order_column) if sort_order == "ascend" else desc(order_column))

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    country_region_options = [
        value
        for value in db.session.query(Strategy.country_region)
        .filter(Strategy.user_id == user.id)
        .distinct()
        .order_by(Strategy.country_region.asc())
        .all()
    ]
    source_options = [
        value
        for value in db.session.query(Strategy.source)
        .filter(Strategy.user_id == user.id)
        .distinct()
        .order_by(Strategy.source.asc())
        .all()
    ]
    status_options = [
        value
        for value in db.session.query(Strategy.status)
        .filter(Strategy.user_id == user.id)
        .distinct()
        .order_by(Strategy.status.asc())
        .all()
    ]

    return {
        "items": [item.to_dict() for item in items],
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": total,
        },
        "filters": {
            "countryRegions": [value for (value,) in country_region_options if value],
            "sources": [value for (value,) in source_options if value],
            "statuses": [value for (value,) in status_options if value],
        },
    }


def get_strategy(user: User, strategy_id: int) -> Strategy:
    strategy = Strategy.query.filter(
        Strategy.id == strategy_id,
        Strategy.user_id == user.id,
    ).first()
    if not strategy:
        raise StrategyError("未找到对应的策略。")
    normalized_country_region = _normalize_country_region(strategy.country_region)
    if normalized_country_region != strategy.country_region:
        strategy.country_region = normalized_country_region
        db.session.commit()
    return strategy


def _normalize_user_strategy_country_regions(user_id: int) -> None:
    changed = False
    for strategy in Strategy.query.filter(Strategy.user_id == user_id).all():
        normalized = _normalize_country_region(strategy.country_region)
        if normalized and normalized != strategy.country_region:
            strategy.country_region = normalized
            changed = True
    if changed:
        db.session.commit()


def _normalize_country_region(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    code_candidate = text.split("-", 1)[0].strip().upper()
    country = Country.query.filter(Country.country_code == code_candidate).first()
    if country:
        return country.country_code

    country = Country.query.filter(Country.country_name == text).first()
    if country:
        return country.country_code

    return code_candidate
