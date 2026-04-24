export type ExchangeOption = { label: string; value: string; countryCode?: string | null };
export type CountryOption = { label: string; value: string };
export type StockOption = { label: string; value: string; latestDate?: string | null };
export type IndexOption = { label: string; value: string; latestDate?: string | null };
export type TradingCalendarDay = {
  exchangeCode: string;
  date: string;
  status: 0 | 1;
};

export type StockDailyCoverage = {
  existingDates: string[];
  latestDate: string | null;
  count: number;
};

export type IndexDailyCoverage = {
  existingDates: string[];
  latestDate: string | null;
  count: number;
};

export type PickerDateValue = {
  format: (pattern: string) => string;
};

export type EventLogItem = {
  id: number;
  time: string | null;
  eventName: string;
  target: string | null;
  status: string;
  message: string;
  durationMs: number | null;
};

export type ExchangeCoverageRow = {
  exchangeCode: string;
  exchangeName: string;
  actual: number;
  expected: number;
  percent: number;
};

export type OverviewMetrics = {
  stocksCount: number;
  stockDailyBarsCount: number;
  exchangeCount: number;
  syncedStocksCount: number;
  latestTradeDate: string | null;
  exchangeCoverage: ExchangeCoverageRow[];
};

export type IssueRow = {
  key: string;
  issueType: string;
  dataset: string;
  affected: string;
  severity: "轻微" | "中等" | "严重";
  status: string;
};

export type PriceRow = {
  key: string;
  code: string;
  name: string;
  date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
  amount: string;
  change: string;
  status: string;
};

export type TimelineLogRow = {
  key: string;
  time: string;
  task: string;
  dataset: string;
  cost: string;
  status: "成功" | "失败" | "运行中" | "部分成功";
  message: string;
};

export type SyncFormValues = {
  syncItem:
    | "country_list"
    | "exchange_list"
    | "stock_list"
    | "index_list"
    | "trading_calendar"
    | "stock_daily_history"
    | "index_daily_history";
  exchangeCode?: string;
  countryCode?: string;
  ticker?: string;
  dateMode?: "auto_fill" | "custom";
  dateRange?: [PickerDateValue, PickerDateValue];
};

export type TaskStatusResponse = {
  taskId: string;
  state: string;
  ready: boolean;
  successful: boolean;
  failed: boolean;
  result?: {
    recordsAffected?: number;
    totalStocks?: number;
    skippedCount?: number;
    successCount?: number;
    failedCount?: number;
    syncItemLabel?: string;
  };
  error?: string;
};

export type BrowserBar = {
  date: string | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
};

export type BrowserMeta = {
  type: "stock" | "index";
  name: string;
  ticker: string;
  exchangeCode?: string | null;
  countryCode?: string | null;
  latestDate: string | null;
  count: number;
};

export type SyncEnqueueResponse = {
  message: string;
  taskId: string;
};

export type DataSourceStatusItem = {
  sourceKey: string;
  sourceName: string;
  status: "normal" | "abnormal" | "unknown" | "checking";
  latencyMs: number | null;
  checkedAt: string | null;
  httpStatus: number | null;
  message: string | null;
};
