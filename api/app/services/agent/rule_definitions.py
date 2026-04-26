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
    {"label": "5日收益率", "value": "return_5d", "description": "close / close[-5] - 1。"},
    {"label": "20日收益率", "value": "return_20d", "description": "close / close[-20] - 1。"},
    {"label": "60日收益率", "value": "return_60d", "description": "close / close[-60] - 1。"},
    {"label": "量比(5日)", "value": "volume_ratio_5", "description": "当日成交量相对 5 日平均成交量的倍数。"},
    {"label": "量比(20日)", "value": "volume_ratio_20", "description": "当日成交量相对 20 日平均成交量的倍数。"},
    {"label": "ATR14", "value": "atr14", "description": "14 日平均真实波幅。"},
    {"label": "20日波动率", "value": "volatility_20d", "description": "最近 20 个交易日日收益率标准差，不做年化。"},
    {"label": "20日区间位置", "value": "close_pct_of_20d_range", "description": "收盘价位于最近 20 日高低区间中的相对位置。"},
    {"label": "60日区间位置", "value": "close_pct_of_60d_range", "description": "收盘价位于最近 60 日高低区间中的相对位置。"},
    {"label": "距20日高点", "value": "distance_to_20d_high", "description": "收盘价相对最近 20 日最高价的偏离率。"},
    {"label": "距20日低点", "value": "distance_to_20d_low", "description": "收盘价相对最近 20 日最低价的偏离率。"},
    {"label": "实体占比", "value": "body_pct", "description": "|close - open| / open。"},
    {"label": "上影线占比", "value": "upper_shadow_pct", "description": "上影线长度相对开盘价的比例。"},
    {"label": "下影线占比", "value": "lower_shadow_pct", "description": "下影线长度相对开盘价的比例。"},
    {"label": "向上跳空", "value": "gap_up", "description": "若开盘价高于前一日最高价则记为 1，否则为 0。"},
    {"label": "向下跳空", "value": "gap_down", "description": "若开盘价低于前一日最低价则记为 1，否则为 0。"},
    {"label": "持仓收益率", "value": "position_return", "description": "当前收盘价相对持仓成本的收益率。"},
    {"label": "持仓天数", "value": "holding_days", "description": "从首次建仓到当前 K 线为止已持有的交易日数。"},
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
