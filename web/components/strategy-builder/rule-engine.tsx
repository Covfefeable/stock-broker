"use client";

import { DeleteOutlined, PlusOutlined, QuestionCircleOutlined } from "@ant-design/icons";
import { Button, Card, Input, InputNumber, Modal, Popover, Radio, Select, Switch, Table, Tabs, Tag, Tooltip, Typography } from "antd";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { EmptyState } from "@/components/empty-state";
import { StrategyPreviewChart } from "@/components/strategy-builder/strategy-preview-chart";
import type {
  ExpressionFunctionName,
  ExpressionOperator,
  ExpressionToken,
  RiskBacktestConfig,
  RuleCondition,
  RuleFieldValue,
  RuleGroup,
  RuleLogic,
  RuleNode,
  RuleOperator,
  RuleScope,
  StrategyRule,
  StrategyDslConfig,
  StrategyPreviewResult,
} from "@/components/strategy-builder/types";

const { Text } = Typography;

type Props = {
  value: StrategyDslConfig;
  onChange: (nextValue: StrategyDslConfig) => void;
  onPreview?: () => void;
  previewLoading?: boolean;
  previewResult?: StrategyPreviewResult | null;
  previewDisabled?: boolean;
};

type RuleFieldOption = {
  label: string;
  value: RuleFieldValue;
  scopes: RuleScope[];
  category: string;
  help: string;
};

type PreviewMetricConfig = {
  key: string;
  label: string;
  help: string;
  strategyValue: (preview: StrategyPreviewResult) => string;
  benchmarkValue: (preview: StrategyPreviewResult) => string;
};

const FIELD_OPTIONS: RuleFieldOption[] = [
  { label: "开盘价", value: "open", scopes: ["entry", "exit"], category: "原始行情", help: "当日开盘成交价。" },
  { label: "最高价", value: "high", scopes: ["entry", "exit"], category: "原始行情", help: "当日最高成交价。" },
  { label: "最低价", value: "low", scopes: ["entry", "exit"], category: "原始行情", help: "当日最低成交价。" },
  { label: "收盘价", value: "close", scopes: ["entry", "exit"], category: "原始行情", help: "当日收盘成交价。" },
  { label: "成交量", value: "volume", scopes: ["entry", "exit"], category: "原始行情", help: "当日成交数量。" },
  { label: "MA5", value: "ma5", scopes: ["entry", "exit"], category: "趋势因子", help: "最近 5 个交易日收盘价的简单移动平均。" },
  { label: "MA10", value: "ma10", scopes: ["entry", "exit"], category: "趋势因子", help: "最近 10 个交易日收盘价的简单移动平均。" },
  { label: "MA20", value: "ma20", scopes: ["entry", "exit"], category: "趋势因子", help: "最近 20 个交易日收盘价的简单移动平均。" },
  { label: "MA60", value: "ma60", scopes: ["entry", "exit"], category: "趋势因子", help: "最近 60 个交易日收盘价的简单移动平均。" },
  { label: "MA120", value: "ma120", scopes: ["entry", "exit"], category: "趋势因子", help: "最近 120 个交易日收盘价的简单移动平均。" },
  { label: "RSI14", value: "rsi14", scopes: ["entry", "exit"], category: "动量因子", help: "14 日相对强弱指标，范围通常在 0 到 100。" },
  { label: "MACD DIF", value: "macd_dif", scopes: ["entry", "exit"], category: "动量因子", help: "EMA12 与 EMA26 的差值，反映快慢趋势差。" },
  { label: "MACD DEA", value: "macd_dea", scopes: ["entry", "exit"], category: "动量因子", help: "MACD DIF 的 9 周期 EMA。" },
  { label: "KDJ K", value: "kdj_k", scopes: ["entry", "exit"], category: "动量因子", help: "KDJ 中较敏感的 K 值，反映短线位置变化。" },
  { label: "KDJ D", value: "kdj_d", scopes: ["entry", "exit"], category: "动量因子", help: "KDJ 中更平滑的 D 值，常与 K 值配合看金叉死叉。" },
  { label: "BIAS(MA20)", value: "bias_ma20", scopes: ["entry", "exit"], category: "趋势因子", help: "收盘价相对 MA20 的偏离率，口径为 close / MA20 - 1。" },
  { label: "ATR14占比", value: "atr14_pct", scopes: ["entry", "exit"], category: "波动因子", help: "14 日平均真实波幅相对收盘价的比例，口径为 ATR14 / close。" },
  { label: "20日波动率", value: "volatility_20d", scopes: ["entry", "exit"], category: "波动因子", help: "最近 20 个交易日日收益率标准差，不做年化。" },
  { label: "日内振幅", value: "range_pct", scopes: ["entry", "exit"], category: "波动因子", help: "当日最高价与最低价的差相对收盘价的比例，口径为 (high - low) / close。" },
  { label: "跳空幅度", value: "gap_pct", scopes: ["entry", "exit"], category: "波动因子", help: "当日开盘价相对前一交易日收盘价的变化率，口径为 open / close[-1] - 1。" },
  { label: "20日区间位置", value: "close_pct_of_20d_range", scopes: ["entry", "exit"], category: "位置因子", help: "收盘价位于最近 20 日高低区间中的相对位置，范围通常在 0 到 1。" },
  { label: "60日区间位置", value: "close_pct_of_60d_range", scopes: ["entry", "exit"], category: "位置因子", help: "收盘价位于最近 60 日高低区间中的相对位置，范围通常在 0 到 1。" },
  { label: "距20日高点", value: "distance_to_20d_high", scopes: ["entry", "exit"], category: "位置因子", help: "收盘价相对最近 20 日最高价的偏离率，口径为 close / high20 - 1。" },
  { label: "距20日低点", value: "distance_to_20d_low", scopes: ["entry", "exit"], category: "位置因子", help: "收盘价相对最近 20 日最低价的偏离率，口径为 close / low20 - 1。" },
  { label: "持仓收益率", value: "position_return", scopes: ["exit"], category: "持仓状态", help: "当前收盘价相对持仓成本的收益率。" },
  { label: "当前仓位", value: "position_ratio", scopes: ["entry", "exit"], category: "持仓状态", help: "当前持仓市值占总权益的比例，范围通常为 0 到 1。" },
  { label: "持仓天数", value: "holding_days", scopes: ["exit"], category: "持仓状态", help: "从首次建仓到当前 K 线为止已持有的交易日数量。" },
  { label: "距上次交易天数", value: "days_since_last_trade", scopes: ["entry", "exit"], category: "持仓状态", help: "距离最近一次买入或卖出的交易日数量。" },
];

