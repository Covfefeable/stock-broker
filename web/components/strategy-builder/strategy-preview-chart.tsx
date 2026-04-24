"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { StrategyPreviewResult } from "@/components/strategy-builder/types";

type Props = {
  preview: StrategyPreviewResult;
};

export function StrategyPreviewChart({ preview }: Props) {
  const chartRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!chartRef.current) {
      return;
    }

    const chart = echarts.init(chartRef.current, undefined, { renderer: "canvas" });
    chart.setOption({
      backgroundColor: "transparent",
      animation: true,
      grid: {
        left: 12,
        right: 12,
        top: 24,
        bottom: 28,
        containLabel: true,
      },
      legend: {
        top: 0,
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
          name: "买入持有",
          type: "line",
          smooth: true,
          showSymbol: false,
          lineStyle: {
            width: 2,
            color: "#14b8a6",
          },
          data: preview.benchmarkCurve.map((item) => item.value),
        },
      ],
    });

    const resizeObserver = new ResizeObserver(() => {
      chart.resize();
    });
    resizeObserver.observe(chartRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.dispose();
    };
  }, [preview]);

  return <div className="strategy-preview-chart" ref={chartRef} />;
}
