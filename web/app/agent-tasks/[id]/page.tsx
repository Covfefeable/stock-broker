"use client";

import { ArrowLeftOutlined } from "@ant-design/icons";
import { Button, Card, Collapse, Empty, Modal, Space, Table, Tag, Tooltip, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import type { AgentIterationItem, AgentTaskDetailResponse, AgentTaskItem } from "@/components/agent-tasks/types";
import { StrategyPreviewChart } from "@/components/strategy-builder/strategy-preview-chart";
import type { StrategyPreviewResult } from "@/components/strategy-builder/types";
import { getAccessToken } from "@/lib/auth";
import { apiGet, apiPost } from "@/lib/api";

const { Title, Text, Paragraph } = Typography;

const statusMeta = {
  queued: { label: "排队中", color: "default" },
  running: { label: "运行中", color: "processing" },
  success: { label: "已完成", color: "success" },
  failure: { label: "失败", color: "error" },
} as const;

function formatPercent(value: number | null | undefined) {
  return value === null || value === undefined ? "-" : `${value.toFixed(2)}%`;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
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
  const [dslOpen, setDslOpen] = useState(false);
  const [dslIteration, setDslIteration] = useState<AgentIterationItem | null>(null);
  const [savingBestStrategy, setSavingBestStrategy] = useState(false);

  const loadDetail = useCallback(async () => {
    setLoading(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<AgentTaskDetailResponse>(`/agent-tasks/${params.id}`, token);
      setTask(response.task);
      setIterations(response.iterations);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载 Agent 任务详情失败。");
    } finally {
      setLoading(false);
    }
  }, [messageApi, params.id]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const openIterationPreview = useCallback(
    async (iteration: AgentIterationItem) => {
      try {
        setPreviewLoading(true);
        setPreviewIteration(iteration);
        setPreviewOpen(true);
        const token = getAccessToken();
        const response = await apiGet<StrategyPreviewResult>(
          `/agent-tasks/${params.id}/iterations/${iteration.id}/preview`,
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
        title: "总结",
        dataIndex: "summary",
        key: "summary",
        ellipsis: true,
      },
      {
        title: "操作",
        key: "actions",
        width: 180,
        render: (_, record) => (
          <Space size={4}>
            <Button type="link" onClick={() => void openIterationPreview(record)}>
              查看收益
            </Button>
            <Button
              type="link"
              onClick={() => {
                setDslIteration(record);
                setDslOpen(true);
              }}
            >
              查看 DSL
            </Button>
          </Space>
        ),
      },
    ],
    [openIterationPreview],
  );

  const handleSaveBestStrategy = useCallback(async () => {
    if (!task?.bestStrategyConfig) {
      messageApi.warning("当前还没有可保存的最佳策略。");
      return;
    }

    const bestIteration =
      iterations.find(
        (item) =>
          item.annualReturn !== null &&
          task.bestAnnualReturn !== null &&
          Math.abs(item.annualReturn - task.bestAnnualReturn) < 0.0001,
      ) ?? null;

    try {
      setSavingBestStrategy(true);
      const token = getAccessToken();
      await apiPost(
        "/strategies",
        {
          name: `${task.name} - 最佳策略`,
          type: "AI Agent",
          source: "人工创建",
          countryRegion: task.countryCode,
          assetType: task.assetType,
          assetIdentifier: task.assetIdentifier,
          assetName: task.assetName,
          strategyConfig: task.bestStrategyConfig,
          annualReturn: task.bestAnnualReturn,
          maxDrawdown: bestIteration?.maxDrawdown ?? null,
        },
        token,
      );
      messageApi.success("当前最佳策略已保存。");
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "保存当前最佳策略失败。");
    } finally {
      setSavingBestStrategy(false);
    }
  }, [iterations, messageApi, task]);

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
          <Empty description="未找到对应的 Agent 任务" />
        </Card>
      ) : null}

      {task ? (
        <>
          <div className="agent-task-detail-grid">
            <Card className="dashboard-card" bordered loading={loading} title="任务概览">
              <div className="agent-task-detail-meta">
                <div>
                  <Text type="secondary">任务名称</Text>
                  <Title level={4}>{task.name}</Title>
                </div>
                <div>
                  <Text type="secondary">状态</Text>
                  <div>
                    <Tag color={statusMeta[task.status].color}>{statusMeta[task.status].label}</Tag>
                  </div>
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
                  <Text type="secondary">当前最佳收益</Text>
                  <div>{formatPercent(task.bestAnnualReturn)}</div>
                </div>
                <div>
                  <Text type="secondary">当前最佳 Sharpe</Text>
                  <div>{task.bestSharpe !== null ? task.bestSharpe.toFixed(2) : "-"}</div>
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
                  <Text type="secondary">初始资金</Text>
                  <div>{task.initialCapital?.toLocaleString("zh-CN") ?? "-"}</div>
                </div>
                <div>
                  <Text type="secondary">每次买入仓位</Text>
                  <div>{task.positionSize !== null ? `${(task.positionSize * 100).toFixed(2)}%` : "-"}</div>
                </div>
                <div>
                  <Text type="secondary">止损比例</Text>
                  <div>{task.stopLoss !== null ? `${(task.stopLoss * 100).toFixed(2)}%` : "-"}</div>
                </div>
                <div>
                  <Text type="secondary">止盈比例</Text>
                  <div>{task.takeProfit !== null ? `${(task.takeProfit * 100).toFixed(2)}%` : "-"}</div>
                </div>
                <div>
                  <Text type="secondary">最大持仓天数</Text>
                  <div>{task.maxHoldingDays}</div>
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
              <Paragraph className="agent-task-detail-paragraph">{task.note || "暂无任务说明。"}</Paragraph>
              {iterations.length ? (
                <div className="agent-iteration-thoughts">
                  {iterations.map((iteration) => (
                    <div key={iteration.id} className="agent-iteration-thought-card">
                      <div className="agent-iteration-thought-head">
                        <strong>第 {iteration.iterationNumber} 轮</strong>
                        <Tag color={statusMeta[iteration.status as keyof typeof statusMeta]?.color ?? "default"}>
                          {statusMeta[iteration.status as keyof typeof statusMeta]?.label ?? iteration.status}
                        </Tag>
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
                        <Text type="secondary">记忆</Text>
                        <Paragraph className="agent-task-detail-paragraph">
                          {iteration.memory || "本轮未保存记忆，当前展示的是基于策略结果生成的简要记忆。"}
                        </Paragraph>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty description="暂无迭代分析与决策" />
              )}
            </Card>

            <Card
              className="dashboard-card agent-task-detail-card-equal"
              bordered
              title="当前最佳策略"
              extra={
                <Button type="primary" size="small" loading={savingBestStrategy} onClick={() => void handleSaveBestStrategy()}>
                  保存为策略
                </Button>
              }
            >
              {task.bestSummary ? (
                <Paragraph className="agent-task-detail-paragraph">{task.bestSummary}</Paragraph>
              ) : (
                <Empty description="暂无最佳策略总结" />
              )}
              {task.bestStrategyConfig ? (
                <Collapse
                  ghost
                  items={[
                    {
                      key: "best-strategy-dsl",
                      label: "查看 DSL",
                      children: <pre className="strategy-dsl-code-block">{JSON.stringify(task.bestStrategyConfig, null, 2)}</pre>,
                    },
                  ]}
                />
              ) : null}
            </Card>
          </div>

          <Card className="dashboard-card" bordered title="迭代记录">
            <Table<AgentIterationItem>
              rowKey="id"
              columns={iterationColumns}
              dataSource={iterations}
              pagination={false}
              locale={{ emptyText: "暂无迭代记录" }}
            />
          </Card>
        </>
      ) : null}

      <Modal
        title={previewIteration ? `第 ${previewIteration.iterationNumber} 轮收益预览` : "收益预览"}
        open={previewOpen}
        onCancel={() => {
          setPreviewOpen(false);
          setPreviewResult(null);
          setPreviewIteration(null);
        }}
        footer={null}
        width={1120}
      >
        {previewLoading ? (
          <Card loading bordered={false} />
        ) : previewResult ? (
          <div className="strategy-preview-panel">
            <div className="strategy-preview-metrics">
              {[
                ["年化收益", `${previewResult.annualReturn.toFixed(2)}%`, `${previewResult.benchmarkAnnualReturn.toFixed(2)}%`],
                ["总收益", `${previewResult.totalReturn.toFixed(2)}%`, `${previewResult.benchmarkReturn.toFixed(2)}%`],
                ["最大回撤", `${previewResult.maxDrawdown.toFixed(2)}%`, `${previewResult.benchmarkMaxDrawdown.toFixed(2)}%`],
                ["波动率", `${previewResult.volatility.toFixed(2)}%`, `${previewResult.benchmarkVolatility.toFixed(2)}%`],
                ["Sharpe", previewResult.sharpe.toFixed(2), previewResult.benchmarkSharpe.toFixed(2)],
                ["胜率", `${previewResult.winRate.toFixed(2)}%`, `${previewResult.benchmarkWinRate.toFixed(2)}%`],
                ["交易次数", String(previewResult.tradeCount), String(previewResult.benchmarkTradeCount)],
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

            <StrategyPreviewChart preview={previewResult} />

            <div className="strategy-preview-range">
              <Text type="secondary">
                回测区间：{previewResult.dateRange.start ?? "--"} 至 {previewResult.dateRange.end ?? "--"}
              </Text>
            </div>

            <Table
              className="strategy-preview-trades"
              size="small"
              pagination={false}
              scroll={{ y: 240 }}
              rowKey={(record) => `${record.date}_${record.side}_${record.price}`}
              dataSource={previewResult.trades}
              locale={{ emptyText: "暂无成交记录" }}
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
                  render: (value: string) => (
                    <Tooltip title={value}>
                      <span>{value}</span>
                    </Tooltip>
                  ),
                },
              ]}
            />
          </div>
        ) : (
          <Empty description="暂无收益预览" />
        )}
      </Modal>

      <Modal
        title={dslIteration ? `第 ${dslIteration.iterationNumber} 轮 DSL` : "策略 DSL"}
        open={dslOpen}
        onCancel={() => {
          setDslOpen(false);
          setDslIteration(null);
        }}
        footer={null}
        width={920}
      >
        {dslIteration?.strategyConfig ? (
          <pre className="strategy-dsl-code-block">{JSON.stringify(dslIteration.strategyConfig, null, 2)}</pre>
        ) : (
          <Empty description="暂无 DSL 内容" />
        )}
      </Modal>
    </AppShell>
  );
}
