"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { StrategyPreviewResult } from "@/components/strategy-builder/types";

type Props = {
  preview: StrategyPreviewResult;
  activeDate?: string | null;
  onActiveDateChange?: (date: string) => void;
};

export function StrategyPreviewChart({ preview, activeDate, onActiveDateChange }: Props) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<echarts.EChartsType | null>(null);
  const suppressAxisPointerRef = useRef(false);

  useEffect(() => {
    if (!chartRef.current) {
      return;
    }

    const equityValueByDate = new Map(preview.equityCurve.map((item) => [item.date, item.value]));
    const tradeMarkerLimit = 60;
    const tradeMarkerStep = Math.max(1, Math.ceil(preview.trades.length / tradeMarkerLimit));
    const visibleTrades = preview.trades.filter((_, index) => index % tradeMarkerStep === 0);
    const buyPoints = visibleTrades
      .filter((trade) => trade.side === "buy")
      .map((trade) => [trade.date, equityValueByDate.get(trade.date), trade.price, trade.reason, "买入"])
      .filter((item) => item[1] !== undefined);
    const sellPoints = visibleTrades
      .filter((trade) => trade.side === "sell")
      .map((trade) => [trade.date, equityValueByDate.get(trade.date), trade.price, trade.reason, "卖出"])
      .filter((item) => item[1] !== undefined);
    const resolveAxisDate = (value: string | number) => {
      if (typeof value === "number") {
        return preview.equityCurve[Math.round(value)]?.date ?? null;
      }
      const numericIndex = Number(value);
      if (Number.isInteger(numericIndex) && preview.equityCurve[numericIndex]) {
        return preview.equityCurve[numericIndex].date;
      }
      return equityValueByDate.has(value) ? value : null;
    };

    const chart = echarts.init(chartRef.current, undefined, { renderer: "canvas" });
    chartInstanceRef.current = chart;
    chart.setOption({
      backgroundColor: "transparent",
      animation: true,
      grid: {
        left: 12,
        right: 12,
        top: 24,
        bottom: 54,
        containLabel: true,
      },
      legend: {
        top: 0,
        data: ["策略净值", "买入持有基准"],
        textStyle: {
          color: "rgba(191, 219, 254, 0.82)",
          fontSize: 12,
        },
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(15, 23, 42, 0.96)",
        borderColor: "rgba(99, 102, 241, 0.24)",
        textStyle: {
          color: "#f8fafc",
        },
        formatter: (params: unknown) => {
          const rows = Array.isArray(params) ? params : [params];
          const axisLabel = rows[0]?.axisValueLabel ?? rows[0]?.name ?? "";
          const lines = rows.map((row) => {
            const value = Array.isArray(row.value) ? row.value[1] : row.value;
            if (Array.isArray(row.value) && row.value[4]) {
              const price = Array.isArray(row.value) ? row.value[2] : undefined;
              const reason = Array.isArray(row.value) ? row.value[3] : "";
              return `${row.marker}${row.value[4]}: ${price != null ? Number(price).toFixed(4) : "-"}${reason ? ` (${reason})` : ""}`;
            }
            return `${row.marker}${row.seriesName}: ${Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 2 })}`;
          });
          return [axisLabel, ...lines].join("<br/>");
        },
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: preview.equityCurve.map((item) => item.date),
        axisLine: {
          lineStyle: {
            color: "rgba(148, 163, 184, 0.28)",
          },
        },
        axisLabel: {
          color: "rgba(191, 219, 254, 0.62)",
          fontSize: 11,
          formatter: (value: string) => value.slice(5),
        },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLine: { show: false },
        splitLine: {
          lineStyle: {
            color: "rgba(148, 163, 184, 0.12)",
          },
        },
        axisLabel: {
          color: "rgba(191, 219, 254, 0.62)",
          fontSize: 11,
        },
      },
      dataZoom: [
        {
          type: "inside",
          xAxisIndex: 0,
          filterMode: "none",
          minSpan: 3,
          throttle: 50,
          zoomOnMouseWheel: true,
          moveOnMouseMove: true,
          moveOnMouseWheel: false,
        },
        {
          type: "slider",
          xAxisIndex: 0,
          bottom: 8,
          height: 20,
          filterMode: "none",
          minSpan: 3,
          borderColor: "rgba(99, 102, 241, 0.18)",
          fillerColor: "rgba(99, 102, 241, 0.2)",
          backgroundColor: "rgba(15, 23, 42, 0.36)",
          handleSize: 14,
          handleStyle: {
            color: "#6366f1",
            borderColor: "rgba(199, 210, 254, 0.88)",
          },
          moveHandleStyle: {
            color: "rgba(99, 102, 241, 0.34)",
          },
          selectedDataBackground: {
            lineStyle: {
              color: "rgba(148, 163, 184, 0.75)",
            },
            areaStyle: {
              color: "rgba(99, 102, 241, 0.12)",
            },
          },
          textStyle: {
            color: "rgba(191, 219, 254, 0.58)",
          },
        },
      ],
      series: [
        {
          name: "策略净值",
          type: "line",
          smooth: true,
          showSymbol: false,
          lineStyle: {
            width: 2,
            color: "#6366f1",
          },
          areaStyle: {
            color: "rgba(99, 102, 241, 0.12)",
          },
          data: preview.equityCurve.map((item) => item.value),
        },
        {
          name: "买入持有基准",
          type: "line",
          smooth: true,
          showSymbol: false,
          lineStyle: {
            width: 2,
            color: "#14b8a6",
          },
          data: preview.benchmarkCurve.map((item) => item.value),
        },
        {
          name: "策略净值",
          type: "scatter",
          legendHoverLink: false,
          symbol: "circle",
          symbolSize: 6,
          itemStyle: {
            color: "rgba(59, 130, 246, 0.72)",
            borderColor: "rgba(191, 219, 254, 0.84)",
            borderWidth: 1,
          },
          z: 6,
          data: buyPoints,
        },
        {
          name: "策略净值",
          type: "scatter",
          legendHoverLink: false,
          symbol: "circle",
          symbolSize: 6,
          itemStyle: {
            color: "rgba(239, 68, 68, 0.72)",
            borderColor: "rgba(254, 226, 226, 0.84)",
            borderWidth: 1,
          },
          z: 6,
          data: sellPoints,
        },
      ],
    });

    const resizeObserver = new ResizeObserver(() => {
      chart.resize();
    });
    resizeObserver.observe(chartRef.current);

    chart.on("updateAxisPointer", (event: unknown) => {
      if (suppressAxisPointerRef.current) {
        return;
      }
      const payload = event as { axesInfo?: Array<{ axisDim?: string; value?: string | number }> };
      const axisValue = payload.axesInfo?.find((item) => item.axisDim === "x")?.value;
      if (axisValue !== undefined && axisValue !== null) {
        const date = resolveAxisDate(axisValue);
        if (date) {
          onActiveDateChange?.(date);
        }
      }
    });

    return () => {
      resizeObserver.disconnect();
      chartInstanceRef.current = null;
      chart.dispose();
    };
  }, [onActiveDateChange, preview]);

  useEffect(() => {
    const chart = chartInstanceRef.current;
    if (!chart || !activeDate) {
      return;
    }
    const dataIndex = preview.equityCurve.findIndex((item) => item.date === activeDate);
    if (dataIndex < 0) {
      return;
    }
    suppressAxisPointerRef.current = true;
    chart.dispatchAction({
      type: "showTip",
      seriesIndex: 0,
      dataIndex,
    });
    window.setTimeout(() => {
      suppressAxisPointerRef.current = false;
    }, 80);
  }, [activeDate, preview.equityCurve]);

  return <div className="strategy-preview-chart" ref={chartRef} />;
}
