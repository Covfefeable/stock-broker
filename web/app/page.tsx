"use client";

import {
  BarChartOutlined,
  DatabaseOutlined,
  NodeIndexOutlined,
  RobotOutlined,
  RiseOutlined,
} from "@ant-design/icons";
import { Badge, Button, Card, Col, Progress, Row, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { AppShell } from "@/components/app-shell";

const { Text, Title } = Typography;

type RankingRow = {
  key: string;
  rank: number;
  name: string;
  type: string;
  source: string;
  annualReturn: string;
  drawdown: string;
  sharpe: string;
  complexity: number;
  date: string;
};

const metrics = [
  {
    title: "股票数据覆盖",
    value: "5,214",
    hint: "A 股可用标的，最新行情已同步",
    icon: <DatabaseOutlined />,
  },
  {
    title: "策略总数",
    value: "128",
    hint: "其中 24 个由 AI 生成，12 个已通过校验",
    icon: <NodeIndexOutlined />,
  },
  {
    title: "最佳年化收益",
    value: "18.6%",
    hint: "均线动量策略 v7，最大回撤 14.2%",
    icon: <RiseOutlined />,
    positive: true,
  },
  {
    title: "AI Agent 任务",
    value: "6",
    hint: "3 个运行中，本周新增 42 次迭代",
    icon: <RobotOutlined />,
  },
];

const agentTasks = [
  { name: "寻找低回撤动量策略", current: 23, total: 50, best: "15.8%", target: "18.4%" },
  { name: "价值因子组合优化", current: 11, total: 30, best: "12.4%", target: "16.1%" },
  { name: "中证 500 趋势策略探索", current: 37, total: 80, best: "19.1%", target: "22.5%" },
];

const recentBacktests = [
  ["均线动量策略 v7", "18.6%", "14.2%", "1.31", "已完成"],
  ["低波动价值策略 v3", "11.2%", "9.8%", "1.05", "已完成"],
  ["RSI 反转策略 v2", "-2.4%", "28.1%", "-0.12", "未通过"],
  ["多因子评分策略 v5", "16.1%", "17.6%", "1.18", "已完成"],
  ["AI 趋势策略 v12", "14.9%", "19.3%", "0.96", "警告"],
];

const rankingRows: RankingRow[] = [
  {
    key: "1",
    rank: 1,
    name: "均线动量策略 v7",
    type: "动量",
    source: "AI 生成",
    annualReturn: "18.6%",
    drawdown: "14.2%",
    sharpe: "1.31",
    complexity: 11,
    date: "2026-04-22",
  },
  {
    key: "2",
    rank: 2,
    name: "多因子评分策略 v5",
    type: "多因子",
    source: "人工创建",
    annualReturn: "16.1%",
    drawdown: "17.6%",
    sharpe: "1.18",
    complexity: 18,
    date: "2026-04-21",
  },
  {
    key: "3",
    rank: 3,
    name: "低回撤价值策略 v3",
    type: "价值",
    source: "AI 生成",
    annualReturn: "13.8%",
    drawdown: "8.9%",
    sharpe: "1.22",
    complexity: 14,
    date: "2026-04-20",
  },
  {
    key: "4",
    rank: 4,
    name: "趋势突破策略 v9",
    type: "趋势",
    source: "AI 生成",
    annualReturn: "12.7%",
    drawdown: "15.4%",
    sharpe: "0.97",
    complexity: 16,
    date: "2026-04-19",
  },
];

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
    render: (value: string) => <Text className="positive-text">{value}</Text>,
  },
  {
    title: "最大回撤",
    dataIndex: "drawdown",
    render: (value: string) => <Text className="negative-text">{value}</Text>,
  },
  { title: "夏普比率", dataIndex: "sharpe" },
  { title: "复杂度", dataIndex: "complexity" },
  { title: "最近回测", dataIndex: "date" },
  {
    title: "操作",
    render: () => (
      <Button size="small" type="link">
        查看
      </Button>
    ),
  },
];

export default function Home() {
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
          <Button>新建策略</Button>
          <Button icon={<BarChartOutlined />}>运行回测</Button>
          <Button type="primary">创建 AI Agent 任务</Button>
        </Space>
      </section>

      <Row gutter={[20, 20]}>
        {metrics.map((metric) => (
          <Col xs={24} md={12} xl={6} key={metric.title}>
            <Card className="metric-card">
              <div className="metric-card-head">
                <Text>{metric.title}</Text>
                <span className="metric-icon">{metric.icon}</span>
              </div>
              <strong className={metric.positive ? "positive-text" : ""}>{metric.value}</strong>
              <Text className="metric-hint">{metric.hint}</Text>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[20, 20]} className="dashboard-main-row">
        <Col xs={24} xl={16}>
          <Card className="ranking-panel ranking-panel-main" title="策略排行榜">
            <Table
              columns={rankingColumns}
              dataSource={rankingRows}
              pagination={false}
              size="middle"
              scroll={{ x: 980 }}
            />
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <Card
            className="agent-panel"
            title="AI Agent 运行状态"
            extra={<Button type="link">查看全部</Button>}
          >
            <Space direction="vertical" size={22} className="full-width">
              {agentTasks.map((task) => (
                <div className="agent-task" key={task.name}>
                  <div className="agent-task-title">
                    <strong>{task.name}</strong>
                    <Tag>{task.current}/{task.total}</Tag>
                  </div>
                  <Progress percent={Math.round((task.current / task.total) * 100)} showInfo={false} />
                  <div className="agent-task-meta">
                    <Text>当前收益：{task.best}</Text>
                    <Text>目标：{task.target}</Text>
                  </div>
                </div>
              ))}
            </Space>
          </Card>
        </Col>
      </Row>

      <Row gutter={[20, 20]} className="dashboard-secondary-row">
        <Col xs={24} xl={8}>
          <Card title="数据同步状态" extra={<Button type="link">进入数据中心</Button>}>
            <div className="status-list">
              {["日线行情", "股票基础信息", "指数行情", "复权因子"].map((item) => (
                <div key={item}>
                  <Badge status="success" text={item} />
                  <Text>已完成</Text>
                </div>
              ))}
              <div>
                <Badge status="warning" text="财务因子" />
                <Text>部分更新</Text>
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <Card title="最近回测">
            <div className="compact-table">
              {recentBacktests.map(([name, annual, drawdown, sharpe, status]) => (
                <div className="compact-row" key={name}>
                  <span>{name}</span>
                  <Text className={annual.startsWith("-") ? "negative-text" : "positive-text"}>
                    {annual}
                  </Text>
                  <Text className="negative-text">{drawdown}</Text>
                  <Text>{sharpe}</Text>
                  <Tag color={status === "未通过" ? "red" : status === "警告" ? "orange" : "green"}>
                    {status}
                  </Tag>
                </div>
              ))}
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <Card title="策略校验提醒">
            <Space direction="vertical" size={14} className="full-width">
              <div className="warning-item">
                <Tag color="orange">复杂度</Tag>
                <Text>AI 趋势策略 v12 复杂度评分过高，可能过拟合</Text>
              </div>
              <div className="warning-item">
                <Tag color="red">回撤</Tag>
                <Text>RSI 反转策略 v2 最大回撤超过限制</Text>
              </div>
              <div className="warning-item">
                <Tag color="gold">规则</Tag>
                <Text>均线突破策略 v4 规则嵌套深度接近上限</Text>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

    </AppShell>
  );
}
