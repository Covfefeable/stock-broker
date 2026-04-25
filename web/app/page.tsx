"use client";

import {
  DatabaseOutlined,
  NodeIndexOutlined,
  RobotOutlined,
  RiseOutlined,
} from "@ant-design/icons";
import { Badge, Button, Card, Col, Progress, Row, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { apiGet } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

const { Text, Title } = Typography;

type RankingRow = {
  id: number;
  rank: number;
  name: string;
  type: string;
  source: string;
  annualReturn: string | null;
  drawdown: string | null;
  status: string;
  updatedAt: string | null;
};

type AgentTaskRow = {
  id: number;
  name: string;
  status: string;
  currentIteration: number;
  maxIterations: number;
  bestAnnualReturn: string | null;
  targetAnnualReturn: string | null;
};

type SyncStatusRow = {
  target: string;
  name: string;
  status: "success" | "empty";
  latestEvent: { status: string; message: string; time: string | null } | null;
};

type RecentBacktestRow = {
  id: number;
  name: string;
  annualReturn: string | null;
  drawdown: string | null;
  status: string;
  updatedAt: string | null;
};

type StrategyAlert = {
  id: number;
  type: string;
  level: "warning" | "danger";
  message: string;
};

type DashboardOverview = {
  metrics: {
    syncedAssetCount: number;
    strategyCount: number;
    bestAnnualReturn: string | null;
    agentTaskCount: number;
    runningAgentTaskCount: number;
  };
  ranking: RankingRow[];
  agentTasks: AgentTaskRow[];
  syncStatus: SyncStatusRow[];
  recentBacktests: RecentBacktestRow[];
  strategyAlerts: StrategyAlert[];
};

const emptyOverview: DashboardOverview = {
  metrics: {
    syncedAssetCount: 0,
    strategyCount: 0,
    bestAnnualReturn: null,
    agentTaskCount: 0,
    runningAgentTaskCount: 0,
  },
  ranking: [],
  agentTasks: [],
  syncStatus: [],
  recentBacktests: [],
  strategyAlerts: [],
};

const rankingColumns: ColumnsType<RankingRow> = [
  { title: "排名", dataIndex: "rank", width: 70 },
  { title: "策略名称", dataIndex: "name" },
  {
    title: "类型",
    dataIndex: "type",
    render: (value: string) => <Tag>{value}</Tag>,
  },
  {
    title: "来源",
    dataIndex: "source",
    render: (value: string) => <Tag color={value === "AI 生成" ? "purple" : "blue"}>{value}</Tag>,
  },
  {
    title: "年化收益",
    dataIndex: "annualReturn",
    render: (value: string | null) => <Text className={value?.startsWith("-") ? "negative-text" : "positive-text"}>{value ?? "-"}</Text>,
  },
  {
    title: "最大回撤",
    dataIndex: "drawdown",
    render: (value: string | null) => <Text className="negative-text">{value ?? "-"}</Text>,
  },
  { title: "状态", dataIndex: "status", render: (value: string) => <Tag>{value}</Tag> },
  { title: "更新时间", dataIndex: "updatedAt", render: formatDate },
  {
    title: "操作",
    render: (_value, row) => (
      <Link href={`/strategy-builder/${row.id}`}>
        查看
      </Link>
    ),
  },
];

export default function Home() {
  const [overview, setOverview] = useState<DashboardOverview>(emptyOverview);
  const [loading, setLoading] = useState(true);

  const loadOverview = useCallback(async () => {
    setLoading(true);
    try {
      const token = getAccessToken();
      const payload = await apiGet<DashboardOverview>("/dashboard/overview", token);
      setOverview(payload);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  const metrics = useMemo(
    () => [
      {
        title: "已同步股票/指数",
        value: formatInteger(overview.metrics.syncedAssetCount),
        icon: <DatabaseOutlined />,
      },
      {
        title: "策略总数",
        value: formatInteger(overview.metrics.strategyCount),
        icon: <NodeIndexOutlined />,
      },
      {
        title: "最佳年化收益",
        value: overview.metrics.bestAnnualReturn ?? "-",
        icon: <RiseOutlined />,
        positive: Boolean(overview.metrics.bestAnnualReturn && !overview.metrics.bestAnnualReturn.startsWith("-")),
      },
      {
        title: "AI Agent 任务",
        value: formatInteger(overview.metrics.agentTaskCount),
        icon: <RobotOutlined />,
      },
    ],
    [overview.metrics],
  );

  return (
    <AppShell>
      <section className="dashboard-heading">
        <div>
          <Title level={1}>总览</Title>
          <Text className="page-description">
            查看数据同步、策略表现、回测结果与 AI Agent 运行状态。
          </Text>
        </div>
        <Space>
          <Link href="/strategy-builder/new">
            <Button>新建策略</Button>
          </Link>
          <Link href="/agent-tasks/new">
            <Button type="primary">创建 AI Agent 任务</Button>
          </Link>
        </Space>
      </section>

      <Row gutter={[20, 20]} className="equal-height-row">
        {metrics.map((metric) => (
          <Col xs={24} md={12} xl={6} key={metric.title}>
            <Card className="metric-card dashboard-card" loading={loading}>
              <div className="metric-card-head">
                <Text>{metric.title}</Text>
                <span className="metric-icon">{metric.icon}</span>
              </div>
              <strong className={metric.positive ? "positive-text" : ""}>{metric.value}</strong>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[20, 20]} className="dashboard-main-row equal-height-row">
        <Col xs={24} xl={16}>
          <Card className="dashboard-card ranking-panel ranking-panel-main" title="策略排行榜" loading={loading}>
            <Table
              columns={rankingColumns}
              dataSource={overview.ranking}
              rowKey="id"
              pagination={false}
              size="middle"
              scroll={{ x: 860 }}
            />
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <Card
            className="dashboard-card agent-panel"
            title="AI Agent 运行状态"
            loading={loading}
            extra={<Link href="/agent-tasks">查看全部</Link>}
          >
            {overview.agentTasks.length ? (
              <Space orientation="vertical" size={22} className="full-width">
              {overview.agentTasks.map((task) => (
                <div className="agent-task" key={task.name}>
                  <div className="agent-task-title">
                    <strong>{task.name}</strong>
                    <Tag>{task.currentIteration}/{task.maxIterations}</Tag>
                  </div>
                  <Progress percent={getProgressPercent(task.currentIteration, task.maxIterations)} showInfo={false} />
                  <div className="agent-task-meta">
                    <Text>当前收益：{task.bestAnnualReturn ?? "-"}</Text>
                    <Text>目标：{task.targetAnnualReturn ?? "-"}</Text>
                  </div>
                </div>
              ))}
              </Space>
            ) : (
              <EmptyState title="暂无运行中的 Agent 任务" compact />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[20, 20]} className="dashboard-secondary-row equal-height-row">
        <Col xs={24} xl={8}>
          <Card
            className="dashboard-card"
            title="数据同步状态"
            loading={loading}
            extra={<Link href="/data-center">进入数据中心</Link>}
          >
            <div className="status-list">
              {overview.syncStatus.map((item) => (
                <div key={item.target}>
                  <Badge status={item.status === "success" ? "success" : "default"} text={item.name} />
                  <Text>{item.latestEvent ? formatStatus(item.latestEvent.status) : item.status === "success" ? "已有数据" : "暂无数据"}</Text>
                </div>
              ))}
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <Card className="dashboard-card" title="最近回测" loading={loading}>
            {overview.recentBacktests.length ? (
              <div className="compact-table">
              {overview.recentBacktests.map((item) => (
                <div className="compact-row" key={item.id}>
                  <span>{item.name}</span>
                  <Text className={item.annualReturn?.startsWith("-") ? "negative-text" : "positive-text"}>
                    {item.annualReturn ?? "-"}
                  </Text>
                  <Text className="negative-text">{item.drawdown ?? "-"}</Text>
                  <Tag>{item.status}</Tag>
                </div>
              ))}
              </div>
            ) : (
              <EmptyState title="暂无回测结果" compact />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <Card className="dashboard-card" title="策略校验提醒" loading={loading}>
            {overview.strategyAlerts.length ? (
              <Space orientation="vertical" size={14} className="full-width">
                {overview.strategyAlerts.map((item) => (
                  <div className="warning-item" key={item.id}>
                    <Tag color={item.level === "danger" ? "red" : "orange"}>{item.type}</Tag>
                    <Text>{item.message}</Text>
                  </div>
                ))}
              </Space>
            ) : (
              <EmptyState title="暂无策略提醒" compact />
            )}
          </Card>
        </Col>
      </Row>

    </AppShell>
  );
}

function formatInteger(value: number): string {
  return new Intl.NumberFormat("zh-CN").format(value);
}

function getProgressPercent(current: number, total: number): number {
  if (!total) return 0;
  return Math.min(100, Math.round((current / total) * 100));
}

function formatStatus(status: string): string {
  if (status === "success") return "已完成";
  if (status === "running") return "运行中";
  if (status === "queued") return "排队中";
  if (status === "partial_success") return "部分完成";
  return "失败";
}

function formatDate(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}
