"use client";

import { ArrowLeftOutlined, CheckOutlined, CloseOutlined, EditOutlined, QuestionCircleOutlined, SaveOutlined } from "@ant-design/icons";
import { Button, Card, Input, Modal, Progress, Space, Table, Tabs, Tag, Tooltip, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import type { AgentIterationItem, AgentTaskDetailResponse, AgentTaskItem } from "@/components/agent-tasks/types";
import { RuleReadonlyPreview } from "@/components/strategy-builder/rule-engine";
import { StrategyBacktestDetailPanel } from "@/components/strategy-builder/strategy-backtest-detail-panel";
import type { StrategyDslConfig, StrategyPreviewResult } from "@/components/strategy-builder/types";
import { getAccessToken } from "@/lib/auth";
import { apiGet, apiPost, apiPut } from "@/lib/api";

const { Title, Text, Paragraph } = Typography;

type TaskSocketMessage =
  | {
      type: "snapshot";
      payload: {
        tasks: Array<{ taskId: string; entityType?: string | null; entityId?: number | null }>;
      };
    }
  | {
      type: "task.updated";
      payload: { taskId: string; entityType?: string | null; entityId?: number | null };
      userId?: number | null;
    }
  | {
      type: "error";
      message: string;
    };

const statusMeta = {
  queued: { label: "排队中", color: "default" },
  running: { label: "运行中", color: "processing" },
  success: { label: "已完成", color: "success" },
  failure: { label: "失败", color: "error" },
  stopped: { label: "已停止", color: "warning" },
} as const;

const previewRangeOptions = [
  { key: "current", label: "当前回测区间" },
  { key: "recent_1y", label: "近一年" },
  { key: "recent_3y", label: "近三年" },
  { key: "recent_5y", label: "近五年" },
];

function formatPercent(value: number | null | undefined) {
  return value === null || value === undefined ? "-" : `${value.toFixed(2)}%`;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function renderOptionalText(value: string | null | undefined, fallback: string) {
  const normalized = String(value ?? "").trim();
  if (!normalized || normalized.toLowerCase() === "none") {
    return fallback;
  }
  return normalized;
}

function buildTaskCenterWsUrl(token: string): string {
  const configuredBase = process.env.NEXT_PUBLIC_WS_BASE_URL?.replace(/\/$/, "");
  if (configuredBase) {
    return `${configuredBase}/ws/tasks?token=${encodeURIComponent(token)}`;
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/ws/tasks?token=${encodeURIComponent(token)}`;
}

function asStrategyDslConfig(value: Record<string, unknown> | null | undefined): StrategyDslConfig | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const hasRuleList = Array.isArray(value.entryRules) && Array.isArray(value.exitRules);
  const hasLegacyRule = "entry" in value && "exit" in value;
  if (!hasRuleList && !hasLegacyRule) {
    return null;
  }
  return value as unknown as StrategyDslConfig;
}

function renderPerformanceScoreTooltip() {
  return (
    <div className="metric-tooltip-content">
      <div>综合分数用于平衡收益、稳定性和回撤后选择最佳综合表现。</div>
      <div>公式：年化收益 * 年化收益权重 + Sharpe * Sharpe 权重 - 最大回撤 * 最大回撤权重。</div>
      <div>当前默认：年化收益权重 0.7，Sharpe 权重 5，最大回撤权重 0.2。</div>
      <div>实际权重可在系统设置的评分权重中调整，后续迭代按当时配置计算。</div>
    </div>
  );
}

function AgentIterationPreviewPanel({
  preview,
  strategyConfig,
  iteration,
}: {
  preview: StrategyPreviewResult;
  strategyConfig?: Record<string, unknown> | null;
  iteration?: AgentIterationItem | null;
}) {
  return (
    <StrategyBacktestDetailPanel
      preview={preview}
      tradeScrollY={240}
      metrics={[
        {
          label: "综合分数",
          strategyValue: preview.score != null ? preview.score.toFixed(2) : iteration?.score != null ? iteration.score.toFixed(2) : "-",
          benchmarkValue:
            preview.benchmarkScore != null
              ? preview.benchmarkScore.toFixed(2)
              : iteration?.benchmarkScore != null
                ? iteration.benchmarkScore.toFixed(2)
                : "-",
        },
        { label: "年化收益", strategyValue: `${preview.annualReturn.toFixed(2)}%`, benchmarkValue: `${preview.benchmarkAnnualReturn.toFixed(2)}%` },
        { label: "总收益", strategyValue: `${preview.totalReturn.toFixed(2)}%`, benchmarkValue: `${preview.benchmarkReturn.toFixed(2)}%` },
        { label: "最大回撤", strategyValue: `${preview.maxDrawdown.toFixed(2)}%`, benchmarkValue: `${preview.benchmarkMaxDrawdown.toFixed(2)}%` },
        { label: "波动率", strategyValue: `${preview.volatility.toFixed(2)}%`, benchmarkValue: `${preview.benchmarkVolatility.toFixed(2)}%` },
        { label: "Sharpe", strategyValue: preview.sharpe.toFixed(2), benchmarkValue: preview.benchmarkSharpe.toFixed(2) },
        { label: "胜率", strategyValue: `${preview.winRate.toFixed(2)}%`, benchmarkValue: `${preview.benchmarkWinRate.toFixed(2)}%` },
        { label: "交易次数", strategyValue: String(preview.tradeCount), benchmarkValue: String(preview.benchmarkTradeCount) },
      ]}
      rulePreview={
        <Card className="strategy-rule-card" size="small" title="规则预览">
          <RuleReadonlyPreview value={asStrategyDslConfig(strategyConfig)} />
        </Card>
      }
    />
  );
}

export default function AgentTaskDetailPage() {
  const params = useParams<{ id: string }>();
  const [messageApi, contextHolder] = message.useMessage();
  const [loading, setLoading] = useState(true);
  const [task, setTask] = useState<AgentTaskItem | null>(null);
  const [iterations, setIterations] = useState<AgentIterationItem[]>([]);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewResult, setPreviewResult] = useState<StrategyPreviewResult | null>(null);
  const [previewIteration, setPreviewIteration] = useState<AgentIterationItem | null>(null);
  const [previewRange, setPreviewRange] = useState("current");
  const [savingBestAnnualStrategy, setSavingBestAnnualStrategy] = useState(false);
  const [savingBestCompositeStrategy, setSavingBestCompositeStrategy] = useState(false);
  const [savingIterationStrategyId, setSavingIterationStrategyId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const refreshTimerRef = useRef<number | null>(null);

  const loadDetail = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setLoading(true);
    }
    try {
      const token = getAccessToken();
      const response = await apiGet<AgentTaskDetailResponse>(`/agent-tasks/${params.id}`, token);
      setTask(response.task);
      setDraftName(response.task.name);
      setIterations(response.iterations);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载 Agent 任务详情失败。");
    } finally {
      if (!options?.silent) {
        setLoading(false);
      }
    }
  }, [messageApi, params.id]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    const token = getAccessToken();
    const currentTaskId = Number(params.id);
    if (!token || Number.isNaN(currentTaskId)) {
      return;
    }

    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;

    const scheduleRefresh = () => {
      if (refreshTimerRef.current) {
        window.clearTimeout(refreshTimerRef.current);
      }
      refreshTimerRef.current = window.setTimeout(() => {
        if (!cancelled) {
          void loadDetail({ silent: true });
        }
      }, 350);
    };

    const connect = () => {
      if (cancelled) {
        return;
      }
      socket = new WebSocket(buildTaskCenterWsUrl(token));
      socket.onmessage = (event) => {
        if (cancelled) {
          return;
        }
        try {
          const payload = JSON.parse(event.data) as TaskSocketMessage;
          if (payload.type === "task.updated" && payload.payload.entityType === "agent_task" && payload.payload.entityId === currentTaskId) {
            scheduleRefresh();
          }
        } catch {
          // Ignore malformed websocket messages; the task center owns user-facing websocket errors.
        }
      };
      socket.onclose = () => {
        if (!cancelled) {
          reconnectTimer = window.setTimeout(connect, 2000);
        }
      };
      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (refreshTimerRef.current) {
        window.clearTimeout(refreshTimerRef.current);
      }
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
      }
      socket?.close();
    };
  }, [loadDetail, params.id]);

  const handleSaveName = useCallback(async () => {
    const normalizedName = draftName.trim();
    if (!normalizedName) {
      messageApi.warning("请输入任务名称。");
      return;
    }
    try {
      setSavingName(true);
      const token = getAccessToken();
      const response = await apiPut<{ task: AgentTaskItem }>(`/agent-tasks/${params.id}`, { name: normalizedName }, token);
      setTask(response.task);
      setDraftName(response.task.name);
      setEditingName(false);
      messageApi.success("任务名称已更新。");
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "更新任务名称失败。");
    } finally {
      setSavingName(false);
    }
  }, [draftName, messageApi, params.id]);

  const loadIterationPreview = useCallback(
    async (iteration: AgentIterationItem, rangeKey: string) => {
      try {
        setPreviewLoading(true);
        const token = getAccessToken();
        const response = await apiGet<StrategyPreviewResult>(
          `/agent-tasks/${params.id}/iterations/${iteration.id}/preview?range=${encodeURIComponent(rangeKey)}`,
          token,
        );
        setPreviewResult(response);
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载迭代收益预览失败。");
      } finally {
        setPreviewLoading(false);
      }
    },
    [messageApi, params.id],
  );

  const openIterationPreview = useCallback(
    async (iteration: AgentIterationItem) => {
      setPreviewIteration(iteration);
      setPreviewRange("current");
      setPreviewResult(null);
      setPreviewOpen(true);
      await loadIterationPreview(iteration, "current");
    },
    [loadIterationPreview],
  );

  const handlePreviewRangeChange = useCallback(
    async (rangeKey: string) => {
      if (!previewIteration) {
        return;
      }
      setPreviewRange(rangeKey);
      setPreviewResult(null);
      await loadIterationPreview(previewIteration, rangeKey);
    },
    [loadIterationPreview, previewIteration],
  );

  const saveStrategyFromIteration = useCallback(
    async (iteration: AgentIterationItem, nameSuffix: string) => {
      if (!task || !iteration.strategyConfig) {
        messageApi.warning("当前迭代没有可保存的策略。");
        return;
      }

      try {
        setSavingIterationStrategyId(iteration.id);
        const token = getAccessToken();
        await apiPost(
          "/strategies",
          {
            name: `${task.name} - ${nameSuffix}`,
            type: "AI Agent",
            source: "人工创建",
            countryRegion: task.countryCode,
            assetType: task.assetType,
            assetIdentifier: task.assetIdentifier,
            assetName: task.assetName,
            strategyConfig: iteration.strategyConfig,
            annualReturn: iteration.annualReturn,
            maxDrawdown: iteration.maxDrawdown ?? null,
          },
          token,
        );
        messageApi.success("策略已保存。");
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "保存策略失败。");
      } finally {
        setSavingIterationStrategyId(null);
      }
    },
    [messageApi, task],
  );

  const iterationColumns: ColumnsType<AgentIterationItem> = useMemo(
    () => [
      { title: "轮次", dataIndex: "iterationNumber", key: "iterationNumber", width: 80 },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 96,
        render: (value: string) => {
          const meta = statusMeta[value as keyof typeof statusMeta];
          return <Tag color={meta?.color ?? "default"}>{meta?.label ?? value}</Tag>;
        },
      },
      {
        title: "交易风格",
        dataIndex: "intentLabel",
        key: "intentLabel",
        width: 130,
        render: (value: string | null | undefined, record) => (
          <Tag color="blue">{value || record.intent || "未记录"}</Tag>
        ),
      },
      {
        title: "净值对比",
        key: "equityPreview",
        width: 150,
        render: (_, record) => <MiniEquityCompareChart preview={record.equityPreview} />,
      },
      {
        title: "年化收益",
        dataIndex: "annualReturn",
        key: "annualReturn",
        width: 120,
        render: (value: number | null) => formatPercent(value),
      },
      {
        title: "最大回撤",
        dataIndex: "maxDrawdown",
        key: "maxDrawdown",
        width: 120,
        render: (value: number | null) => formatPercent(value),
      },
      {
        title: "Sharpe",
        dataIndex: "sharpe",
        key: "sharpe",
        width: 100,
        render: (value: number | null) => (value !== null ? value.toFixed(2) : "-"),
      },
      {
        title: (
          <Space size={4}>
            综合分数
            <Tooltip title={renderPerformanceScoreTooltip()}>
              <QuestionCircleOutlined />
            </Tooltip>
          </Space>
        ),
        dataIndex: "score",
        key: "score",
        width: 130,
        sorter: (a, b) => (a.score ?? Number.NEGATIVE_INFINITY) - (b.score ?? Number.NEGATIVE_INFINITY),
        render: (value: number | null | undefined) => (value !== null && value !== undefined ? value.toFixed(2) : "-"),
      },
      {
        title: "总结",
        dataIndex: "summary",
        key: "summary",
        ellipsis: true,
      },
      {
        title: "操作",
        key: "actions",
        width: 170,
        fixed: "right",
        render: (_, record) => (
          <Space size={12} className="table-action-links">
            <Button type="link" onClick={() => void openIterationPreview(record)}>
              查看详情
            </Button>
            <Button
              type="link"
              loading={savingIterationStrategyId === record.id}
              onClick={() => void saveStrategyFromIteration(record, `第 ${record.iterationNumber} 轮策略`)}
            >
              保存为策略
            </Button>
          </Space>
        ),
      },
    ],
    [openIterationPreview, saveStrategyFromIteration, savingIterationStrategyId],
  );

  const bestAnnualIteration = useMemo(() => {
    return iterations.reduce<AgentIterationItem | null>((best, item) => {
      if (item.annualReturn === null) {
        return best;
      }
      if (!best || best.annualReturn === null || item.annualReturn > best.annualReturn) {
        return item;
      }
      return best;
    }, null);
  }, [iterations]);

  const bestCompositeIteration = useMemo(() => {
    if (task?.bestScore !== null && task?.bestScore !== undefined) {
      const matched = iterations.find(
        (item) => item.score !== null && item.score !== undefined && Math.abs(item.score - task.bestScore!) < 0.0001,
      );
      if (matched) {
        return matched;
      }
    }
    if (task?.bestAnnualReturn === null || task?.bestAnnualReturn === undefined) {
      return null;
    }
    return (
      iterations.find(
        (item) => item.annualReturn !== null && Math.abs(item.annualReturn - task.bestAnnualReturn!) < 0.0001,
      ) ?? null
    );
  }, [iterations, task?.bestAnnualReturn, task?.bestScore]);

  const bestMaxDrawdown = task?.bestMaxDrawdown ?? bestCompositeIteration?.maxDrawdown ?? null;
  const bestSharpe = task?.bestSharpe ?? bestCompositeIteration?.sharpe ?? null;
  const bestCompositeScore = task?.bestScore ?? bestCompositeIteration?.score ?? null;
  const bestCompositeStrategyConfig = asStrategyDslConfig(
    (bestCompositeIteration?.strategyConfig as Record<string, unknown> | undefined) ?? task?.bestStrategyConfig ?? null,
  );
  const iterationPercent = task ? Math.min(100, Math.round((task.currentIteration / Math.max(task.maxIterations, 1)) * 100)) : 0;

  const handleSaveBestAnnualStrategy = useCallback(async () => {
    if (!task || !bestAnnualIteration?.strategyConfig) {
      messageApi.warning("当前还没有可保存的最佳年化收益策略。");
      return;
    }

    try {
      setSavingBestAnnualStrategy(true);
      await saveStrategyFromIteration(bestAnnualIteration, "最佳年化收益策略");
    } finally {
      setSavingBestAnnualStrategy(false);
    }
  }, [bestAnnualIteration, messageApi, saveStrategyFromIteration, task]);

  const handleSaveBestCompositeStrategy = useCallback(async () => {
    if (!task?.bestStrategyConfig) {
      messageApi.warning("当前还没有可保存的最佳综合表现策略。");
      return;
    }

    try {
      setSavingBestCompositeStrategy(true);
      const token = getAccessToken();
      await apiPost(
        "/strategies",
        {
          name: `${task.name} - 最佳综合表现策略`,
          type: "AI Agent",
          source: "人工创建",
          countryRegion: task.countryCode,
          assetType: task.assetType,
          assetIdentifier: task.assetIdentifier,
          assetName: task.assetName,
          strategyConfig: task.bestStrategyConfig,
          annualReturn: bestCompositeIteration?.annualReturn ?? task.bestAnnualReturn,
          maxDrawdown: bestCompositeIteration?.maxDrawdown ?? task.bestMaxDrawdown ?? null,
        },
        token,
      );
      messageApi.success("当前最佳综合表现策略已保存。");
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "保存当前最佳综合表现策略失败。");
    } finally {
      setSavingBestCompositeStrategy(false);
    }
  }, [bestCompositeIteration, messageApi, task]);

  return (
    <AppShell>
      {contextHolder}
      <section className="dashboard-heading">
        <div>
          <Title level={1}>Agent 任务详情</Title>
          <Text className="page-description">查看任务配置、运行状态、每轮思考过程以及对应的收益预览。</Text>
        </div>
        <Space>
          <Link href="/agent-tasks">
            <Button icon={<ArrowLeftOutlined />}>返回列表</Button>
          </Link>
        </Space>
      </section>

      {!task && !loading ? (
        <Card className="dashboard-card" bordered>
          <EmptyState title="未找到对应的 Agent 任务" compact />
        </Card>
      ) : null}

      {task ? (
        <>
          <div className="agent-task-detail-grid">
            <Card className="dashboard-card" bordered loading={loading} title="任务概览">
              <div className="agent-best-performance">
                <div className="agent-best-performance-action">
                  <div className="agent-metric-title">
                    <Text type="secondary">当前最佳年化收益率</Text>
                    <Tooltip title="保存当前最佳年化收益对应的迭代策略">
                      <Button
                        type="text"
                        size="small"
                        icon={<SaveOutlined />}
                        loading={savingBestAnnualStrategy}
                        onClick={() => void handleSaveBestAnnualStrategy()}
                      />
                    </Tooltip>
                  </div>
                  <strong className={bestAnnualIteration?.annualReturn !== null && bestAnnualIteration?.annualReturn !== undefined && bestAnnualIteration.annualReturn < 0 ? "negative-text" : "positive-text"}>
                    {formatPercent(bestAnnualIteration?.annualReturn ?? null)}
                  </strong>
                </div>
                <div className="agent-best-performance-action">
                  <div className="agent-metric-title">
                    <Text type="secondary">
                      当前最佳综合分数{" "}
                      <Tooltip title={renderPerformanceScoreTooltip()}>
                        <QuestionCircleOutlined />
                      </Tooltip>
                    </Text>
                    <Tooltip title="保存当前最佳综合表现对应的策略">
                      <Button
                        type="text"
                        size="small"
                        icon={<SaveOutlined />}
                        loading={savingBestCompositeStrategy}
                        onClick={() => void handleSaveBestCompositeStrategy()}
                      />
                    </Tooltip>
                  </div>
                  <strong>{bestCompositeScore !== null && bestCompositeScore !== undefined ? bestCompositeScore.toFixed(2) : "-"}</strong>
                </div>
                <div>
                  <Text type="secondary">最大回撤</Text>
                  <strong className="negative-text">{formatPercent(bestMaxDrawdown)}</strong>
                </div>
                <div>
                  <Text type="secondary">Sharpe</Text>
                  <strong>{bestSharpe !== null && bestSharpe !== undefined ? bestSharpe.toFixed(2) : "-"}</strong>
                </div>
              </div>
              <div className="agent-best-progress-row">
                <div className="agent-metric-title">
                  <Text type="secondary">迭代进度</Text>
                </div>
                <Progress percent={iterationPercent} size="small" />
                <span>{task.currentIteration} / {task.maxIterations}</span>
              </div>
              <div className="agent-task-detail-meta">
                <div>
                  <Text type="secondary">任务名称</Text>
                  {editingName ? (
                    <div className="agent-task-name-editor">
                      <Input
                        value={draftName}
                        autoFocus
                        onChange={(event) => setDraftName(event.target.value)}
                        onPressEnter={() => void handleSaveName()}
                      />
                      <Button
                        type="text"
                        size="small"
                        icon={<CheckOutlined />}
                        loading={savingName}
                        onClick={() => void handleSaveName()}
                      />
                      <Button
                        type="text"
                        size="small"
                        icon={<CloseOutlined />}
                        disabled={savingName}
                        onClick={() => {
                          setDraftName(task.name);
                          setEditingName(false);
                        }}
                      />
                    </div>
                  ) : (
                    <div className="agent-task-name-view">
                      <Tooltip title={task.name}>
                        <Title level={4} className="agent-task-name-ellipsis">{task.name}</Title>
                      </Tooltip>
                      <Button
                        type="text"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => {
                          setDraftName(task.name);
                          setEditingName(true);
                        }}
                      />
                    </div>
                  )}
                </div>
                <div>
                  <Text type="secondary">状态</Text>
                  <div className="agent-task-status-text">{statusMeta[task.status].label}</div>
                </div>
                <div>
                  <Text type="secondary">标的</Text>
                  <div className="agent-task-asset-name">{task.assetName}</div>
                  <Text type="secondary">{task.assetIdentifier}</Text>
                </div>
                <div>
                  <Text type="secondary">AI 模型</Text>
                  <div>{task.aiModelName || "-"}</div>
                </div>
                <div>
                  <Text type="secondary">当前迭代</Text>
                  <div>
                    {task.currentIteration} / {task.maxIterations}
                  </div>
                </div>
                <div>
                  <Text type="secondary">最近更新时间</Text>
                  <div>{formatDateTime(task.updatedAt)}</div>
                </div>
              </div>
            </Card>

            <Card className="dashboard-card" bordered loading={loading} title="目标与回测参数">
              <div className="agent-task-detail-meta">
                <div>
                  <Text type="secondary">目标年化收益率</Text>
                  <div>{formatPercent(task.targetAnnualReturn)}</div>
                </div>
                <div>
                  <Text type="secondary">最大可接受回撤</Text>
                  <div>{formatPercent(task.maxDrawdownLimit)}</div>
                </div>
                <div>
                  <Text type="secondary">最低 Sharpe</Text>
                  <div>{task.minSharpe !== null ? task.minSharpe.toFixed(2) : "-"}</div>
                </div>
                <div>
                  <Text type="secondary">回测区间</Text>
                  <div>
                    {task.backtestStartDate ?? "-"} 至 {task.backtestEndDate ?? "-"}
                  </div>
                </div>
              </div>
            </Card>
          </div>

          <div className="agent-task-detail-grid">
            <Card className="dashboard-card agent-task-detail-card-equal" bordered title="任务说明与迭代思路">
              <Paragraph className="agent-task-detail-paragraph">
                {renderOptionalText(task.note, "暂无任务说明。")}
              </Paragraph>
              {iterations.length ? (
                <div className="agent-iteration-thoughts">
                  {iterations.map((iteration) => (
                    <div key={iteration.id} className="agent-iteration-thought-card">
                      <div className="agent-iteration-thought-head">
                        <strong>第 {iteration.iterationNumber} 轮</strong>
                        <Space size={8}>
                          <Tag color="blue">{iteration.intentLabel || iteration.intent || "未记录"}</Tag>
                          <Tag color={statusMeta[iteration.status as keyof typeof statusMeta]?.color ?? "default"}>
                            {statusMeta[iteration.status as keyof typeof statusMeta]?.label ?? iteration.status}
                          </Tag>
                        </Space>
                      </div>
                      <div className="agent-iteration-thought-block">
                        <Text type="secondary">分析</Text>
                        <Paragraph className="agent-task-detail-paragraph">
                          {iteration.analysis || "本轮未返回单独分析，已根据结果自动生成简要说明。"}
                        </Paragraph>
                      </div>
                      <div className="agent-iteration-thought-block">
                        <Text type="secondary">决策</Text>
                        <Paragraph className="agent-task-detail-paragraph">
                          {iteration.actionPlan || "本轮未返回单独决策，当前展示的是根据结果生成的默认决策建议。"}
                        </Paragraph>
                      </div>
                      <div className="agent-iteration-thought-block">
                        <Text type="secondary">规则预览</Text>
                        <RuleReadonlyPreview value={asStrategyDslConfig(iteration.strategyConfig)} compact />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="暂无迭代分析与决策" compact />
              )}
            </Card>

            <Card
              className="dashboard-card agent-task-detail-card-equal"
              bordered
              title="当前最佳综合表现"
            >
              <div className="agent-best-composite-content">
                {renderOptionalText(task.bestSummary, "") ? (
                  <Paragraph className="agent-task-detail-paragraph">
                    {renderOptionalText(task.bestSummary, "暂无最佳策略总结")}
                  </Paragraph>
                ) : (
                  <EmptyState title="暂无最佳策略总结" compact />
                )}
                {bestCompositeStrategyConfig ? (
                  <div className="agent-best-rule-scroll">
                    <RuleReadonlyPreview value={bestCompositeStrategyConfig} />
                  </div>
                ) : null}
              </div>
            </Card>
          </div>

          <Card className="dashboard-card" bordered title="迭代记录">
            <Table<AgentIterationItem>
              rowKey="id"
              columns={iterationColumns}
              dataSource={iterations}
              pagination={false}
              locale={{
                emptyText: <EmptyState title="暂无迭代记录" compact />,
              }}
              scroll={{ x: 1190 }}
            />
          </Card>
        </>
      ) : null}

      <Modal
        title={previewIteration ? `第 ${previewIteration.iterationNumber} 轮详情` : "迭代详情"}
        open={previewOpen}
        onCancel={() => {
          setPreviewOpen(false);
          setPreviewResult(null);
          setPreviewIteration(null);
          setPreviewRange("current");
        }}
        footer={null}
        width={1120}
      >
        <Tabs
          activeKey={previewRange}
          items={previewRangeOptions.map((item) => ({ key: item.key, label: item.label }))}
          onChange={(key) => void handlePreviewRangeChange(key)}
        />
        {previewLoading ? <Card loading bordered={false} /> : null}
        {!previewLoading && previewResult ? (
          <AgentIterationPreviewPanel
            preview={previewResult}
            strategyConfig={previewIteration?.strategyConfig}
            iteration={previewIteration}
          />
        ) : null}
        {!previewLoading && !previewResult ? <EmptyState title="暂无收益预览" compact /> : null}
      </Modal>
    </AppShell>
  );
}

function MiniEquityCompareChart({
  preview,
}: {
  preview?: {
    equityCurve: Array<{ date: string; value: number }>;
    benchmarkCurve: Array<{ date: string; value: number }>;
  } | null;
}) {
  const width = 118;
  const height = 42;
  const padding = 3;
  const strategyValues = preview?.equityCurve?.map((item) => item.value).filter((value) => Number.isFinite(value)) ?? [];
  const benchmarkValues = preview?.benchmarkCurve?.map((item) => item.value).filter((value) => Number.isFinite(value)) ?? [];
  const total = Math.min(strategyValues.length, benchmarkValues.length);

  if (!preview || total < 2) {
    return <span className="backtest-mini-chart-empty">暂无曲线</span>;
  }

  const strategySeries = strategyValues.slice(0, total);
  const benchmarkSeries = benchmarkValues.slice(0, total);
  const allValues = [...strategySeries, ...benchmarkSeries];
  const minValue = Math.min(...allValues);
  const maxValue = Math.max(...allValues);
  const span = maxValue - minValue || 1;

  const toPath = (values: number[]) =>
    values
      .map((value, index) => {
        const x = padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
        const y = padding + (1 - (value - minValue) / span) * (height - padding * 2);
        return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");

  return (
    <Tooltip title="策略净值 vs 买入持有基准">
      <svg className="backtest-mini-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="策略净值和买入持有基准对比">
        <path d={toPath(benchmarkSeries)} className="backtest-mini-chart-benchmark" />
        <path d={toPath(strategySeries)} className="backtest-mini-chart-strategy" />
      </svg>
    </Tooltip>
  );
}
