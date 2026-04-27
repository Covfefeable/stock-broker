from __future__ import annotations


RULE_FIELDS = [
    {"label": "收盘价", "value": "close", "description": "当日收盘成交价。"},
    {"label": "开盘价", "value": "open", "description": "当日开盘成交价。"},
    {"label": "最高价", "value": "high", "description": "当日最高成交价。"},
    {"label": "最低价", "value": "low", "description": "当日最低成交价。"},
    {"label": "成交量", "value": "volume", "description": "当日成交数量。"},
    {"label": "MA5", "value": "ma5", "description": "最近 5 个交易日收盘价的简单移动平均。"},
    {"label": "MA10", "value": "ma10", "description": "最近 10 个交易日收盘价的简单移动平均。"},
    {"label": "MA20", "value": "ma20", "description": "最近 20 个交易日收盘价的简单移动平均。"},
    {"label": "MA60", "value": "ma60", "description": "最近 60 个交易日收盘价的简单移动平均。"},
    {"label": "MA120", "value": "ma120", "description": "最近 120 个交易日收盘价的简单移动平均。"},
    {"label": "RSI14", "value": "rsi14", "description": "14 日相对强弱指标，通常在 0 到 100 之间。"},
    {"label": "MACD DIF", "value": "macd_dif", "description": "EMA12 与 EMA26 的差值。"},
    {"label": "MACD DEA", "value": "macd_dea", "description": "MACD DIF 的 9 周期 EMA。"},
    {"label": "KDJ K", "value": "kdj_k", "description": "KDJ 中较敏感的 K 值。"},
    {"label": "KDJ D", "value": "kdj_d", "description": "KDJ 中更平滑的 D 值。"},
    {"label": "BIAS(MA20)", "value": "bias_ma20", "description": "收盘价相对 MA20 的偏离率，口径为 close / MA20 - 1。"},
    {"label": "ATR14占比", "value": "atr14_pct", "description": "14 日平均真实波幅相对收盘价的比例，口径为 ATR14 / close。"},
    {"label": "20日波动率", "value": "volatility_20d", "description": "最近 20 个交易日日收益率标准差，不做年化。"},
    {"label": "日内振幅", "value": "range_pct", "description": "当日最高价与最低价的差相对收盘价的比例，口径为 (high - low) / close。"},
    {"label": "跳空幅度", "value": "gap_pct", "description": "当日开盘价相对前一交易日收盘价的变化率，口径为 open / close[-1] - 1。"},
    {"label": "20日区间位置", "value": "close_pct_of_20d_range", "description": "收盘价位于最近 20 日高低区间中的相对位置。"},
    {"label": "60日区间位置", "value": "close_pct_of_60d_range", "description": "收盘价位于最近 60 日高低区间中的相对位置。"},
    {"label": "距20日高点", "value": "distance_to_20d_high", "description": "收盘价相对最近 20 日最高价的偏离率。"},
    {"label": "距20日低点", "value": "distance_to_20d_low", "description": "收盘价相对最近 20 日最低价的偏离率。"},
    {"label": "持仓收益率", "value": "position_return", "description": "当前收盘价相对持仓成本的收益率。"},
    {"label": "当前仓位", "value": "position_ratio", "description": "当前持仓市值占总权益的比例，范围通常为 0 到 1。"},
    {"label": "持仓天数", "value": "holding_days", "description": "从首次建仓到当前 K 线为止已持有的交易日数。"},
    {"label": "距上次交易天数", "value": "days_since_last_trade", "description": "距离最近一次买入或卖出的交易日数量。"},
]

RULE_OPERATORS = [
    {"label": "大于", "value": ">"},
    {"label": "大于等于", "value": ">="},
    {"label": "小于", "value": "<"},
    {"label": "小于等于", "value": "<="},
    {"label": "等于", "value": "=="},
    {"label": "不等于", "value": "!="},
    {"label": "上穿", "value": "cross_over"},
    {"label": "下穿", "value": "cross_under"},
]
RULE_FIELD_VALUES = {item["value"] for item in RULE_FIELDS}
RULE_OPERATOR_VALUES = {item["value"] for item in RULE_OPERATORS}
RULE_FUNCTIONS = [
    {"name": "abs", "args": "x", "description": "绝对值。"},
    {"name": "min", "args": "a, b", "description": "两个表达式取较小值。"},
    {"name": "max", "args": "a, b", "description": "两个表达式取较大值。"},
    {"name": "sum", "args": "x, n", "description": "最近 n 根 K 线的表达式求和。"},
    {"name": "avg", "args": "x, n", "description": "最近 n 根 K 线的表达式均值。"},
    {"name": "std", "args": "x, n", "description": "最近 n 根 K 线的表达式标准差。"},
    {"name": "highest", "args": "x, n", "description": "最近 n 根 K 线的表达式最大值。"},
    {"name": "lowest", "args": "x, n", "description": "最近 n 根 K 线的表达式最小值。"},
    {"name": "change", "args": "x, n", "description": "当前表达式值减去 n 根 K 线前的表达式值。"},
    {"name": "pct_change", "args": "x, n", "description": "当前表达式相对 n 根 K 线前的变化率。"},
    {"name": "ema", "args": "x, n", "description": "最近 n 根 K 线表达式的指数移动平均，首值使用窗口第一项。"},
    {"name": "slope", "args": "x, n", "description": "最近 n 根 K 线表达式对时间序号的线性回归斜率。"},
    {"name": "zscore", "args": "x, n", "description": "当前表达式相对最近 n 根 K 线均值的标准分。"},
    {"name": "percentile_rank", "args": "x, n", "description": "当前表达式在最近 n 根 K 线中的分位排名，范围 0 到 1。"},
    {"name": "drawdown_from_high", "args": "x, n", "description": "当前表达式相对最近 n 根 K 线最高值的回撤，口径为 x / highest(x, n) - 1。"},
]

AGENT_STRATEGY_INTENTS = {
    "trend_following": "趋势跟随",
    "trend_pullback": "趋势回踩",
    "breakout": "突破追涨",
    "mean_reversion": "均值回归",
    "dip_buying": "低吸抄底",
    "momentum_acceleration": "动能加速",
    "volatility_breakout": "波动突破",
    "defensive_timing": "防守择时",
    "range_trading": "区间高抛低吸",
}


FIELD_LABELS_BY_VALUE = {item["value"]: item["label"] for item in RULE_FIELDS}
OPERATOR_LABELS = {item["value"]: item["label"] for item in RULE_OPERATORS}
