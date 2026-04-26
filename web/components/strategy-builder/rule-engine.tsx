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
  { label: "5日收益率", value: "return_5d", scopes: ["entry", "exit"], category: "动量因子", help: "相对 5 个交易日前收盘价的累计收益率，口径为 close / close[-5] - 1。" },
  { label: "20日收益率", value: "return_20d", scopes: ["entry", "exit"], category: "动量因子", help: "相对 20 个交易日前收盘价的累计收益率，口径为 close / close[-20] - 1。" },
  { label: "60日收益率", value: "return_60d", scopes: ["entry", "exit"], category: "动量因子", help: "相对 60 个交易日前收盘价的累计收益率，口径为 close / close[-60] - 1。" },
  { label: "量比(5日)", value: "volume_ratio_5", scopes: ["entry", "exit"], category: "量价因子", help: "当日成交量相对 5 日平均成交量的倍数。" },
  { label: "量比(20日)", value: "volume_ratio_20", scopes: ["entry", "exit"], category: "量价因子", help: "当日成交量相对 20 日平均成交量的倍数。" },
  { label: "ATR14", value: "atr14", scopes: ["entry", "exit"], category: "波动因子", help: "14 日平均真实波幅，衡量价格波动强度。" },
  { label: "20日波动率", value: "volatility_20d", scopes: ["entry", "exit"], category: "波动因子", help: "最近 20 个交易日日收益率标准差，不做年化。" },
  { label: "20日区间位置", value: "close_pct_of_20d_range", scopes: ["entry", "exit"], category: "位置因子", help: "收盘价位于最近 20 日高低区间中的相对位置，范围通常在 0 到 1。" },
  { label: "60日区间位置", value: "close_pct_of_60d_range", scopes: ["entry", "exit"], category: "位置因子", help: "收盘价位于最近 60 日高低区间中的相对位置，范围通常在 0 到 1。" },
  { label: "距20日高点", value: "distance_to_20d_high", scopes: ["entry", "exit"], category: "位置因子", help: "收盘价相对最近 20 日最高价的偏离率，口径为 close / high20 - 1。" },
  { label: "距20日低点", value: "distance_to_20d_low", scopes: ["entry", "exit"], category: "位置因子", help: "收盘价相对最近 20 日最低价的偏离率，口径为 close / low20 - 1。" },
  { label: "实体占比", value: "body_pct", scopes: ["entry", "exit"], category: "K线形态", help: "K 线实体长度相对开盘价的比例，口径为 |close - open| / open。" },
  { label: "上影线占比", value: "upper_shadow_pct", scopes: ["entry", "exit"], category: "K线形态", help: "上影线长度相对开盘价的比例。" },
  { label: "下影线占比", value: "lower_shadow_pct", scopes: ["entry", "exit"], category: "K线形态", help: "下影线长度相对开盘价的比例。" },
  { label: "向上跳空", value: "gap_up", scopes: ["entry", "exit"], category: "K线形态", help: "若当日开盘价高于前一日最高价则记为 1，否则为 0。" },
  { label: "向下跳空", value: "gap_down", scopes: ["entry", "exit"], category: "K线形态", help: "若当日开盘价低于前一日最低价则记为 1，否则为 0。" },
  { label: "持仓收益率", value: "position_return", scopes: ["exit"], category: "持仓状态", help: "当前收盘价相对持仓成本的收益率。" },
  { label: "持仓天数", value: "holding_days", scopes: ["exit"], category: "持仓状态", help: "从首次建仓到当前 K 线为止已持有的交易日数量。" },
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

