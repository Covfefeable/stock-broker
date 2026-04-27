"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Table, Tag, Tooltip, Typography } from "antd";
import { EmptyState } from "@/components/empty-state";
import { StrategyPreviewChart } from "@/components/strategy-builder/strategy-preview-chart";
import type { StrategyPreviewResult } from "@/components/strategy-builder/types";

const { Text } = Typography;

type MetricItem = {
  label: string;
  strategyValue: string;
  benchmarkValue: string;
};

type Props = {
  preview: StrategyPreviewResult;
  metrics: MetricItem[];
  rulePreview?: ReactNode;
  tradeScrollY?: number;
};

export function StrategyBacktestDetailPanel({ preview, metrics, rulePreview, tradeScrollY = 260 }: Props) {
  const [activeDate, setActiveDate] = useState<string | null>(null);
  const tableWrapRef = useRef<HTMLDivElement | null>(null);
  const activeSourceRef = useRef<"chart" | "table" | null>(null);
  const debounceTimerRef = useRef<number | null>(null);

  const dateIndexMap = useMemo(() => {
    return new Map(preview.equityCurve.map((item, index) => [item.date, index]));
  }, [preview.equityCurve]);

  const activeTradeDate = useMemo(() => {
    if (!activeDate || !preview.trades.length) {
      return null;
    }
    const targetIndex = dateIndexMap.get(activeDate);
    if (targetIndex === undefined) {
      return activeDate;
    }
    return preview.trades.reduce<string | null>((bestDate, trade) => {
      const tradeIndex = dateIndexMap.get(trade.date);
      if (tradeIndex === undefined) {
        return bestDate;
      }
      if (!bestDate) {
        return trade.date;
      }
      const bestIndex = dateIndexMap.get(bestDate);
      return bestIndex === undefined || Math.abs(tradeIndex - targetIndex) < Math.abs(bestIndex - targetIndex)
        ? trade.date
        : bestDate;
    }, null);
  }, [activeDate, dateIndexMap, preview.trades]);

  useEffect(() => {
    if (!activeTradeDate || activeSourceRef.current !== "chart") {
      return;
    }
    const rows = Array.from(tableWrapRef.current?.querySelectorAll<HTMLTableRowElement>("tr[data-trade-date]") ?? []);
    const row = rows.find((item) => item.dataset.tradeDate === activeTradeDate);
    row?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeTradeDate]);

  const handleChartActiveDateChange = useCallback((date: string) => {
    activeSourceRef.current = "chart";
    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = window.setTimeout(() => {
      setActiveDate((current) => (current === date ? current : date));
    }, 80);
  }, []);

  const handleTradeRowEnter = useCallback((date: string) => {
    activeSourceRef.current = "table";
    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = window.setTimeout(() => {
      setActiveDate((current) => (current === date ? current : date));
    }, 80);
  }, []);

  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        window.clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  return (
    <div className="strategy-preview-panel">
      <div className="strategy-preview-metrics">
        {metrics.map((metric) => (
          <div key={metric.label} className="strategy-preview-metric-card">
            <div className="strategy-preview-metric-header">
              <span>{metric.label}</span>
            </div>
            <div className="strategy-preview-metric-values">
              <div>
                <small>策略</small>
                <strong>{metric.strategyValue}</strong>
              </div>
              <div>
                <small>买入持有基准</small>
                <strong>{metric.benchmarkValue}</strong>
              </div>
            </div>
          </div>
        ))}
      </div>

      {rulePreview ? <div className="agent-iteration-detail-rule-section">{rulePreview}</div> : null}

      <StrategyPreviewChart preview={preview} activeDate={activeDate} onActiveDateChange={handleChartActiveDateChange} />

      <div className="strategy-preview-range">
        <Text type="secondary">
          回测区间：{preview.dateRange.start ?? "--"} 至 {preview.dateRange.end ?? "--"}
        </Text>
      </div>

      <div ref={tableWrapRef}>
        <Table
          className="strategy-preview-trades"
          size="small"
          pagination={false}
          scroll={{ y: tradeScrollY }}
          rowKey={(record) => `${record.date}_${record.side}_${record.price}_${record.shares}`}
          rowClassName={(record) => (record.date === activeTradeDate ? "strategy-trade-row-active" : "")}
          onRow={(record) => ({
            "data-trade-date": record.date,
            onMouseEnter: () => handleTradeRowEnter(record.date),
          })}
          dataSource={preview.trades}
          locale={{
            emptyText: <EmptyState title="暂无成交记录" compact />,
          }}
          columns={[
            { title: "日期", dataIndex: "date", width: 120 },
            {
              title: "方向",
              dataIndex: "side",
              width: 80,
              render: (value: "buy" | "sell") => (
                <Tag color={value === "buy" ? "blue" : "volcano"}>{value === "buy" ? "买入" : "卖出"}</Tag>
              ),
            },
            { title: "价格", dataIndex: "price", width: 100 },
            { title: "数量", dataIndex: "shares", width: 100 },
            {
              title: "仓位",
              dataIndex: "positionRatio",
              width: 100,
              render: (value?: number) => (value == null ? "--" : `${Number(value).toFixed(2)}%`),
            },
            {
              title: "收益率",
              dataIndex: "return",
              render: (value?: number) => (value == null ? "--" : `${value.toFixed(2)}%`),
            },
            {
              title: "触发原因",
              dataIndex: "reason",
              ellipsis: true,
              render: (value: string) => (
                <Tooltip title={value}>
                  <span>{value || "-"}</span>
                </Tooltip>
              ),
            },
          ]}
        />
      </div>
    </div>
  );
}
