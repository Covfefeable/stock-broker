export type RuleLogic = "and" | "or";
export type RuleOperator = ">" | ">=" | "<" | "<=" | "==" | "!=" | "cross_over" | "cross_under";
export type RuleRightMode = "field" | "constant";
export type RuleScope = "entry" | "exit";

export type RuleFieldValue =
  | "open"
  | "high"
  | "low"
  | "close"
  | "volume"
  | "ma5"
  | "ma20"
  | "kdj_k"
  | "kdj_d"
  | "macd_dif"
  | "macd_dea"
  | "rsi14"
  | "position_return"
  | "holding_days";

export type RuleCondition = {
  id: string;
  type: "condition";
  leftField: RuleFieldValue;
  operator: RuleOperator;
  rightMode: RuleRightMode;
  rightField?: RuleFieldValue;
  rightValue?: number;
};

export type RuleGroup = {
  id: string;
  type: "group";
  logic: RuleLogic;
  children: RuleNode[];
};

export type RuleNode = RuleCondition | RuleGroup;

export type RiskBacktestConfig = {
  initialCapital: number;
  positionSize: number;
  stopLoss: number;
  takeProfit: number;
  maxHoldingDays: number;
  backtestStartDate: string;
  backtestEndDate: string;
};

export type StrategyDslConfig = {
  entry: RuleGroup;
  exit: RuleGroup;
  risk: RiskBacktestConfig;
};

export type StrategyPreviewResult = {
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
    return?: number;
    reason: string;
  }>;
  dateRange: {
    start: string | null;
    end: string | null;
  };
};
