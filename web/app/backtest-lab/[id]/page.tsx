"use client";

import { ArrowLeftOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Descriptions, Modal, Progress, Select, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { RuleReadonlyPreview } from "@/components/strategy-builder/rule-engine";
import { StrategyPreviewChart } from "@/components/strategy-builder/strategy-preview-chart";
import type { StrategyDslConfig, StrategyPreviewResult } from "@/components/strategy-builder/types";
import { apiGet, apiPost } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

const { Paragraph, Text, Title } = Typography;

type EvaluationStatus = "not_evaluated" | "queued" | "running" | "success" | "failure";

type StrategyRow = {
  id: number;
  name: string;
  type: string;
  source: string;
  status: string;
  assetName: string | null;
  assetIdentifier: string | null;
  assetType: "stock" | "index" | null;
  strategyConfig?: Record<string, unknown> | null;
  evaluationStatus: EvaluationStatus;
  evaluationStatusLabel: string;
};

type EvaluationResult = {
  assetName?: string | null;
  assetIdentifier?: string | null;
  assetType?: string | null;
  countryCode?: string | null;
  rangeLabel?: string;
  status: "success" | "failure";
  passed?: boolean;
  score?: number | null;
  benchmarkScore?: number | null;
  reason?: string;
  dateRange?: { start?: string | null; end?: string | null };
  annualReturn?: number | null;
  benchmarkAnnualReturn?: number | null;
  maxDrawdown?: number | null;
  benchmarkMaxDrawdown?: number | null;
  sharpe?: number | null;
  benchmarkSharpe?: number | null;
  tradeCount?: number | null;
  benchmarkTradeCount?: number | null;
  winRate?: number | null;
  benchmarkWinRate?: number | null;
  detail?: StrategyPreviewResult | null;
};

type EvaluationGroup = {
  label: string;
  total: number;
  successCount: number;
  passedCount: number;
  passRate: number;
  averageAnnualReturn: number;
  averageMaxDrawdown: number;
  averageSharpe: number;
  conclusion: string;
  warnings?: EvaluationResult[];
};

type TradeHealth = {
  score: number;
  conclusion: string;
  averageTradeCount: number;
  warnings?: string[];
};

type EvaluationReport = {
  score?: number;
  conclusion?: string;
  summary?: string;
  aiAdvice?: {
    status?: "success" | "failed" | "skipped";
    message?: string;
    ruleAnalysis?: string;
    riskPoints?: string[];
    recommendation?: string;
  };
  fullOriginal?: EvaluationResult;
  generality?: EvaluationGroup;
  stability?: EvaluationGroup;
  tradeHealth?: TradeHealth;
  crossAssetResults?: EvaluationResult[];
  timeRangeResults?: EvaluationResult[];
};

type Evaluation = {
  id: number;
  status: EvaluationStatus;
  score: number | null;
  conclusion: string | null;
  generalityConclusion: string | null;
  stabilityConclusion: string | null;
  riskConclusion: string | null;
  summary: string | null;
  errorMessage: string | null;
  report: EvaluationReport;
  startedAt: string | null;
  finishedAt: string | null;
  updatedAt: string | null;
};

type DetailResponse = {
  strategy: StrategyRow;
  evaluation: Evaluation | null;
};

type EvaluationCandidate = {
  label: string;
  value: string;
  name?: string | null;
  assetIdentifier: string;
  latestDate?: string | null;
};

type EvaluationCandidateResponse = {
  countryCode: string;
  assetType: "stock" | "index";
  items: EvaluationCandidate[];
};

const statusMeta: Record<EvaluationStatus, { label: string; color: string }> = {
  not_evaluated: { label: "未评估", color: "default" },
  queued: { label: "评估中", color: "processing" },
  running: { label: "评估中", color: "processing" },
  success: { label: "已完成", color: "success" },
  failure: { label: "失败", color: "error" },
};

const conclusionColor: Record<string, string> = {
  已通过: "green",
  可观察: "blue",
  风险较高: "orange",
  未通过: "red",
};

function asStrategyDslConfig(value: Record<string, unknown> | null | undefined): StrategyDslConfig | null {
  if (!value || typeof value !== "object" || !("entry" in value) || !("exit" in value)) {
    return null;
  }
  return value as unknown as StrategyDslConfig;
}

export default function BacktestLabDetailPage() {
  const params = useParams<{ id: string }>();
  const strategyId = Number(params.id);
  const [messageApi, contextHolder] = message.useMessage();
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [payload, setPayload] = useState<DetailResponse | null>(null);
  const [evaluateModalOpen, setEvaluateModalOpen] = useState(false);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [aiSelecting, setAiSelecting] = useState(false);
  const [candidateOptions, setCandidateOptions] = useState<EvaluationCandidate[]>([]);
  const [candidateCountryCode, setCandidateCountryCode] = useState("");
  const [selectedCandidateValues, setSelectedCandidateValues] = useState<string[]>([]);
  const [detailResult, setDetailResult] = useState<EvaluationResult | null>(null);

  const loadDetail = useCallback(async () => {
    setLoading(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<DetailResponse>(`/backtest-lab/strategies/${strategyId}`, token);
      setPayload(response);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载评估详情失败。");
    } finally {
      setLoading(false);
    }
  }, [messageApi, strategyId]);

  useEffect(() => {
    if (Number.isFinite(strategyId)) {
      void loadDetail();
    }
  }, [loadDetail, strategyId]);

  const openEvaluateModal = useCallback(async () => {
    if (!payload) return;
    setEvaluateModalOpen(true);
    setSelectedCandidateValues([]);
    setCandidateOptions([]);
    setCandidateCountryCode(payload.strategy.assetIdentifier || "");
    setLoadingCandidates(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<EvaluationCandidateResponse>(
        `/backtest-lab/strategies/${strategyId}/candidate-assets`,
        token,
      );
      setCandidateOptions(response.items);
      setCandidateCountryCode(response.countryCode);
      if (response.items.length === 0) {
        messageApi.warning("当前没有可用于重新评估的已同步标的。");
      }
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载可评估标的失败。");
    } finally {
      setLoadingCandidates(false);
    }
  }, [messageApi, payload, strategyId]);

  const handleAiSelectCandidates = useCallback(async () => {
    setAiSelecting(true);
    try {
      const token = getAccessToken();
      const response = await apiPost<{ items: EvaluationCandidate[]; selection?: { message?: string } }>(
        `/backtest-lab/strategies/${strategyId}/candidate-assets/ai`,
        {},
        token,
      );
      const values = response.items.map((item) => item.value).filter(Boolean);
      setSelectedCandidateValues(values);
      messageApi.success(response.selection?.message || "已由 AI 添加评估标的。");
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "AI 添加标的失败。");
    } finally {
      setAiSelecting(false);
    }
  }, [messageApi, strategyId]);

  const handleEvaluate = useCallback(async () => {
    setEvaluating(true);
    try {
      const token = getAccessToken();
      await apiPost(
        `/backtest-lab/strategies/${strategyId}/evaluate`,
        { assetIdentifiers: selectedCandidateValues },
        token,
      );
      messageApi.success("策略全面评估任务已提交，可在任务中心查看进度。");
      setEvaluateModalOpen(false);
      setCandidateOptions([]);
      setCandidateCountryCode("");
      setSelectedCandidateValues([]);
      await loadDetail();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "提交策略评估失败。");
    } finally {
      setEvaluating(false);
    }
  }, [loadDetail, messageApi, selectedCandidateValues, strategyId]);

  const report = payload?.evaluation?.report || {};
  const isRunning = payload?.strategy.evaluationStatus === "queued" || payload?.strategy.evaluationStatus === "running";

  const crossAssetColumns = useResultColumns("标的", setDetailResult);
  const timeRangeColumns = useResultColumns("区间", setDetailResult);

  return (
    <AppShell>
      {contextHolder}
      <section className="dashboard-heading">
        <div>
          <Title level={1}>回测评估详情</Title>
          <Text className="page-description">查看该策略当前覆盖式全面评估报告。</Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => void loadDetail()}>
            刷新
          </Button>
          <Link href="/backtest-lab">
            <Button icon={<ArrowLeftOutlined />}>返回列表</Button>
          </Link>
        </Space>
      </section>

      {!payload && !loading ? (
        <Card className="dashboard-card" bordered>
          <EmptyState title="未找到评估详情" compact />
        </Card>
      ) : null}

      {payload ? (
        <>
          <div className="backtest-detail-grid">
            <Card className="dashboard-card" bordered loading={loading} title="评估概览">
              <div className="backtest-score-panel">
                <div>
                  <Text type="secondary">综合评分</Text>
                  <strong>{formatNumber(payload.evaluation?.score)}</strong>
                </div>
                <div>
                  <Text type="secondary">评估结论</Text>
                  {payload.evaluation?.conclusion ? (
                    <Tag color={conclusionColor[payload.evaluation.conclusion] || "default"}>
                      {payload.evaluation.conclusion}
                    </Tag>
                  ) : (
                    <Text>-</Text>
                  )}
                </div>
                <div>
                  <Text type="secondary">状态</Text>
                  <Tag color={statusMeta[payload.strategy.evaluationStatus]?.color || "default"}>
                    {statusMeta[payload.strategy.evaluationStatus]?.label || payload.strategy.evaluationStatusLabel}
                  </Tag>
                </div>
                <Button type="primary" loading={evaluating} disabled={isRunning} onClick={() => void openEvaluateModal()}>
                  重新评估
                </Button>
              </div>

              {report.aiAdvice ? (
                <div className="backtest-overview-ai-advice">
                  <AiAdvicePanel advice={report.aiAdvice} />
                </div>
              ) : (
                <EmptyState title="暂无评估报告" description="点击重新评估后会生成覆盖式报告。" compact />
              )}
            </Card>

            <Card className="dashboard-card" bordered loading={loading} title="策略快照">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="策略名称">{payload.strategy.name}</Descriptions.Item>
                <Descriptions.Item label="来源">{payload.strategy.source}</Descriptions.Item>
                <Descriptions.Item label="类型">{payload.strategy.type}</Descriptions.Item>
                <Descriptions.Item label="原始标的">
                  {payload.strategy.assetName || "-"} / {payload.strategy.assetIdentifier || "-"}
                </Descriptions.Item>
                <Descriptions.Item label="评估时间">{formatDateTime(payload.evaluation?.updatedAt || null)}</Descriptions.Item>
              </Descriptions>
              <div className="backtest-rule-snapshot">
                <RuleReadonlyPreview value={asStrategyDslConfig(payload.strategy.strategyConfig)} compact />
              </div>
            </Card>
          </div>

          <div className="backtest-detail-metrics">
            <MetricCard title="跨标的通过率" value={formatPercent(report.generality?.passRate)} helper={report.generality?.conclusion} />
            <MetricCard title="跨时间通过率" value={formatPercent(report.stability?.passRate)} helper={report.stability?.conclusion} />
            <MetricCard title="交易健康度" value={formatNumber(report.tradeHealth?.score)} helper={report.tradeHealth?.conclusion} />
            <MetricCard title="原始标的年化" value={formatPercent(report.fullOriginal?.annualReturn)} helper={`持续持有 ${formatPercent(report.fullOriginal?.benchmarkAnnualReturn)}`} />
          </div>

          {payload.evaluation?.errorMessage ? (
            <Card className="dashboard-card" bordered title="失败原因">
              <Text type="danger">{payload.evaluation.errorMessage}</Text>
            </Card>
          ) : null}

          <Card className="dashboard-card backtest-detail-card" bordered title="跨标的通用性">
            <Table<EvaluationResult>
              rowKey={(record, index) => `${record.assetIdentifier || record.assetName}-${index}`}
              columns={crossAssetColumns}
              dataSource={report.crossAssetResults || []}
              pagination={false}
              locale={{ emptyText: <EmptyState title="暂无跨标的评估结果" compact /> }}
              scroll={{ x: 1160 }}
            />
          </Card>

          <Card className="dashboard-card backtest-detail-card" bordered title="跨时间区间稳定性">
            <Table<EvaluationResult>
              rowKey={(record, index) => `${record.rangeLabel || record.dateRange?.start}-${index}`}
              columns={timeRangeColumns}
              dataSource={report.timeRangeResults || []}
              pagination={false}
              locale={{ emptyText: <EmptyState title="暂无跨时间区间评估结果" compact /> }}
              scroll={{ x: 1160 }}
            />
          </Card>

          <Card className="dashboard-card backtest-detail-card" bordered title="交易健康度">
            {report.tradeHealth ? (
              <div className="backtest-health-panel">
                <Progress percent={Math.round(report.tradeHealth.score || 0)} strokeColor="#10b981" />
                <Descriptions column={3} size="small">
                  <Descriptions.Item label="结论">{report.tradeHealth.conclusion}</Descriptions.Item>
                  <Descriptions.Item label="平均交易次数">{formatNumber(report.tradeHealth.averageTradeCount)}</Descriptions.Item>
                  <Descriptions.Item label="警告数量">{report.tradeHealth.warnings?.length || 0}</Descriptions.Item>
                </Descriptions>
                {report.tradeHealth.warnings?.length ? (
                  <div className="backtest-warning-list">
                    {report.tradeHealth.warnings.map((item) => (
                      <Text key={item} type="secondary">{item}</Text>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : (
              <EmptyState title="暂无交易健康度数据" compact />
            )}
          </Card>
        </>
      ) : null}
      <Modal
        title="选择重新评估标的"
        open={evaluateModalOpen}
        okText="开始重新评估"
        cancelText="取消"
        width={720}
        confirmLoading={evaluating}
        okButtonProps={{ disabled: selectedCandidateValues.length === 0 }}
        onCancel={() => {
          setEvaluateModalOpen(false);
          setCandidateOptions([]);
          setCandidateCountryCode("");
          setSelectedCandidateValues([]);
        }}
        onOk={() => void handleEvaluate()}
      >
        <div className="evaluation-target-panel">
          <div>
            <Text type="secondary">国家/地区</Text>
            <strong>{candidateCountryCode || "-"}</strong>
          </div>
          <div>
            <Text type="secondary">标的类型</Text>
            <strong>{payload?.strategy.assetType === "stock" ? "股票" : "指数"}</strong>
          </div>
        </div>
        <Space.Compact className="evaluation-select-row">
          <Select
            mode="multiple"
            allowClear
            showSearch
            loading={loadingCandidates}
            value={selectedCandidateValues}
            options={candidateOptions}
            optionFilterProp="label"
            placeholder="请选择用于重新评估的股票或指数"
            maxTagCount="responsive"
            onChange={setSelectedCandidateValues}
          />
          <Button loading={aiSelecting} onClick={() => void handleAiSelectCandidates()}>
            由 AI 添加
          </Button>
        </Space.Compact>
        <Text type="secondary">这里只能选择同国家/地区、同类型且已经同步过历史日线数据的标的。</Text>
      </Modal>
      <Modal
        title={detailResult ? `${detailResult.rangeLabel || detailResult.assetName || detailResult.assetIdentifier || "评估样本"}详情` : "评估详情"}
        open={Boolean(detailResult)}
        footer={null}
        width={1120}
        onCancel={() => setDetailResult(null)}
      >
        {detailResult?.detail ? (
          <EvaluationResultDetail result={detailResult} />
        ) : (
          <EmptyState title="暂无详情数据" description="请重新评估后查看指标、图表和成交明细。" compact />
        )}
      </Modal>
    </AppShell>
  );
}

function AiAdvicePanel({ advice }: { advice?: EvaluationReport["aiAdvice"] }) {
  if (!advice) {
    return <EmptyState title="暂无 AI 建议" description="完成评估后会结合规则与评分生成建议。" compact />;
  }
  if (advice.status !== "success") {
    return <EmptyState title="暂无 AI 建议" description={advice.message || "AI 建议暂不可用。"} compact />;
  }

  return (
    <div className="backtest-ai-advice">
      <div>
        <Text type="secondary">买入卖出规则解析</Text>
        <Paragraph>{advice.ruleAnalysis || "暂无规则解析。"}</Paragraph>
      </div>
      <div>
        <Text type="secondary">潜在风险点</Text>
        {advice.riskPoints?.length ? (
          <ul>
            {advice.riskPoints.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <Paragraph>暂无明确风险点。</Paragraph>
        )}
      </div>
      <div>
        <Text type="secondary">综合建议</Text>
        <Paragraph>{advice.recommendation || "暂无综合建议。"}</Paragraph>
      </div>
    </div>
  );
}

function EvaluationResultDetail({ result }: { result: EvaluationResult }) {
  const detail = result.detail;
  if (!detail) {
    return <EmptyState title="暂无详情数据" compact />;
  }

  return (
    <div className="strategy-preview-panel">
      <div className="strategy-preview-metrics">
        {[
          ["综合分数", formatNumber(result.score), formatNumber(result.benchmarkScore)],
          ["年化收益", formatPercent(detail.annualReturn), formatPercent(detail.benchmarkAnnualReturn)],
          ["总收益", formatPercent(detail.totalReturn), formatPercent(detail.benchmarkReturn)],
          ["最大回撤", formatPercent(detail.maxDrawdown), formatPercent(detail.benchmarkMaxDrawdown)],
          ["波动率", formatPercent(detail.volatility), formatPercent(detail.benchmarkVolatility)],
          ["Sharpe", formatNumber(detail.sharpe), formatNumber(detail.benchmarkSharpe)],
          ["胜率", formatPercent(detail.winRate), formatPercent(detail.benchmarkWinRate)],
          ["交易次数", formatNumber(detail.tradeCount), formatNumber(detail.benchmarkTradeCount)],
        ].map(([label, strategyValue, benchmarkValue]) => (
          <div key={label} className="strategy-preview-metric-card">
            <div className="strategy-preview-metric-header">
              <span>{label}</span>
            </div>
            <div className="strategy-preview-metric-values">
              <div>
                <small>策略</small>
                <strong>{strategyValue}</strong>
              </div>
              <div>
                <small>持续持有</small>
                <strong>{benchmarkValue}</strong>
              </div>
            </div>
          </div>
        ))}
      </div>

      <StrategyPreviewChart preview={detail} />

      <div className="strategy-preview-range">
        <Text type="secondary">
          回测区间：{detail.dateRange.start ?? "--"} 至 {detail.dateRange.end ?? "--"}
        </Text>
      </div>

      <Table
        className="strategy-preview-trades"
        size="small"
        pagination={false}
        scroll={{ y: 260 }}
        rowKey={(record) => `${record.date}_${record.side}_${record.price}_${record.shares}`}
        dataSource={detail.trades}
        locale={{ emptyText: <EmptyState title="暂无成交记录" compact /> }}
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
            title: "收益率",
            dataIndex: "return",
            render: (value?: number) => (value == null ? "--" : `${value.toFixed(2)}%`),
          },
          {
            title: "触发原因",
            dataIndex: "reason",
            ellipsis: true,
            render: (value: string) => value || "-",
          },
        ]}
      />
    </div>
  );
}

function useResultColumns(firstTitle: string, onViewDetail: (record: EvaluationResult) => void): ColumnsType<EvaluationResult> {
  return useMemo(
    () => [
      {
        title: firstTitle,
        key: "target",
        width: 220,
        render: (_, record) => (
          <div className="backtest-lab-asset">
            <span>{record.rangeLabel || record.assetName || "-"}</span>
            <Text type="secondary">{record.assetIdentifier || formatRange(record.dateRange)}</Text>
          </div>
        ),
      },
      {
        title: "结果",
        key: "passed",
        width: 100,
        render: (_, record) =>
          record.status === "success" ? (
            <Tag color={record.passed ? "green" : "red"}>{record.passed ? "通过" : "未通过"}</Tag>
          ) : (
            <Tag color="error">失败</Tag>
          ),
      },
      {
        title: "综合分数",
        key: "score",
        width: 118,
        render: (_, record) => (
          <ComparedMetricCell value={record.score} benchmark={record.benchmarkScore} formatter={formatNumber} />
        ),
      },
      {
        title: "年化收益",
        key: "annualReturn",
        width: 122,
        render: (_, record) => (
          <ComparedMetricCell value={record.annualReturn} benchmark={record.benchmarkAnnualReturn} formatter={formatPercent} />
        ),
      },
      {
        title: "最大回撤",
        key: "maxDrawdown",
        width: 122,
        render: (_, record) => (
          <ComparedMetricCell
            value={record.maxDrawdown}
            benchmark={record.benchmarkMaxDrawdown}
            formatter={formatPercent}
            higherBetter={false}
          />
        ),
      },
      {
        title: "Sharpe",
        key: "sharpe",
        width: 110,
        render: (_, record) => (
          <ComparedMetricCell value={record.sharpe} benchmark={record.benchmarkSharpe} formatter={formatNumber} />
        ),
      },
      {
        title: "交易次数",
        key: "tradeCount",
        width: 110,
        render: (_, record) => (
          <ComparedMetricCell value={record.tradeCount} benchmark={record.benchmarkTradeCount} formatter={formatNumber} />
        ),
      },
      {
        title: "胜率",
        key: "winRate",
        width: 110,
        render: (_, record) => (
          <ComparedMetricCell value={record.winRate} benchmark={record.benchmarkWinRate} formatter={formatPercent} />
        ),
      },
      {
        title: "说明",
        dataIndex: "reason",
        ellipsis: true,
        render: (value: string | undefined) => value || "-",
      },
      {
        title: "操作",
        key: "action",
        width: 100,
        fixed: "right",
        render: (_, record) => (
          <Button type="link" onClick={() => onViewDetail(record)}>
            查看详情
          </Button>
        ),
      },
    ],
    [firstTitle, onViewDetail],
  );
}

function ComparedMetricCell({
  value,
  benchmark,
  formatter,
  higherBetter = true,
}: {
  value: number | null | undefined;
  benchmark: number | null | undefined;
  formatter: (value: number | null | undefined) => string;
  higherBetter?: boolean;
}) {
  const hasValue = value !== null && value !== undefined;
  const hasBenchmark = benchmark !== null && benchmark !== undefined;
  const isBetter = hasValue && hasBenchmark ? (higherBetter ? value > benchmark : value < benchmark) : false;

  return (
    <div className="backtest-compared-cell">
      <span className={hasValue ? (isBetter ? "positive-text" : "negative-text") : undefined}>{formatter(value)}</span>
      <small>{formatter(benchmark)}</small>
    </div>
  );
}

function MetricCard({ title, value, helper }: { title: string; value: string; helper?: string }) {
  return (
    <Card className="metric-card" bordered>
      <Text type="secondary">{title}</Text>
      <strong>{value}</strong>
      {helper ? <span>{helper}</span> : null}
    </Card>
  );
}

function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : value.toFixed(2);
}

function formatPercent(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : `${value.toFixed(2)}%`;
}

function formatRange(range?: { start?: string | null; end?: string | null }): string {
  if (!range?.start && !range?.end) return "-";
  return `${range.start || "-"} 至 ${range.end || "-"}`;
}

function formatDateTime(value: string | null): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}
