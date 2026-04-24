"use client";

import { DeleteOutlined, PlusOutlined, QuestionCircleOutlined } from "@ant-design/icons";
import { Button, Card, Input, InputNumber, Radio, Select, Switch, Table, Tabs, Tag, Tooltip, Typography } from "antd";
import { useMemo } from "react";
import type { ReactNode } from "react";
import { StrategyPreviewChart } from "@/components/strategy-builder/strategy-preview-chart";
import type {
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
    leftField: "close",
    operator: ">",
    rightMode: "field",
    rightField: "ma20",
    rightValue: undefined,
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
                    locale={{ emptyText: "暂无成交记录" }}
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
  const fieldOptions = availableFields.map((item) => ({ label: renderFieldOptionLabel(item), value: item.value }));
  const isCrossOperator = value.operator === "cross_over" || value.operator === "cross_under";

  return (
    <div className="strategy-condition-row">
      <div className="strategy-condition-cell">
        <span className="strategy-condition-label">左值</span>
        <Select className="strategy-condition-field" options={fieldOptions} value={value.leftField} onChange={(next) => onChange({ ...value, leftField: next })} />
      </div>
      <div className="strategy-condition-cell">
        <span className="strategy-condition-label">运算符</span>
        <Select
          className="strategy-condition-operator"
          options={OPERATOR_OPTIONS}
          value={value.operator}
          onChange={(next) =>
            onChange({
              ...value,
              operator: next,
              rightMode: next === "cross_over" || next === "cross_under" ? "field" : value.rightMode,
            })
          }
        />
      </div>
      <div className="strategy-condition-cell">
        <span className="strategy-condition-label">右值类型</span>
        <Radio.Group
          className="strategy-condition-mode"
          size="small"
          optionType="button"
          buttonStyle="solid"
          options={[
            { label: "指标", value: "field" },
            { label: "数值", value: "constant" },
          ]}
          value={isCrossOperator ? "field" : value.rightMode}
          disabled={isCrossOperator}
          onChange={(event) =>
            onChange({
              ...value,
              rightMode: event.target.value,
              rightField: event.target.value === "field" ? value.rightField ?? "ma20" : undefined,
              rightValue: event.target.value === "constant" ? value.rightValue ?? 0 : undefined,
            })
          }
        />
      </div>
      <div className="strategy-condition-cell">
        <span className="strategy-condition-label">右值</span>
        {isCrossOperator || value.rightMode === "field" ? (
          <Select className="strategy-condition-field" options={fieldOptions} value={value.rightField} onChange={(next) => onChange({ ...value, rightField: next })} />
        ) : (
          <InputNumber className="strategy-condition-value" value={value.rightValue} onChange={(next) => onChange({ ...value, rightValue: Number(next ?? 0) })} />
        )}
      </div>
      <div className="strategy-condition-remove">
        <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={onDelete} />
      </div>
    </div>
  );
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
      const leftLabel = FIELD_OPTIONS.find((item) => item.value === child.leftField)?.label ?? child.leftField;
      const operatorLabel = OPERATOR_OPTIONS.find((item) => item.value === child.operator)?.label ?? child.operator;
      const rightLabel =
        child.rightMode === "field"
          ? FIELD_OPTIONS.find((item) => item.value === child.rightField)?.label ?? child.rightField ?? "-"
          : String(child.rightValue ?? 0);
      return `${leftLabel} ${operatorLabel} ${rightLabel}`;
    })
    .join(joiner);
}
