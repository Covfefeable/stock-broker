"use client";

import { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";
import { EmptyState } from "@/components/empty-state";
import type { BrowserBar } from "@/components/data-center/types";

type Props = {
  bars: BrowserBar[];
  dark?: boolean;
};

export function KlineChart({ bars, dark = true }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  const validBars = useMemo(
    () =>
      bars.filter(
        (item) =>
          item.date &&
          item.open !== null &&
          item.high !== null &&
          item.low !== null &&
          item.close !== null,
      ),
    [bars],
  );

  useEffect(() => {
    const node = containerRef.current;
    if (!node || !validBars.length) {
      return;
    }

    const chart = echarts.init(node, undefined, { renderer: "canvas" });
    const dates = validBars.map((item) => item.date as string);
    const kline = validBars.map((item) => [item.open, item.close, item.low, item.high]);
    const volume = validBars.map((item, index) => [
      index,
      item.volume ?? 0,
      (item.close ?? 0) >= (item.open ?? 0) ? 1 : -1,
    ]);

    chart.setOption({
      animation: false,
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
        borderWidth: 0,
        backgroundColor: dark ? "rgba(15,23,42,0.92)" : "rgba(255,255,255,0.96)",
        textStyle: { color: dark ? "#e5e7eb" : "#111827" },
      },
      axisPointer: {
        link: [{ xAxisIndex: "all" }],
        label: { backgroundColor: "#6366f1" },
      },
      grid: [
        { left: 48, right: 18, top: 16, height: "62%" },
        { left: 48, right: 18, top: "74%", height: "16%" },
      ],
      xAxis: [
        {
          type: "category",
          data: dates,
          scale: true,
          boundaryGap: false,
          axisLine: { lineStyle: { color: dark ? "#334155" : "#cbd5e1" } },
          axisLabel: { color: dark ? "#94a3b8" : "#64748b" },
          splitLine: { show: false },
          min: "dataMin",
          max: "dataMax",
        },
        {
          type: "category",
          gridIndex: 1,
          data: dates,
          scale: true,
          boundaryGap: false,
          axisLine: { lineStyle: { color: dark ? "#334155" : "#cbd5e1" } },
          axisLabel: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
          min: "dataMin",
          max: "dataMax",
        },
      ],
      yAxis: [
        {
          scale: true,
          splitArea: { show: false },
          axisLine: { show: false },
          axisLabel: { color: dark ? "#94a3b8" : "#64748b" },
          splitLine: { lineStyle: { color: dark ? "rgba(51,65,85,0.35)" : "rgba(203,213,225,0.8)" } },
        },
        {
          scale: true,
          gridIndex: 1,
          axisLine: { show: false },
          axisLabel: { color: dark ? "#94a3b8" : "#64748b" },
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        { type: "inside", xAxisIndex: [0, 1], start: 60, end: 100 },
        {
          show: true,
          xAxisIndex: [0, 1],
          type: "slider",
          bottom: 8,
          height: 18,
          borderColor: "transparent",
          backgroundColor: dark ? "rgba(51,65,85,0.35)" : "rgba(226,232,240,0.9)",
          fillerColor: "rgba(99,102,241,0.28)",
          handleStyle: { color: "#6366f1", borderColor: "#6366f1" },
        },
      ],
      series: [
        {
          name: "K线",
          type: "candlestick",
          data: kline,
          itemStyle: {
            color: "#ef4444",
            color0: "#10b981",
            borderColor: "#ef4444",
            borderColor0: "#10b981",
          },
        },
        {
          name: "成交量",
          type: "bar",
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volume,
          itemStyle: {
            color: (params: { data: [number, number, number] }) =>
              params.data[2] > 0 ? "rgba(239,68,68,0.75)" : "rgba(16,185,129,0.75)",
          },
        },
      ],
    });

    const resizeObserver = new ResizeObserver(() => chart.resize());
    resizeObserver.observe(node);

    return () => {
      resizeObserver.disconnect();
      chart.dispose();
    };
  }, [dark, validBars]);

  if (!validBars.length) {
    return (
      <div className="data-browser-empty-chart">
        <EmptyState title="请选择股票或指数" />
      </div>
    );
  }

  return <div ref={containerRef} className="data-browser-kline-chart" />;
}
