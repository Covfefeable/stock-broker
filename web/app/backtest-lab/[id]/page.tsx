"use client";

import { ArrowLeftOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Descriptions, Progress, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
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

export default function BacktestLabDetailPage() {
  const params = useParams<{ id: string }>();
  const strategyId = Number(params.id);
  const [messageApi, contextHolder] = message.useMessage();
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [payload, setPayload] = useState<DetailResponse | null>(null);

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

  const handleEvaluate = useCallback(async () => {
    setEvaluating(true);
    try {
      const token = getAccessToken();
      await apiPost(`/backtest-lab/strategies/${strategyId}/evaluate`, {}, token);
      messageApi.success("策略全面评估任务已提交，可在任务中心查看进度。");
      await loadDetail();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "提交策略评估失败。");
    } finally {
      setEvaluating(false);
    }
  }, [loadDetail, messageApi, strategyId]);

  const report = payload?.evaluation?.report || {};
  const isRunning = payload?.strategy.evaluationStatus === "queued" || payload?.strategy.evaluationStatus === "running";

  const crossAssetColumns = useResultColumns("标的");
  const timeRangeColumns = useResultColumns("区间");

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
                <Button type="primary" loading={evaluating} disabled={isRunning} onClick={() => void handleEvaluate()}>
                  重新评估
                </Button>
              </div>

              {payload.evaluation?.summary ? (
                <Paragraph className="backtest-detail-summary">{payload.evaluation.summary}</Paragraph>
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
              scroll={{ x: 1060 }}
            />
          </Card>

          <Card className="dashboard-card backtest-detail-card" bordered title="跨时间区间稳定性">
            <Table<EvaluationResult>
              rowKey={(record, index) => `${record.rangeLabel || record.dateRange?.start}-${index}`}
              columns={timeRangeColumns}
              dataSource={report.timeRangeResults || []}
              pagination={false}
              locale={{ emptyText: <EmptyState title="暂无跨时间区间评估结果" compact /> }}
              scroll={{ x: 1060 }}
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
    </AppShell>
  );
}

function useResultColumns(firstTitle: string): ColumnsType<EvaluationResult> {
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
    ],
    [firstTitle],
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