export function createDefaultStrategyDslConfig(): StrategyDslConfig {
  return {
    entry: createGroup(),
    exit: createGroup(),
    risk: {
      initialCapital: 100000,
      positionSize: 1,
      stopLoss: 0.08,
      takeProfit: 0.2,
      minAddPositionInterval: 3,
      maxHoldingDays: 30,
      forceCloseOnEnd: true,
      backtestStartDate: "2020-01-01",
      backtestEndDate: new Date().toISOString().slice(0, 10),
    },
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
  const entrySummary = useMemo(() => summarizeGroup(value.entry), [value.entry]);
  const exitSummary = useMemo(() => summarizeGroup(value.exit), [value.exit]);

  const updateGroup = (scope: RuleScope, nextGroup: RuleGroup) => {
    onChange({
      ...value,
      [scope]: nextGroup,
    });
  };

  const updateRisk = <K extends keyof RiskBacktestConfig>(key: K, nextValue: RiskBacktestConfig[K]) => {
    onChange({
      ...value,
      risk: {
        ...value.risk,
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
            children: <RuleGroupEditor value={value.entry} scope="entry" depth={0} onChange={(nextGroup) => updateGroup("entry", nextGroup)} />,
          },
          {
            key: "exit",
            label: "卖出规则",
            children: <RuleGroupEditor value={value.exit} scope="exit" depth={0} onChange={(nextGroup) => updateGroup("exit", nextGroup)} />,
          },
          {
            key: "risk",
            label: "风控与回测",
            children: (
              <div className="strategy-risk-grid">
                <Card className="strategy-rule-card" size="small" title="风险参数">
                  <div className="strategy-risk-form">
                    <label>
                      <span>初始资金</span>
                      <InputNumber min={0} value={value.risk.initialCapital} onChange={(next) => updateRisk("initialCapital", Number(next ?? 0))} />
                    </label>
                    <label>
                      <span>每次买入仓位</span>
                      <InputNumber min={0} max={1} step={0.1} value={value.risk.positionSize} onChange={(next) => updateRisk("positionSize", Number(next ?? 0))} />
                    </label>
                    <label>
                      <span>止损比例</span>
                      <InputNumber min={0} max={1} step={0.01} value={value.risk.stopLoss} onChange={(next) => updateRisk("stopLoss", Number(next ?? 0))} />
                    </label>
                    <label>
                      <span>止盈比例</span>
                      <InputNumber min={0} max={2} step={0.01} value={value.risk.takeProfit} onChange={(next) => updateRisk("takeProfit", Number(next ?? 0))} />
                    </label>
                    <label>
                      <span>最小加仓间隔</span>
                      <InputNumber min={0} step={1} value={value.risk.minAddPositionInterval ?? 3} onChange={(next) => updateRisk("minAddPositionInterval", Number(next ?? 0))} />
                    </label>
                    <label>
                      <span>最大持仓天数</span>
                      <InputNumber min={1} value={value.risk.maxHoldingDays} onChange={(next) => updateRisk("maxHoldingDays", Number(next ?? 1))} />
                    </label>
                    <label className="strategy-risk-switch-row">
                      <span>
                        强制期末平仓
                        <Tooltip title="开启后，回测结束时若仍有持仓，会按最后一个交易日收盘价强制平仓并计入收益。">
                          <QuestionCircleOutlined className="strategy-preview-metric-help" />
                        </Tooltip>
                      </span>
                      <Switch checked={value.risk.forceCloseOnEnd !== false} onChange={(checked) => updateRisk("forceCloseOnEnd", checked)} />
                    </label>
                  </div>
                </Card>

                <Card className="strategy-rule-card" size="small" title="回测区间">
                  <div className="strategy-risk-form">
                    <label>
                      <span>开始日期</span>
                      <Input type="date" value={value.risk.backtestStartDate} onChange={(event) => updateRisk("backtestStartDate", event.target.value)} />
                    </label>
                    <label>
                      <span>结束日期</span>
                      <Input type="date" value={value.risk.backtestEndDate} onChange={(event) => updateRisk("backtestEndDate", event.target.value)} />
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
                    <pre>{JSON.stringify(value, null, 2)}</pre>
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
                            <small>持续持有</small>
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
  if (!value?.entry || !value?.exit) {
    return <EmptyState title="暂无规则内容" compact />;
  }

  return (
    <div className={compact ? "strategy-rule-readonly strategy-rule-readonly-compact" : "strategy-rule-readonly"}>
      <RuleReadonlySection title="买入规则" group={value.entry} />
      <RuleReadonlySection title="卖出规则" group={value.exit} />
    </div>
  );
}

function RuleReadonlySection({ title, group }: { title: string; group: RuleGroup }) {
  return (
    <div className="strategy-rule-readonly-section">
      <div className="strategy-rule-readonly-title">
        <span>{title}</span>
        <Tag color={group.logic === "and" ? "blue" : "gold"}>{group.logic === "and" ? "满足全部条件" : "满足任一条件"}</Tag>
      </div>
      <div className="strategy-rule-readonly-expression">{summarizeGroup(group) || "暂无条件"}</div>
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