const OPERATOR_OPTIONS: Array<{ label: string; value: RuleOperator }> = [
  { label: "大于", value: ">" },
  { label: "大于等于", value: ">=" },
  { label: "小于", value: "<" },
  { label: "小于等于", value: "<=" },
  { label: "等于", value: "==" },
  { label: "不等于", value: "!=" },
  { label: "上穿", value: "cross_over" },
  { label: "下穿", value: "cross_under" },
];

const LOGIC_OPTIONS: Array<{ label: string; value: RuleLogic }> = [
  { label: "满足全部条件", value: "and" },
  { label: "满足任一条件", value: "or" },
];

const EXPRESSION_OPERATOR_OPTIONS: Array<{ label: string; value: ExpressionOperator }> = [
  { label: "+", value: "+" },
  { label: "-", value: "-" },
  { label: "*", value: "*" },
  { label: "/", value: "/" },
];

const FUNCTION_OPTIONS: Array<{ label: string; value: ExpressionFunctionName; help: string }> = [
  { label: "abs(x)", value: "abs", help: "绝对值。" },
  { label: "min(a, b)", value: "min", help: "取两个表达式中的较小值。" },
  { label: "max(a, b)", value: "max", help: "取两个表达式中的较大值。" },
  { label: "sum(x, n)", value: "sum", help: "最近 n 根 K 线的表达式求和。" },
  { label: "avg(x, n)", value: "avg", help: "最近 n 根 K 线的表达式均值。" },
  { label: "std(x, n)", value: "std", help: "最近 n 根 K 线的表达式标准差。" },
  { label: "highest(x, n)", value: "highest", help: "最近 n 根 K 线的表达式最大值。" },
  { label: "lowest(x, n)", value: "lowest", help: "最近 n 根 K 线的表达式最小值。" },
  { label: "change(x, n)", value: "change", help: "当前表达式值减去 n 根 K 线前的表达式值。" },
  { label: "pct_change(x, n)", value: "pct_change", help: "当前表达式值相对 n 根 K 线前表达式值的变化率。" },
  { label: "ema(x, n)", value: "ema", help: "最近 n 根 K 线表达式的指数移动平均，首值使用窗口第一项。" },
  { label: "slope(x, n)", value: "slope", help: "最近 n 根 K 线表达式对时间序号的线性回归斜率。" },
  { label: "zscore(x, n)", value: "zscore", help: "当前表达式相对最近 n 根 K 线均值的标准分。" },
  { label: "percentile_rank(x, n)", value: "percentile_rank", help: "当前表达式在最近 n 根 K 线中的分位排名，范围 0 到 1。" },
  { label: "drawdown_from_high(x, n)", value: "drawdown_from_high", help: "当前表达式相对最近 n 根 K 线最高值的回撤，口径为 x / highest(x, n) - 1。" },
];

const PREVIEW_METRICS: PreviewMetricConfig[] = [
  {
    key: "annualReturn",
    label: "年化收益",
    help: "将当前回测区间的累计收益折算成年化后的收益率，用来衡量策略长期收益能力。",
    strategyValue: (preview) => `${preview.annualReturn.toFixed(2)}%`,
    benchmarkValue: (preview) => `${preview.benchmarkAnnualReturn.toFixed(2)}%`,
  },
  {
    key: "totalReturn",
    label: "总收益",
    help: "从回测开始到结束，策略资金相对初始资金的累计收益率。",
    strategyValue: (preview) => `${preview.totalReturn.toFixed(2)}%`,
    benchmarkValue: (preview) => `${preview.benchmarkReturn.toFixed(2)}%`,
  },
  {
    key: "maxDrawdown",
    label: "最大回撤",
    help: "净值从历史最高点回落到最低点的最大跌幅，用来衡量策略最痛的时候会亏多少。",
    strategyValue: (preview) => `${preview.maxDrawdown.toFixed(2)}%`,
    benchmarkValue: (preview) => `${preview.benchmarkMaxDrawdown.toFixed(2)}%`,
  },
  {
    key: "volatility",
    label: "波动率",
    help: "按日收益率计算并年化后的净值波动水平，越高表示策略起伏越大。",
    strategyValue: (preview) => `${preview.volatility.toFixed(2)}%`,
    benchmarkValue: (preview) => `${preview.benchmarkVolatility.toFixed(2)}%`,
  },
  {
    key: "sharpe",
    label: "Sharpe",
    help: "单位波动换来的收益能力，通常越高越好。",
    strategyValue: (preview) => preview.sharpe.toFixed(2),
    benchmarkValue: (preview) => preview.benchmarkSharpe.toFixed(2),
  },
  {
    key: "winRate",
    label: "胜率",
    help: "已完成交易中盈利交易的占比，用来观察策略命中率。",
    strategyValue: (preview) => `${preview.winRate.toFixed(2)}%`,
    benchmarkValue: (preview) => `${preview.benchmarkWinRate.toFixed(2)}%`,
  },
  {
    key: "tradeCount",
    label: "交易次数",
    help: "回测区间内完成卖出的交易数量，帮助判断策略交易频率。",
    strategyValue: (preview) => String(preview.tradeCount),
    benchmarkValue: (preview) => String(preview.benchmarkTradeCount),
  },
];

function createId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function createCondition(): RuleCondition {
  return {
    id: createId("condition"),
    type: "condition",
    leftExpression: [{ type: "variable", name: "close" }],
    operator: ">",
    rightExpression: [{ type: "variable", name: "ma20" }],
  };
}

