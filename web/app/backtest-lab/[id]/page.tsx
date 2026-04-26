"use client";

import { ArrowLeftOutlined, QuestionCircleOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Descriptions, Modal, Progress, Select, Space, Table, Tag, Tooltip, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
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
  scoreDiff?: number | null;
  sampleScore?: number | null;
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
  score?: number;
  averageSampleScore?: number;
  sampleScoreStd?: number;
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
  const [generatingImproved, setGeneratingImproved] = useState(false);
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

  const handleGenerateImprovedStrategy = useCallback(async () => {
    setGeneratingImproved(true);
    try {
      const token = getAccessToken();
      const response = await apiPost<{ draft: Record<string, unknown> }>(
        `/backtest-lab/strategies/${strategyId}/generate-improved`,
        {},
        token,
      );
      const key = `strategy-prefill-${Date.now()}`;
      window.localStorage.setItem(key, JSON.stringify(response.draft));
      window.open(`/strategy-builder/new?prefill=${encodeURIComponent(key)}`, "_blank", "noopener,noreferrer");
      messageApi.success("更优策略草稿已生成，已在新标签页打开。");
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "生成更优策略失败。");
    } finally {
      setGeneratingImproved(false);
    }
  }, [messageApi, strategyId]);

  const report = payload?.evaluation?.report || {};
  const isRunning = payload?.strategy.evaluationStatus === "queued" || payload?.strategy.evaluationStatus === "running";

  const crossAssetColumns = useResultColumns("标的", setDetailResult);
  const timeRangeColumns = useResultColumns("区间", setDetailResult);
  const totalScoreTooltip = buildTotalScoreTooltip(report);

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
                  <MetricLabel title="综合评分" tooltip={totalScoreTooltip} />
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
                <Space className="backtest-score-actions">
                  <Button className="backtest-score-action-button" type="primary" loading={evaluating} disabled={isRunning} onClick={() => void openEvaluateModal()}>
                    重新评估
                  </Button>
                  <Button className="backtest-score-action-button" type="primary" loading={generatingImproved} disabled={isRunning || !payload.evaluation || payload.evaluation.status !== "success"} onClick={() => void handleGenerateImprovedStrategy()}>
                    生成更优策略
                  </Button>
                </Space>
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
            <MetricCard title="跨标的得分" value={formatNumber(report.generality?.score)} helper={`${report.generality?.conclusion || "-"} / 通过率 ${formatPercent(report.generality?.passRate)}`} tooltip={buildGroupScoreTooltip(report.generality, "跨标的")} />
            <MetricCard title="跨时间得分" value={formatNumber(report.stability?.score)} helper={`${report.stability?.conclusion || "-"} / 通过率 ${formatPercent(report.stability?.passRate)}`} tooltip={buildGroupScoreTooltip(report.stability, "跨时间")} />
            <MetricCard title="交易健康度" value={formatNumber(report.tradeHealth?.score)} helper={report.tradeHealth?.conclusion} tooltip={buildTradeHealthTooltip(report)} />
            <MetricCard title="风险控制得分" value={formatNumber(calculateRiskScore(report))} helper={`最大平均回撤 ${formatPercent(calculateRiskDrawdown(report))}`} tooltip={buildRiskScoreTooltip(report)} />
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
              scroll={{ x: 1280 }}
            />
          </Card>

          <Card className="dashboard-card backtest-detail-card" bordered title="跨时间区间稳定性">
            <Table<EvaluationResult>
              rowKey={(record, index) => `${record.rangeLabel || record.dateRange?.start}-${index}`}
              columns={timeRangeColumns}
              dataSource={report.timeRangeResults || []}
              pagination={false}
              locale={{ emptyText: <EmptyState title="暂无跨时间区间评估结果" compact /> }}
              scroll={{ x: 1280 }}
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
        title: "样本分",
        key: "sampleScore",
        width: 112,
        render: (_, record) => (
          <div className="backtest-compared-cell">
            <span className={sampleScoreClass(record.sampleScore)}>{formatNumber(record.sampleScore)}</span>
            <small>差值 {formatSignedNumber(record.scoreDiff)}</small>
          </div>
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

function MetricCard({ title, value, helper, tooltip }: { title: string; value: string; helper?: string; tooltip?: ReactNode }) {
  return (
    <Card className="metric-card" bordered>
      <MetricLabel title={title} tooltip={tooltip} />
      <strong>{value}</strong>
      {helper ? <span>{helper}</span> : null}
    </Card>
  );
}

function MetricLabel({ title, tooltip }: { title: string; tooltip?: ReactNode }) {
  return (
    <span className="metric-label-with-help">
      <Text type="secondary">{title}</Text>
      {tooltip ? (
        <Tooltip title={<div className="metric-tooltip-content">{tooltip}</div>} placement="topLeft">
          <QuestionCircleOutlined />
        </Tooltip>
      ) : null}
    </span>
  );
}

function buildTotalScoreTooltip(report: EvaluationReport): ReactNode {
  const generalityScore = report.generality?.score;
  const stabilityScore = report.stability?.score;
  const riskScore = calculateRiskScore(report);
  const tradeHealthScore = report.tradeHealth?.score;
  const totalScore =
    (generalityScore ?? 0) * 0.25
    + (stabilityScore ?? 0) * 0.35
    + riskScore * 0.2
    + (tradeHealthScore ?? 0) * 0.1;
  const finalScore = report.score ?? totalScore;

  return (
    <>
      <div>综合评分用于衡量策略在跨标的、跨时间、风险控制和交易频率上的整体可靠性。</div>
      <div>公式：跨标的得分 * 0.25 + 跨时间得分 * 0.35 + 风险控制得分 * 0.20 + 交易健康度 * 0.10。</div>
      <div>
        实际：{formatNumber(generalityScore)} * 0.25 + {formatNumber(stabilityScore)} * 0.35 + {formatNumber(riskScore)} * 0.20 + {formatNumber(tradeHealthScore)} * 0.10 = {formatNumber(finalScore)}
      </div>
      <div>
        风险控制得分：max(0, 100 - max({formatPercent(report.generality?.averageMaxDrawdown)}, {formatPercent(report.stability?.averageMaxDrawdown)}) * 2) = {formatNumber(riskScore)}。
      </div>
      <div>等级：≥75 已通过；60-74.99 可观察；45-59.99 风险较高；&lt;45 未通过。</div>
    </>
  );
}

function buildGroupScoreTooltip(group: EvaluationGroup | undefined, label: string): ReactNode {
  return (
    <>
      <div>{label}得分衡量策略相对持续持有的平均优势，并对样本间波动做轻微惩罚。</div>
      <div>单样本分 = clamp(50 + (策略综合分 - 持续持有综合分) * 2, 0, 100)。</div>
      <div>分组得分 = 平均样本分 - 样本分标准差 * 0.2。</div>
      <div>
        实际：{formatNumber(group?.averageSampleScore)} - {formatNumber(group?.sampleScoreStd)} * 0.2 = {formatNumber(group?.score)}
      </div>
      <div>
        样本：成功 {group?.successCount ?? 0} / 总数 {group?.total ?? 0}，通过率 {formatPercent(group?.passRate)}。
      </div>
    </>
  );
}

function buildTradeHealthTooltip(report: EvaluationReport): ReactNode {
  const rows = [
    report.fullOriginal,
    ...(report.crossAssetResults || []),
    ...(report.timeRangeResults || []),
  ].filter((item): item is EvaluationResult => Boolean(item) && item?.status === "success");
  const healthyCount = rows.filter((item) => {
    const count = item.tradeCount ?? 0;
    return count >= 2 && count <= 120;
  }).length;
  const totalCount = rows.length;
  const actualScore = totalCount > 0 ? (healthyCount / totalCount) * 100 : 0;

  return (
    <>
      <div>交易健康度用于检查策略是否有足够的交易样本，同时避免过度频繁交易。</div>
      <div>当前口径：每个成功评估样本的交易次数在 2 到 120 次之间视为健康。</div>
      <div>公式：健康样本数 / 成功样本数 * 100。</div>
      <div>
        实际：{healthyCount} / {totalCount} * 100 = {formatNumber(report.tradeHealth?.score ?? actualScore)}；平均交易次数 {formatNumber(report.tradeHealth?.averageTradeCount)}。
      </div>
    </>
  );
}

function buildRiskScoreTooltip(report: EvaluationReport): ReactNode {
  const generalityDrawdown = report.generality?.averageMaxDrawdown;
  const stabilityDrawdown = report.stability?.averageMaxDrawdown;
  const riskDrawdown = calculateRiskDrawdown(report);
  const riskScore = calculateRiskScore(report);

  return (
    <>
      <div>风险控制得分用于衡量策略在跨标的和跨时间评估中的回撤压力。</div>
      <div>公式：max(0, 100 - max(跨标的平均最大回撤, 跨时间平均最大回撤) * 2)。</div>
      <div>
        实际：max(0, 100 - max({formatPercent(generalityDrawdown)}, {formatPercent(stabilityDrawdown)}) * 2)
        = max(0, 100 - {formatNumber(riskDrawdown)} * 2) = {formatNumber(riskScore)}。
      </div>
      <div>该得分在最终综合评分中占 20%。</div>
    </>
  );
}

function calculateRiskDrawdown(report: EvaluationReport): number {
  return Math.max(report.generality?.averageMaxDrawdown ?? 0, report.stability?.averageMaxDrawdown ?? 0);
}

function calculateRiskScore(report: EvaluationReport): number {
  return Math.max(0, 100 - calculateRiskDrawdown(report) * 2);
}

function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : value.toFixed(2);
}

function formatSignedNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

function sampleScoreClass(value: number | null | undefined): string | undefined {
  if (value === null || value === undefined) return undefined;
  if (value >= 55) return "positive-text";
  if (value < 45) return "negative-text";
  return undefined;
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
