export type ExchangeOption = { label: string; value: string };
export type CountryOption = { label: string; value: string };
export type StockOption = { label: string; value: string; latestDate?: string | null };

export type StockDailyCoverage = {
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
  syncItem: "country_list" | "exchange_list" | "stock_list" | "index_list" | "stock_daily_history";
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
