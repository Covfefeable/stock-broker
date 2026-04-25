import type { EventLogItem, OverviewMetrics, TimelineLogRow } from "@/components/data-center/types";

export const defaultMetrics: OverviewMetrics = {
  stocksCount: 0,
  stockDailyBarsCount: 0,
  exchangeCount: 0,
  syncedAssetsCount: 0,
  latestTradeDate: null,
  exchangeCoverage: [],
};

export function mapEventLogRow(item: EventLogItem): TimelineLogRow {
  return {
    key: String(item.id),
    time: formatDisplayTime(item.time),
    task: item.eventNameLabel || item.eventName,
    dataset: item.targetLabel || item.target || "-",
    cost: item.durationMs ? `${item.durationMs} ms` : "-",
    status:
      item.status === "success"
        ? "成功"
        : item.status === "running"
          ? "运行中"
          : item.status === "queued"
            ? "排队中"
          : item.status === "partial_success"
            ? "部分成功"
            : "失败",
    message: normalizeDisplayText(item.message),
  };
}

export function formatDisplayTime(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatInteger(value: number): string {
  return new Intl.NumberFormat("zh-CN").format(value);
}

export function formatPercent(value: number): string {
  return value.toFixed(2);
}

export function normalizeDisplayText(value: string): string {
  return value
    .replaceAll("index_daily_history", "指数历史日线")
    .replaceAll("stock_daily_history", "股票历史日线")
    .replaceAll("trading_calendar", "交易日历")
    .replaceAll("country_list", "国家/地区清单")
    .replaceAll("exchange_list", "交易所清单")
    .replaceAll("stock_list", "股票清单")
    .replaceAll("index_list", "指数清单");
}
