"use client";

import {
  ApiOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import {
  Badge,
  Button,
  Card,
  Col,
  DatePicker,
  Input,
  Progress,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { AppShell } from "@/components/app-shell";

const { RangePicker } = DatePicker;
const { Text, Title } = Typography;

type IssueRow = {
  key: string;
  issueType: string;
  dataset: string;
  affected: string;
  severity: "轻微" | "中等" | "严重";
  status: string;
};

type PriceRow = {
  key: string;
  code: string;
  name: string;
  date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
  amount: string;
  change: string;
  status: string;
};

type LogRow = {
  key: string;
  time: string;
  task: string;
  dataset: string;
  trigger: string;
  cost: string;
  status: "成功" | "部分成功" | "失败" | "运行中";
};

const overviewCards = [
  {
    title: "股票标的",
    value: "12,846",
    suffix: "只",
    description: "A 股、港股、美股可用标的",
    status: "基础信息已更新",
    icon: <DatabaseOutlined />,
  },
  {
    title: "日线行情",
    value: "38,624,910",
    description: "历史价格记录",
    status: "最新日期 2026-04-22",
    icon: <ClockCircleOutlined />,
  },
  {
    title: "指数数据",
    value: "342",
    suffix: "个",
    description: "可用指数",
    status: "已同步",
    icon: <ApiOutlined />,
  },
  {
    title: "数据质量",
    value: "98.7",
    suffix: "%",
    description: "完整率",
    status: "发现 14 个轻微问题",
    icon: <SafetyCertificateOutlined />,
  },
];

const syncTasks = [
  ["A 股日线行情", "已完成", "2026-04-22 18:18", "5,214 只股票", "success"],
  ["港股日线行情", "已完成", "2026-04-22 18:46", "2,812 只股票", "success"],
  ["美股日线行情", "已完成", "2026-04-22 21:12", "4,820 只股票", "success"],
  ["全球指数行情", "已完成", "2026-04-22 21:20", "342 个指数", "success"],
  ["财务因子", "部分完成", "2026-04-22 21:35", "10,984 只股票", "warning"],
];

const dataSources = [
  { name: "Tushare", status: "正常", calls: "今日调用 8,420" },
  { name: "AkShare", status: "正常", calls: "今日调用 1,280" },
  { name: "Polygon", status: "正常", calls: "今日调用 18,640" },
  { name: "HKEX 文件源", status: "正常", calls: "今日调用 3" },
  { name: "财务数据源", status: "警告", calls: "今日调用 2,416" },
];

const completeness: Array<[string, number]> = [
  ["A 股日线行情", 99.2],
  ["港股日线行情", 99.5],
  ["美股日线行情", 99.1],
  ["全球指数行情", 100],
  ["财务因子", 94.8],
  ["公司行动 / 复权因子", 99.7],
];

const issues: IssueRow[] = [
  { key: "1", issueType: "缺失交易日", dataset: "港股日线行情", affected: "8 只股票", severity: "轻微", status: "待修复" },
  { key: "2", issueType: "财务字段为空", dataset: "美股财务因子", affected: "232 只股票", severity: "中等", status: "处理中" },
  { key: "3", issueType: "成交量异常", dataset: "A 股日线行情", affected: "3 只股票", severity: "轻微", status: "已标记" },
  { key: "4", issueType: "非交易日多余记录", dataset: "美股日线行情", affected: "1 只股票", severity: "严重", status: "待修复" },
];

const prices: PriceRow[] = [
  { key: "1", code: "600519.SH", name: "贵州茅台", date: "2026-04-22", open: "1580.20", high: "1602.80", low: "1575.00", close: "1598.50", volume: "32,450", amount: "51.8 亿 CNY", change: "+1.24%", status: "正常" },
  { key: "2", code: "0700.HK", name: "腾讯控股", date: "2026-04-22", open: "392.20", high: "398.40", low: "389.80", close: "396.60", volume: "18,420", amount: "72.9 亿 HKD", change: "+1.88%", status: "正常" },
  { key: "3", code: "AAPL", name: "Apple", date: "2026-04-22", open: "188.40", high: "191.10", low: "187.30", close: "190.82", volume: "48,620,400", amount: "92.8 亿 USD", change: "+1.16%", status: "正常" },
  { key: "4", code: "9988.HK", name: "阿里巴巴-W", date: "2026-04-22", open: "83.50", high: "85.20", low: "82.90", close: "84.85", volume: "298,100", amount: "25.1 亿 HKD", change: "+1.62%", status: "正常" },
  { key: "5", code: "MSFT", name: "Microsoft", date: "2026-04-22", open: "416.80", high: "421.50", low: "415.90", close: "420.70", volume: "19,630,000", amount: "82.6 亿 USD", change: "+0.98%", status: "正常" },
];

const logs: LogRow[] = [
  { key: "1", time: "2026-04-22 21:40", task: "美股公司行动同步", dataset: "复权因子", trigger: "自动", cost: "3 分 12 秒", status: "成功" },
  { key: "2", time: "2026-04-22 21:35", task: "全球财务因子同步", dataset: "财务因子", trigger: "自动", cost: "12 分 48 秒", status: "部分成功" },
  { key: "3", time: "2026-04-22 21:20", task: "全球指数行情同步", dataset: "指数行情", trigger: "自动", cost: "1 分 06 秒", status: "成功" },
  { key: "4", time: "2026-04-22 18:46", task: "港股日线同步", dataset: "港股日线行情", trigger: "自动", cost: "6 分 34 秒", status: "成功" },
  { key: "5", time: "2026-04-22 18:18", task: "A 股日线同步", dataset: "A 股日线行情", trigger: "自动", cost: "8 分 34 秒", status: "成功" },
];

const issueColumns: ColumnsType<IssueRow> = [
  { title: "问题类型", dataIndex: "issueType" },
  { title: "数据集", dataIndex: "dataset" },
  { title: "影响标的", dataIndex: "affected" },
  {
    title: "严重程度",
    dataIndex: "severity",
    render: (value: IssueRow["severity"]) => (
      <Tag color={value === "严重" ? "red" : value === "中等" ? "orange" : "blue"}>{value}</Tag>
    ),
  },
  { title: "状态", dataIndex: "status" },
  {
    title: "操作",
    render: () => <Button type="link" size="small">查看</Button>,
  },
];

const priceColumns: ColumnsType<PriceRow> = [
  { title: "股票代码", dataIndex: "code", fixed: "left", width: 100 },
  { title: "股票名称", dataIndex: "name", fixed: "left", width: 120 },
  { title: "日期", dataIndex: "date", width: 120 },
  { title: "开盘价", dataIndex: "open" },
  { title: "最高价", dataIndex: "high" },
  { title: "最低价", dataIndex: "low" },
  { title: "收盘价", dataIndex: "close" },
  { title: "成交量", dataIndex: "volume" },
  { title: "成交额", dataIndex: "amount" },
  { title: "涨跌幅", dataIndex: "change", render: (value: string) => <Text className="positive-text">{value}</Text> },
  { title: "数据状态", dataIndex: "status", render: (value: string) => <Tag color="green">{value}</Tag> },
  { title: "操作", fixed: "right", width: 100, render: () => <Button type="link" size="small">详情</Button> },
];

const logColumns: ColumnsType<LogRow> = [
  { title: "时间", dataIndex: "time", width: 160 },
  { title: "任务名称", dataIndex: "task" },
  { title: "数据集", dataIndex: "dataset" },
  { title: "触发方式", dataIndex: "trigger" },
  { title: "耗时", dataIndex: "cost" },
  {
    title: "状态",
    dataIndex: "status",
    render: (value: LogRow["status"]) => (
      <Tag color={value === "成功" ? "green" : value === "部分成功" ? "orange" : value === "运行中" ? "blue" : "red"}>{value}</Tag>
    ),
  },
  { title: "详情", render: () => <Button type="link" size="small">查看</Button> },
];

export default function DataCenterPage() {
  return (
    <AppShell>
      <section className="dashboard-heading">
        <div>
          <Title level={1}>数据中心</Title>
          <Text className="page-description">
            管理 A 股、港股、美股等多市场行情、指数、基础信息与财务因子数据，监控同步状态、交易日历一致性和数据质量。
          </Text>
        </div>
        <Space>
          <Button icon={<SyncOutlined />}>手动同步</Button>
          <Button icon={<ApiOutlined />}>添加数据源</Button>
          <Button type="primary" icon={<FileSearchOutlined />}>数据质量检查</Button>
        </Space>
      </section>

      <Row gutter={[20, 20]} className="equal-height-row">
        {overviewCards.map((item) => (
          <Col xs={24} md={12} xl={6} key={item.title}>
            <Card className="metric-card dashboard-card">
              <div className="metric-card-head">
                <Text>{item.title}</Text>
                <span className="metric-icon">{item.icon}</span>
              </div>
              <strong className={item.title === "数据质量" ? "positive-text" : ""}>
                {item.value}{item.suffix ?? ""}
              </strong>
              <Text className="metric-hint">{item.description}，{item.status}</Text>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[20, 20]} className="dashboard-main-row equal-height-row">
        <Col xs={24} xl={15}>
          <Card
            className="dashboard-card data-sync-panel"
            title="数据同步概览"
            extra={<Button type="link">查看同步日志</Button>}
          >
            <div className="sync-timeline">
              {syncTasks.map(([name, status, time, amount, badgeStatus]) => (
                <div className="sync-task" key={name}>
                  <Badge status={badgeStatus as "success" | "warning"} />
                  <div>
                    <strong>{name}</strong>
                    <Text>{status} · {time} · {amount}</Text>
                  </div>
                </div>
              ))}
            </div>
            <div className="calendar-audit-bar">
              <div>
                <CheckCircleOutlined className="positive-text" />
                <span>多市场官方交易日历已验证</span>
              </div>
              <div>
                <SafetyCertificateOutlined className="positive-text" />
                <span>严格数据模式已开启</span>
              </div>
              <div>
                <ClockCircleOutlined />
                <span>下次自动同步：2026-04-23 18:00</span>
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={9}>
          <Card
            className="dashboard-card"
            title="数据源状态"
            extra={<Button type="link">管理数据源</Button>}
          >
            <div className="source-list">
              {dataSources.map((source) => (
                <div className="source-item source-item-simple" key={source.name}>
                  <div>
                    <strong>{source.name}</strong>
                  </div>
                  <div className="source-meta">
                    <Badge status={source.status === "正常" ? "success" : "warning"} text={source.status} />
                    <Text>{source.calls}</Text>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[20, 20]} className="dashboard-secondary-row equal-height-row">
        <Col xs={24} xl={10}>
          <Card className="dashboard-card" title="数据完整率">
            <Space direction="vertical" size={16} className="full-width">
              {completeness.map(([name, percent]) => (
                <div className="quality-progress" key={name}>
                  <div>
                    <Text>{name}</Text>
                    <strong>{percent}%</strong>
                  </div>
                  <Progress percent={percent as number} showInfo={false} status={percent < 96 ? "exception" : "success"} />
                </div>
              ))}
            </Space>
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card className="dashboard-card" title="数据质量问题">
            <Table columns={issueColumns} dataSource={issues} pagination={false} size="small" />
          </Card>
        </Col>
      </Row>

      <Card className="dashboard-card data-browser-card" title="行情数据浏览器">
        <div className="data-filter-row">
          <Input.Search placeholder="输入股票代码或名称" allowClear />
          <Select defaultValue="all" options={[
            { label: "全部市场", value: "all" },
            { label: "A 股", value: "cn" },
            { label: "港股", value: "hk" },
            { label: "美股", value: "us" },
          ]} />
          <Select defaultValue="daily" options={[
            { label: "日线行情", value: "daily" },
            { label: "基础信息", value: "basic" },
            { label: "财务因子", value: "financial" },
            { label: "复权因子", value: "adjust" },
          ]} />
          <RangePicker />
          <Button type="primary">查询</Button>
        </div>
        <Table
          columns={priceColumns}
          dataSource={prices}
          pagination={{ pageSize: 5 }}
          size="middle"
          scroll={{ x: 1180 }}
        />
      </Card>

      <Card className="dashboard-card data-log-card" title="最近同步日志">
        <Table
          columns={logColumns}
          dataSource={logs}
          pagination={false}
          size="middle"
          scroll={{ x: 880 }}
        />
      </Card>
    </AppShell>
  );
}