function createGroup(): RuleGroup {
  return {
    id: createId("group"),
    type: "group",
    logic: "and",
    children: [createCondition()],
  };
}

function createStrategyRule(scope: RuleScope, index = 1): StrategyRule {
  return {
    id: createId(`${scope}_rule`),
    name: scope === "entry" ? `买入规则 ${index}` : `卖出规则 ${index}`,
    action: {
      type: scope === "entry" ? "buy" : "sell",
      size: scope === "entry" ? 1 : 1,
    },
    conditions: createGroup(),
  };
}

export function createDefaultStrategyDslConfig(): StrategyDslConfig {
  return {
    entryRules: [createStrategyRule("entry")],
    exitRules: [createStrategyRule("exit")],
    risk: {
      forceCloseOnEnd: true,
      backtestStartDate: "2020-01-01",
      backtestEndDate: new Date().toISOString().slice(0, 10),
    },
  };
}

export function normalizeStrategyDslConfig(input?: Partial<StrategyDslConfig> | null): StrategyDslConfig {
  const defaults = createDefaultStrategyDslConfig();
  if (!input || typeof input !== "object") {
    return defaults;
  }

  const inputRisk = (input.risk ?? {}) as Partial<RiskBacktestConfig>;
  const risk: RiskBacktestConfig = {
    forceCloseOnEnd: inputRisk.forceCloseOnEnd ?? defaults.risk.forceCloseOnEnd,
    backtestStartDate: inputRisk.backtestStartDate ?? defaults.risk.backtestStartDate,
    backtestEndDate: inputRisk.backtestEndDate ?? defaults.risk.backtestEndDate,
  };
  const entryRules: StrategyRule[] = Array.isArray(input.entryRules) && input.entryRules.length
    ? input.entryRules.map((rule, index) => normalizeStrategyRule(rule, "entry", index + 1))
    : input.entry
      ? [{ ...createStrategyRule("entry"), name: "买入规则", action: { type: "buy", size: 1 }, conditions: input.entry }]
      : defaults.entryRules;
  const exitRules: StrategyRule[] = Array.isArray(input.exitRules) && input.exitRules.length
    ? input.exitRules.map((rule, index) => normalizeStrategyRule(rule, "exit", index + 1))
    : input.exit
      ? [{ ...createStrategyRule("exit"), name: "卖出规则", action: { type: "sell", size: 1 }, conditions: input.exit }]
      : defaults.exitRules;

  return {
    entryRules,
    exitRules,
    risk,
  };
}

function normalizeStrategyRule(rule: Partial<StrategyRule>, scope: RuleScope, index: number): StrategyRule {
  const fallback = createStrategyRule(scope, index);
  const actionType = scope === "entry" ? "buy" : "sell";
  return {
    id: rule.id || fallback.id,
    name: rule.name || fallback.name,
    action: {
      type: actionType,
      size: Number(rule.action?.size ?? fallback.action.size),
    },
    conditions: rule.conditions ?? fallback.conditions,
  };
}

