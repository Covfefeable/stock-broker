export type RuleLogic = "and" | "or";
export type RuleOperator = ">" | ">=" | "<" | "<=" | "==" | "!=" | "cross_over" | "cross_under";
export type RuleScope = "entry" | "exit";
export type ExpressionOperator = "+" | "-" | "*" | "/";
export type ExpressionFunctionName =
  | "abs"
  | "min"
  | "max"
  | "sum"
  | "avg"
  | "std"
  | "highest"
  | "lowest"
  | "change"
  | "pct_change"
  | "ema"
  | "slope"
  | "zscore"
  | "percentile_rank"
  | "drawdown_from_high";

export type RuleFieldValue =
  | "open"
  | "high"
  | "low"
  | "close"
  | "volume"
  | "ma5"
  | "ma10"
  | "ma20"
  | "ma60"
  | "ma120"
  | "kdj_k"
  | "kdj_d"
  | "macd_dif"
  | "macd_dea"
  | "rsi14"
  | "bias_ma20"
  | "atr14_pct"
  | "volatility_20d"
  | "range_pct"
  | "gap_pct"
  | "close_pct_of_20d_range"
  | "close_pct_of_60d_range"
  | "distance_to_20d_high"
  | "distance_to_20d_low"
  | "position_return"
  | "position_ratio"
  | "holding_days"
  | "days_since_last_trade";

export type ExpressionToken =
  | { type: "variable"; name: RuleFieldValue; offset?: number }
  | { type: "number"; value: number }
  | { type: "operator"; value: ExpressionOperator }
  | { type: "groupStart" }
  | { type: "groupEnd" }
  | { type: "function"; name: ExpressionFunctionName; args: ExpressionToken[][] };

export type RuleCondition = {
  id: string;
  type: "condition";
  leftExpression: ExpressionToken[];
  operator: RuleOperator;
  rightExpression: ExpressionToken[];
};

export type RuleGroup = {
  id: string;
  type: "group";
  logic: RuleLogic;
  children: RuleNode[];
};

export type RuleNode = RuleCondition | RuleGroup;

export type StrategyRuleAction = {
  type: "buy" | "sell";
  size: number;
};

export type StrategyRule = {
  id: string;
  name: string;
  action: StrategyRuleAction;
  conditions: RuleGroup;
};

export type RiskBacktestConfig = {
  forceCloseOnEnd: boolean;
  backtestStartDate: string;
  backtestEndDate: string;
};

export type StrategyDslConfig = {
  entryRules: StrategyRule[];
  exitRules: StrategyRule[];
  entry?: RuleGroup;
  exit?: RuleGroup;
  risk: RiskBacktestConfig;
};

export type StrategyPreviewResult = {
  score?: number;
  benchmarkScore?: number;
  annualReturn: number;
  benchmarkAnnualReturn: number;
  totalReturn: number;
  maxDrawdown: number;
  benchmarkMaxDrawdown: number;
  volatility: number;
  benchmarkVolatility: number;
  sharpe: number;
  benchmarkSharpe: number;
  tradeCount: number;
  benchmarkTradeCount: number;
  winRate: number;
  benchmarkWinRate: number;
  initialCapital: number;
  finalEquity: number;
  benchmarkReturn: number;
  equityCurve: Array<{ date: string; value: number }>;
  benchmarkCurve: Array<{ date: string; value: number }>;
  trades: Array<{
    date: string;
    side: "buy" | "sell";
    price: number;
    shares: number;
    positionRatio?: number;
    return?: number;
    reason: string;
  }>;
  dateRange: {
    start: string | null;
    end: string | null;
  };
};