export function RuleEngine({
  value,
  onChange,
  onPreview,
  previewLoading = false,
  previewResult,
  previewDisabled = false,
}: Props) {
  const normalizedValue = useMemo(() => normalizeStrategyDslConfig(value), [value]);
  const entrySummary = useMemo(() => summarizeRules(normalizedValue.entryRules), [normalizedValue.entryRules]);
  const exitSummary = useMemo(() => summarizeRules(normalizedValue.exitRules), [normalizedValue.exitRules]);

  const updateRules = (scope: RuleScope, nextRules: StrategyRule[]) => {
    onChange({
      ...normalizedValue,
      [scope === "entry" ? "entryRules" : "exitRules"]: nextRules,
    });
  };

  const updateRisk = <K extends keyof RiskBacktestConfig>(key: K, nextValue: RiskBacktestConfig[K]) => {
    onChange({
      ...normalizedValue,
      risk: {
        ...normalizedValue.risk,
        [key]: nextValue,
      },
    });
  };

  return (
    <div className="strategy-rule-engine">
      <Tabs
        className="strategy-rule-tabs"
        defaultActiveKey="entry"
        items={[
          {
            key: "entry",
            label: "买入规则",
            children: <RuleListEditor rules={normalizedValue.entryRules} scope="entry" onChange={(nextRules) => updateRules("entry", nextRules)} />,
          },
          {
            key: "exit",
            label: "卖出规则",
            children: <RuleListEditor rules={normalizedValue.exitRules} scope="exit" onChange={(nextRules) => updateRules("exit", nextRules)} />,
          },
          {
            key: "risk",
            label: "风控与回测",
            children: (
              <div className="strategy-risk-grid">
                <Card className="strategy-rule-card" size="small" title="风险参数">
                  <div className="strategy-risk-form">
                    <label className="strategy-risk-switch-row">
                      <span>
                        强制期末平仓
                        <Tooltip title="开启后，回测结束时若仍有持仓，会按最后一个交易日收盘价强制平仓并计入收益。">
                          <QuestionCircleOutlined className="strategy-preview-metric-help" />
                        </Tooltip>
                      </span>
                      <Switch checked={normalizedValue.risk.forceCloseOnEnd !== false} onChange={(checked) => updateRisk("forceCloseOnEnd", checked)} />
                    </label>
                  </div>
                </Card>

                <Card className="strategy-rule-card" size="small" title="回测区间">
                  <div className="strategy-risk-form">
                    <label>
                      <span>开始日期</span>
                      <Input type="date" value={normalizedValue.risk.backtestStartDate} onChange={(event) => updateRisk("backtestStartDate", event.target.value)} />
                    </label>
                    <label>
                      <span>结束日期</span>
                      <Input type="date" value={normalizedValue.risk.backtestEndDate} onChange={(event) => updateRisk("backtestEndDate", event.target.value)} />
                    </label>
                  </div>
                </Card>
              </div>
            ),
          },
          {
            key: "preview",
            label: "DSL 预览",
            children: (
              <div className="strategy-dsl-preview">
                <div className="strategy-dsl-main">
                  <Card className="strategy-rule-card" size="small" title="规则摘要">
                    <div className="strategy-rule-summary">
                      <Text>买入规则：{entrySummary}</Text>
                      <Text>卖出规则：{exitSummary}</Text>
                    </div>
                  </Card>
                  <Card className="strategy-rule-card" size="small" title="JSON DSL">
                    <pre>{JSON.stringify(normalizedValue, null, 2)}</pre>
                  </Card>
                </div>

                <Card
                  className="strategy-rule-card strategy-preview-card"
                  size="small"
                  title="收益预览"
                  extra={
                    <Button type="primary" size="small" loading={previewLoading} disabled={previewDisabled} onClick={onPreview}>
                      预览收益
                    </Button>
                  }
                >
                  <div className="strategy-preview-metrics">
                    {PREVIEW_METRICS.map((metric) => (
                      <div key={metric.key} className="strategy-preview-metric-card">
                        <div className="strategy-preview-metric-header">
                          <span>{metric.label}</span>
                          <Tooltip title={metric.help}>
                            <QuestionCircleOutlined className="strategy-preview-metric-help" />
                          </Tooltip>
                        </div>
                        <div className="strategy-preview-metric-values">
                          <div>
                            <small>策略</small>
                            <strong>{previewResult ? metric.strategyValue(previewResult) : "--"}</strong>
                          </div>
                          <div>
                            <small>买入持有基准</small>
                            <strong>{previewResult ? metric.benchmarkValue(previewResult) : "--"}</strong>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {previewResult ? <StrategyPreviewChart preview={previewResult} /> : null}

                  <div className="strategy-preview-range">
                    <Text type="secondary">
                      回测区间：{previewResult?.dateRange.start ?? "--"} 至 {previewResult?.dateRange.end ?? "--"}
                    </Text>
                  </div>

                  <Table
                    className="strategy-preview-trades"
                    size="small"
                    pagination={false}
                    scroll={{ y: 240 }}
                    rowKey={(record) => `${record.date}_${record.side}_${record.price}`}
                    dataSource={previewResult?.trades ?? []}
                    locale={{
                      emptyText: <EmptyState title="暂无成交记录" compact />,
                    }}
                    columns={[
                      { title: "日期", dataIndex: "date", width: 120 },
                      {
                        title: "方向",
                        dataIndex: "side",
                        width: 80,
                        render: (value: "buy" | "sell") => <Tag color={value === "buy" ? "blue" : "volcano"}>{value === "buy" ? "买入" : "卖出"}</Tag>,
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
                      },
                    ]}
                  />
                </Card>
              </div>
            ),
          },
          {
            key: "nextAction",
            label: "未来操作",
            children: (
              <div className="strategy-dsl-preview">
                <Card className="strategy-rule-card" size="small" title="当前持仓状态">
                  <div className="strategy-preview-metrics strategy-preview-metrics-single">
                    <div className="strategy-preview-metric-card">
                      <div className="strategy-preview-metric-header">
                        <span>持仓状态</span>
                        <Tooltip title="根据当前策略回测到最后一个交易日时的真实持仓状态推导。">
                          <QuestionCircleOutlined className="strategy-preview-metric-help" />
                        </Tooltip>
                      </div>
                      <div className="strategy-preview-next-action-grid">
                        <div>
                          <small>状态</small>
                          <strong>{previewResult?.currentPosition.status ?? "--"}</strong>
                        </div>
                        <div>
                          <small>持仓数量</small>
                          <strong>{previewResult ? previewResult.currentPosition.shares.toFixed(6) : "--"}</strong>
                        </div>
                        <div>
                          <small>持仓均价</small>
                          <strong>{previewResult?.currentPosition.entryPrice != null ? previewResult.currentPosition.entryPrice.toFixed(4) : "--"}</strong>
                        </div>
                        <div>
                          <small>当前仓位</small>
                          <strong>{previewResult ? `${previewResult.currentPosition.positionRatio.toFixed(2)}%` : "--"}</strong>
                        </div>
                        <div>
                          <small>持仓天数</small>
                          <strong>{previewResult?.currentPosition.holdingDays ?? "--"}</strong>
                        </div>
                        <div>
                          <small>浮动收益率</small>
                          <strong>
                            {previewResult?.currentPosition.unrealizedReturn != null
                              ? `${previewResult.currentPosition.unrealizedReturn.toFixed(2)}%`
                              : "--"}
                          </strong>
                        </div>
                      </div>
                    </div>
                  </div>
                </Card>

                <Card className="strategy-rule-card" size="small" title="下一个交易日建议">
                  <div className="strategy-preview-metrics strategy-preview-metrics-single">
                    <div className="strategy-preview-metric-card">
                      <div className="strategy-preview-metric-header">
                        <span>建议动作</span>
                        <Tooltip title="根据回测最后一个交易日收盘后的信号状态，推导下一个交易日开盘时应执行的动作。">
                          <QuestionCircleOutlined className="strategy-preview-metric-help" />
                        </Tooltip>
                      </div>
                      <div className="strategy-preview-next-action-block">
                        <strong>{previewResult?.nextAction.action ?? "--"}</strong>
                        <Text type="secondary">{previewResult?.nextAction.reason ?? "请先执行收益预览。"}</Text>
                      </div>
                    </div>
                  </div>
                </Card>
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}

export function RuleReadonlyPreview({ value, compact = false }: { value?: StrategyDslConfig | null; compact?: boolean }) {
  if (!value) {
    return <EmptyState title="暂无规则内容" compact />;
  }
  const normalizedValue = normalizeStrategyDslConfig(value);
  if (!normalizedValue.entryRules.length || !normalizedValue.exitRules.length) {
    return <EmptyState title="暂无规则内容" compact />;
  }

  return (
    <div className={compact ? "strategy-rule-readonly strategy-rule-readonly-compact" : "strategy-rule-readonly"}>
      <RuleReadonlySection title="买入规则" rules={normalizedValue.entryRules} />
      <RuleReadonlySection title="卖出规则" rules={normalizedValue.exitRules} />
    </div>
  );
}

function RuleReadonlySection({ title, rules }: { title: string; rules: StrategyRule[] }) {
  return (
    <div className="strategy-rule-readonly-section">
      <div className="strategy-rule-readonly-title">
        <span>{title}</span>
        <Tag color="blue">按顺序命中第一条</Tag>
      </div>
      <div className="strategy-rule-readonly-expression">
        {rules.map((rule, index) => (
          <div key={rule.id || index}>
            {index + 1}. {rule.name || "未命名规则"}（{rule.action.type === "buy" ? "买入" : "卖出"} {formatActionSize(rule.action.size)}）：
            {summarizeGroup(rule.conditions) || "暂无条件"}
          </div>
        ))}
      </div>
    </div>
  );
}

function RuleListEditor({ rules, scope, onChange }: { rules: StrategyRule[]; scope: RuleScope; onChange: (nextRules: StrategyRule[]) => void }) {
  const safeRules = rules.length ? rules : [createStrategyRule(scope)];

  const updateRule = (ruleId: string, nextRule: StrategyRule) => {
    onChange(safeRules.map((rule) => (rule.id === ruleId ? nextRule : rule)));
  };

  const removeRule = (ruleId: string) => {
    const nextRules = safeRules.filter((rule) => rule.id !== ruleId);
    onChange(nextRules.length ? nextRules : [createStrategyRule(scope)]);
  };

  const moveRule = (ruleId: string, direction: -1 | 1) => {
    const index = safeRules.findIndex((rule) => rule.id === ruleId);
    const targetIndex = index + direction;
    if (index < 0 || targetIndex < 0 || targetIndex >= safeRules.length) {
      return;
    }
    const nextRules = [...safeRules];
    const [item] = nextRules.splice(index, 1);
    nextRules.splice(targetIndex, 0, item);
    onChange(nextRules);
  };

  return (
    <div className="strategy-rule-list">
      <div className="strategy-rule-list-hint">按顺序判断优先级，命中第一条后执行对应仓位动作。</div>
      {safeRules.map((rule, index) => (
        <Card
          key={rule.id}
          className="strategy-rule-card strategy-rule-item-card"
          size="small"
          title={`${scope === "entry" ? "买入" : "卖出"}规则 ${index + 1}`}
          extra={
            <div className="strategy-rule-group-toolbar">
              <Button size="small" disabled={index === 0} onClick={() => moveRule(rule.id, -1)}>
                上移
              </Button>
              <Button size="small" disabled={index === safeRules.length - 1} onClick={() => moveRule(rule.id, 1)}>
                下移
              </Button>
              <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => removeRule(rule.id)} />
            </div>
          }
        >
          <div className="strategy-rule-action-row">
            <label>
              <span>规则名称</span>
              <Input value={rule.name} onChange={(event) => updateRule(rule.id, { ...rule, name: event.target.value })} />
            </label>
            <label>
              <span>动作</span>
              <Input value={scope === "entry" ? "买入" : "卖出"} disabled />
            </label>
            <label>
              <span>仓位比例</span>
              <InputNumber
                min={0.01}
                max={1}
                step={0.01}
                value={rule.action.size}
                formatter={(value) => `${Number(value ?? 0) * 100}%`}
                parser={(value) => Number(String(value || "").replace("%", "")) / 100}
                onChange={(next) =>
                  updateRule(rule.id, {
                    ...rule,
                    action: { type: scope === "entry" ? "buy" : "sell", size: Number(next ?? 0) },
                  })
                }
              />
            </label>
          </div>
          <RuleGroupEditor
            value={rule.conditions}
            scope={scope}
            depth={0}
            onChange={(nextGroup) => updateRule(rule.id, { ...rule, conditions: nextGroup })}
          />
        </Card>
      ))}
      <Button
        size="small"
        className="strategy-rule-action-button"
        icon={<PlusOutlined />}
        onClick={() => onChange([...safeRules, createStrategyRule(scope, safeRules.length + 1)])}
      >
        添加{scope === "entry" ? "买入" : "卖出"}规则
      </Button>
    </div>
  );
}

type GroupEditorProps = {
  value: RuleGroup;
  scope: RuleScope;
  depth: number;
  onChange: (nextGroup: RuleGroup) => void;
  onDelete?: () => void;
};

function RuleGroupEditor({ value, scope, depth, onChange, onDelete }: GroupEditorProps) {
  const availableFields = FIELD_OPTIONS.filter((item) => item.scopes.includes(scope));

  const updateChild = (childId: string, nextNode: RuleNode) => {
    onChange({
      ...value,
      children: value.children.map((child) => (child.id === childId ? nextNode : child)),
    });
  };

  const removeChild = (childId: string) => {
    const nextChildren = value.children.filter((child) => child.id !== childId);
    onChange({
      ...value,
      children: nextChildren.length ? nextChildren : [createCondition()],
    });
  };

  return (
    <Card
      className={`strategy-rule-group strategy-rule-group-depth-${depth}`}
      size="small"
      title={
        <div className="strategy-rule-group-title">
          <strong>条件组 {depth + 1}</strong>
          <span>{value.children.length} 个子条件</span>
        </div>
      }
      extra={
        <div className="strategy-rule-group-toolbar">
          <Tag color={value.logic === "and" ? "blue" : "purple"}>{value.logic === "and" ? "全部满足" : "任一满足"}</Tag>
          <Radio.Group
            className="strategy-rule-logic-toggle"
            size="small"
            optionType="button"
            buttonStyle="solid"
            options={LOGIC_OPTIONS}
            value={value.logic}
            onChange={(event) => onChange({ ...value, logic: event.target.value as RuleLogic })}
          />
          {onDelete ? <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={onDelete} /> : null}
        </div>
      }
    >
      <div className="strategy-rule-group-body">
        {value.children.map((child) =>
          child.type === "condition" ? (
            <RuleConditionRow
              key={child.id}
              value={child}
              availableFields={availableFields}
              onChange={(nextCondition) => updateChild(child.id, nextCondition)}
              onDelete={() => removeChild(child.id)}
            />
          ) : (
            <RuleGroupEditor
              key={child.id}
              value={child}
              scope={scope}
              depth={depth + 1}
              onChange={(nextGroup) => updateChild(child.id, nextGroup)}
              onDelete={() => removeChild(child.id)}
            />
          ),
        )}
      </div>

      <div className="strategy-rule-group-actions">
        <Button
          size="small"
          className="strategy-rule-action-button"
          icon={<PlusOutlined />}
          onClick={() => onChange({ ...value, children: [...value.children, createCondition()] })}
        >
          添加条件
        </Button>
        <Button
          size="small"
          className="strategy-rule-action-button"
          onClick={() => onChange({ ...value, children: [...value.children, createGroup()] })}
          disabled={depth >= 2}
        >
          添加条件组
        </Button>
      </div>
    </Card>
  );
}

type ConditionRowProps = {
  value: RuleCondition;
  availableFields: RuleFieldOption[];
  onChange: (nextCondition: RuleCondition) => void;
  onDelete: () => void;
};

function RuleConditionRow({ value, availableFields, onChange, onDelete }: ConditionRowProps) {
  return (
    <div className="strategy-condition-row">
      <div className="strategy-condition-cell">
        <span className="strategy-condition-label">左表达式</span>
        <ExpressionEditor value={value.leftExpression} availableFields={availableFields} onChange={(next) => onChange({ ...value, leftExpression: next })} />
      </div>
      <div className="strategy-condition-cell">
        <span className="strategy-condition-label">运算符</span>
        <Select className="strategy-condition-operator" options={OPERATOR_OPTIONS} value={value.operator} onChange={(next) => onChange({ ...value, operator: next })} />
      </div>
      <div className="strategy-condition-cell">
        <span className="strategy-condition-label">右表达式</span>
        <ExpressionEditor value={value.rightExpression} availableFields={availableFields} onChange={(next) => onChange({ ...value, rightExpression: next })} />
      </div>
      <div className="strategy-condition-remove">
        <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={onDelete} />
      </div>
    </div>
  );
}

type ExpressionEditorProps = {
  value: ExpressionToken[];
  availableFields: RuleFieldOption[];
  onChange: (nextValue: ExpressionToken[]) => void;
};

function ExpressionEditor({ value, availableFields, onChange }: ExpressionEditorProps) {
  const tokens = Array.isArray(value) ? value : [];
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [draftToken, setDraftToken] = useState<ExpressionToken | null>(null);
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [dragPreviewIndex, setDragPreviewIndex] = useState<number | null>(null);

  const openAddModal = () => {
    setEditingIndex(null);
    setDraftToken({ type: "variable", name: availableFields[0]?.value ?? "close" });
  };

  const openEditModal = (index: number) => {
    setEditingIndex(index);
    setDraftToken(cloneExpressionToken(tokens[index]));
  };

  const closeModal = () => {
    setEditingIndex(null);
    setDraftToken(null);
  };

  const saveDraft = () => {
    if (!draftToken) {
      return;
    }
    if (editingIndex == null) {
      onChange([...tokens, draftToken]);
    } else {
      onChange(tokens.map((token, index) => (index === editingIndex ? draftToken : token)));
    }
    closeModal();
  };

  const removeToken = (index: number) => {
    onChange(tokens.filter((_, itemIndex) => itemIndex !== index));
  };

  const moveToken = (fromIndex: number, targetIndex: number) => {
    if (fromIndex < 0 || targetIndex < 0 || fromIndex >= tokens.length || targetIndex >= tokens.length) {
      return;
    }
    const toIndex = fromIndex < targetIndex ? targetIndex - 1 : targetIndex;
    if (fromIndex === toIndex) {
      return;
    }
    const nextTokens = [...tokens];
    const [movedToken] = nextTokens.splice(fromIndex, 1);
    nextTokens.splice(toIndex, 0, movedToken);
    onChange(nextTokens);
  };

  return (
    <div className="strategy-expression-editor">
      <div className="strategy-expression-token-list">
        {tokens.length ? (
          tokens.map((token, index) => (
            <ExpressionTokenView
              key={`${token.type}_${index}`}
              index={index}
              token={token}
              availableFields={availableFields}
              issue={getTokenIssue(tokens, token, index, availableFields)}
              dragging={draggingIndex === index}
              dropBefore={dragPreviewIndex === index && draggingIndex !== null && draggingIndex !== index}
              onDragStart={() => {
                setDraggingIndex(index);
                setDragPreviewIndex(index);
              }}
              onDragPreview={(targetIndex) => {
                if (draggingIndex != null && draggingIndex !== targetIndex) {
                  setDragPreviewIndex(targetIndex);
                }
              }}
              onDragEnd={() => {
                setDraggingIndex(null);
                setDragPreviewIndex(null);
              }}
              onDrop={(targetIndex) => {
                if (draggingIndex != null) {
                  moveToken(draggingIndex, targetIndex);
                  setDraggingIndex(null);
                  setDragPreviewIndex(null);
                }
              }}
              onEdit={() => openEditModal(index)}
              onRemove={() => removeToken(index)}
            />
          ))
        ) : (
          <span className="strategy-expression-empty">请添加变量、数字或函数</span>
        )}
        {dragPreviewIndex === tokens.length && draggingIndex !== null ? <span className="strategy-expression-drop-preview strategy-expression-drop-preview-end" /> : null}
        <Button size="small" type="primary" className="strategy-expression-add-button" icon={<PlusOutlined />} onClick={openAddModal}>
          添加
        </Button>
      </div>

      <Modal
        title={editingIndex == null ? "添加表达式片段" : "编辑表达式片段"}
        open={Boolean(draftToken)}
        onCancel={closeModal}
        onOk={saveDraft}
        okText="保存"
        cancelText="取消"
        width={720}
        destroyOnHidden
      >
        {draftToken ? <ExpressionTokenForm token={draftToken} availableFields={availableFields} onChange={setDraftToken} /> : null}
      </Modal>
    </div>
  );
}

type ExpressionTokenViewProps = {
  index: number;
  token: ExpressionToken;
  availableFields: RuleFieldOption[];
  issue?: string;
  dragging: boolean;
  dropBefore: boolean;
  onDragStart: () => void;
  onDragPreview: (targetIndex: number) => void;
  onDragEnd: () => void;
  onDrop: (targetIndex: number) => void;
  onEdit: () => void;
  onRemove: () => void;
};

function ExpressionTokenView({
  index,
  token,
  availableFields,
  issue,
  dragging,
  dropBefore,
  onDragStart,
  onDragPreview,
  onDragEnd,
  onDrop,
  onEdit,
  onRemove,
}: ExpressionTokenViewProps) {
  const content = (
    <div className="strategy-expression-token-popover">
      <div>
        <strong>{formatTokenLabel(token, availableFields)}</strong>
        {issue ? <Text type="danger">{issue}</Text> : <Text type="secondary">拖拽可调整顺序</Text>}
      </div>
      <div>
        <Button size="small" type="primary" onClick={onEdit}>
          编辑
        </Button>
        <Button size="small" danger onClick={onRemove}>
          删除
        </Button>
      </div>
    </div>
  );

  return (
    <Popover trigger="hover" placement="top" content={content}>
      <span
        className={`strategy-expression-token ${getTokenClassName(token)}${issue ? " strategy-expression-token-error" : ""}${
          dragging ? " strategy-expression-token-dragging" : ""
        }${dropBefore ? " strategy-expression-token-drop-before" : ""}`}
        draggable
        onDragStart={(event) => {
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", String(index));
          onDragStart();
        }}
        onDragOver={(event) => {
          event.preventDefault();
          event.dataTransfer.dropEffect = "move";
          const target = event.currentTarget;
          const rect = target.getBoundingClientRect();
          const afterCurrent = event.clientX > rect.left + rect.width / 2;
          onDragPreview(afterCurrent ? index + 1 : index);
        }}
        onDrop={(event) => {
          event.preventDefault();
          onDrop(index);
        }}
        onDragEnd={onDragEnd}
      >
        <span className="strategy-expression-token-grip">⋮⋮</span>
        {issue ? <span className="strategy-expression-token-warning">!</span> : null}
        <strong>{formatTokenLabel(token, availableFields)}</strong>
      </span>
    </Popover>
  );
}

type ExpressionTokenFormProps = {
  token: ExpressionToken;
  availableFields: RuleFieldOption[];
  onChange: (nextToken: ExpressionToken) => void;
};

function ExpressionTokenForm({ token, availableFields, onChange }: ExpressionTokenFormProps) {
  const tokenType = token.type;
  const fieldOptions = availableFields.map((item) => ({ label: renderFieldOptionLabel(item), value: item.value }));

  const changeType = (nextType: ExpressionToken["type"]) => {
    if (nextType === "variable") {
      onChange({ type: "variable", name: availableFields[0]?.value ?? "close" });
    } else if (nextType === "number") {
      onChange({ type: "number", value: 1 });
    } else if (nextType === "operator") {
      onChange({ type: "operator", value: "+" });
    } else if (nextType === "groupStart") {
      onChange({ type: "groupStart" });
    } else if (nextType === "groupEnd") {
      onChange({ type: "groupEnd" });
    } else {
      onChange(createFunctionToken("avg"));
    }
  };

  return (
    <div className="strategy-expression-modal-form">
      <label>
        <span>片段类型</span>
        <Select
          value={tokenType}
          onChange={changeType}
          options={[
            { label: "变量", value: "variable" },
            { label: "数字", value: "number" },
            { label: "运算符", value: "operator" },
            { label: "左括号", value: "groupStart" },
            { label: "右括号", value: "groupEnd" },
            { label: "函数", value: "function" },
          ]}
        />
      </label>

      {token.type === "variable" ? (
        <>
          <label>
            <span>变量</span>
            <Select options={fieldOptions} value={token.name} onChange={(name) => onChange({ ...token, name: name as unknown as RuleFieldValue })} />
          </label>
          <label>
            <span>历史偏移</span>
            <InputNumber min={-10000} max={0} step={1} value={token.offset ?? 0} onChange={(offset) => onChange({ ...token, offset: Number(offset ?? 0) })} />
          </label>
        </>
      ) : null}

      {token.type === "number" ? (
        <label>
          <span>数值</span>
          <InputNumber value={token.value} onChange={(value) => onChange({ ...token, value: Number(value ?? 0) })} />
        </label>
      ) : null}

      {token.type === "operator" ? (
        <label>
          <span>运算符</span>
          <Select
            options={EXPRESSION_OPERATOR_OPTIONS}
            value={token.value}
            onChange={(value) => onChange({ ...token, value: value as unknown as ExpressionOperator })}
          />
        </label>
      ) : null}

      {token.type === "function" ? <FunctionTokenForm token={token} availableFields={availableFields} onChange={onChange} /> : null}
    </div>
  );
}

type FunctionTokenFormProps = {
  token: Extract<ExpressionToken, { type: "function" }>;
  availableFields: RuleFieldOption[];
  onChange: (nextToken: ExpressionToken) => void;
};

function FunctionTokenForm({ token, availableFields, onChange }: FunctionTokenFormProps) {
  const setFunctionName = (name: ExpressionFunctionName) => {
    onChange(createFunctionToken(name));
  };

  const updateArg = (argIndex: number, nextArg: ExpressionToken[]) => {
    onChange({ ...token, args: token.args.map((arg, index) => (index === argIndex ? nextArg : arg)) });
  };

  return (
    <>
      <label>
        <span>函数</span>
        <Select
          value={token.name}
          options={FUNCTION_OPTIONS.map((item) => ({ label: renderFunctionOptionLabel(item), value: item.value }))}
          onChange={(name) => setFunctionName(name as unknown as ExpressionFunctionName)}
        />
      </label>
      <div className="strategy-expression-function-args">
        {token.args.map((arg, index) => (
          <div key={index} className="strategy-expression-function-arg">
            <span>参数 {index + 1}</span>
            <ExpressionEditor value={arg} availableFields={availableFields} onChange={(nextArg) => updateArg(index, nextArg)} />
          </div>
        ))}
      </div>
    </>
  );
}

function cloneExpressionToken(token: ExpressionToken): ExpressionToken {
  return JSON.parse(JSON.stringify(token)) as ExpressionToken;
}

function getTokenClassName(token: ExpressionToken) {
  if (token.type === "variable") {
    return "strategy-expression-token-variable";
  }
  if (token.type === "number") {
    return "strategy-expression-token-number";
  }
  if (token.type === "operator") {
    return "strategy-expression-token-operator";
  }
  if (token.type === "groupStart" || token.type === "groupEnd") {
    return "strategy-expression-token-group";
  }
  return "strategy-expression-token-function";
}

function getTokenIssue(tokens: ExpressionToken[], token: ExpressionToken, index: number, availableFields: RuleFieldOption[]) {
  const previousToken = tokens[index - 1];
  const nextToken = tokens[index + 1];
  const valueTokenTypes = new Set<ExpressionToken["type"]>(["variable", "number", "function"]);
  const previousIsValue = previousToken ? valueTokenTypes.has(previousToken.type) || previousToken.type === "groupEnd" : false;
  const nextIsValue = nextToken ? valueTokenTypes.has(nextToken.type) || nextToken.type === "groupStart" : false;

  if (token.type === "variable") {
    if (!availableFields.some((field) => field.value === token.name)) {
      return "当前规则不可使用这个变量";
    }
    if ((token.offset ?? 0) > 0) {
      return "不允许引用未来数据";
    }
    if (previousIsValue) {
      return "前面缺少运算符";
    }
  }
  if (token.type === "number" || token.type === "function") {
    if (previousIsValue) {
      return "前面缺少运算符";
    }
  }
  if (token.type === "operator") {
    if (!previousIsValue) {
      return "运算符前缺少值";
    }
    if (!nextIsValue) {
      return "运算符后缺少值";
    }
  }
  if (token.type === "groupStart" && previousIsValue) {
    return "左括号前缺少运算符";
  }
  if (token.type === "groupEnd" && (!previousIsValue || nextIsValue)) {
    return "右括号位置不正确";
  }
  return undefined;
}

function formatTokenLabel(token: ExpressionToken, availableFields: RuleFieldOption[]) {
  if (token.type === "variable") {
    const label = availableFields.find((item) => item.value === token.name)?.label ?? token.name;
    return token.offset ? `${label}[${token.offset}]` : label;
  }
  if (token.type === "number") {
    return String(token.value);
  }
  if (token.type === "operator") {
    return token.value;
  }
  if (token.type === "groupStart") {
    return "(";
  }
  if (token.type === "groupEnd") {
    return ")";
  }
  return formatFunctionToken(token, availableFields);
}

function createFunctionToken(name: ExpressionFunctionName): ExpressionToken {
  if (name === "abs") {
    return { type: "function", name, args: [[{ type: "variable", name: "close" }]] };
  }
  if (name === "min" || name === "max") {
    return { type: "function", name, args: [[{ type: "variable", name: "close" }], [{ type: "variable", name: "ma20" }]] };
  }
  return { type: "function", name, args: [[{ type: "variable", name: "close" }], [{ type: "number", value: 20 }]] };
}

function renderFunctionOptionLabel(option: { label: string; help: string }): ReactNode {
  return (
    <span className="strategy-field-option-label">
      <span>{option.label}</span>
      <Tooltip title={option.help}>
        <QuestionCircleOutlined className="strategy-preview-metric-help" />
      </Tooltip>
    </span>
  );
}

function formatFunctionToken(token: Extract<ExpressionToken, { type: "function" }>, availableFields: RuleFieldOption[]) {
  return `${token.name}(${token.args.map((arg) => formatExpression(arg, availableFields)).join(", ")})`;
}

function renderFieldOptionLabel(option: RuleFieldOption): ReactNode {
  return (
    <span className="strategy-field-option-label">
      <span>{option.label}</span>
      <Tag>{option.category}</Tag>
      <Tooltip title={option.help}>
        <QuestionCircleOutlined className="strategy-preview-metric-help" />
      </Tooltip>
    </span>
  );
}

function summarizeGroup(group: RuleGroup): string {
  const joiner = group.logic === "and" ? " 且 " : " 或 ";
  return group.children
    .map((child) => {
      if (child.type === "group") {
        return `(${summarizeGroup(child)})`;
      }
      const operatorLabel = OPERATOR_OPTIONS.find((item) => item.value === child.operator)?.label ?? child.operator;
      return `${formatExpression(child.leftExpression, FIELD_OPTIONS)} ${operatorLabel} ${formatExpression(child.rightExpression, FIELD_OPTIONS)}`;
    })
    .join(joiner);
}

function summarizeRules(rules: StrategyRule[]): string {
  return rules
    .map((rule, index) => `${index + 1}. ${rule.name || "未命名规则"}（${rule.action.type === "buy" ? "买入" : "卖出"} ${formatActionSize(rule.action.size)}）`)
    .join("；");
}

function formatActionSize(size: number | undefined): string {
  return `${Math.round(Number(size ?? 0) * 10000) / 100}%`;
}

function formatExpression(tokens: ExpressionToken[] | undefined, availableFields: RuleFieldOption[]): string {
  if (!Array.isArray(tokens) || !tokens.length) {
    return "-";
  }
  return tokens
    .map((token) => {
      if (token.type === "variable") {
        const label = availableFields.find((item) => item.value === token.name)?.label ?? token.name;
        return token.offset ? `${label}[${token.offset}]` : label;
      }
      if (token.type === "number") {
        return String(token.value);
      }
      if (token.type === "operator") {
        return token.value;
      }
      if (token.type === "groupStart") {
        return "(";
      }
      if (token.type === "groupEnd") {
        return ")";
      }
      return formatFunctionToken(token, availableFields);
    })
    .join(" ");
}
