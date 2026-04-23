"use client";

import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import {
  Badge,
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  Input,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { getAccessToken } from "@/lib/auth";
import { apiGet, apiPost } from "@/lib/api";

const { RangePicker } = DatePicker;
const { Text, Title } = Typography;

type SyncItemOption = {
  label: string;
  value: string;
};

type ExchangeOption = {
  label: string;
  value: string;
};

type CountryOption = {
  label: string;
  value: string;
};

type EventLogItem = {
  id: number;
  time: string | null;
  eventType: string;
  eventName: string;
  source: string | null;
  target: string | null;
  status: string;
  level: string;
  message: string;
  httpStatus: number | null;
  recordsAffected: number | null;
  durationMs: number | null;
};

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
  status: "成功" | "失败" | "运行中";
  message: string;
};

const syncItemOptions: SyncItemOption[] = [
  {
    label: "国家/地区清单",
    value: "country_list",
  },
  {
    label: "交易所清单",
    value: "exchange_list",
  },
  {
    label: "股票清单",
    value: "stock_list",
  },
  {
    label: "指数清单",
    value: "index_list",
  },
];

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
    title: "国家/地区",
    value: "待同步",
    description: "用于市场、时区和延迟信息",
    status: "已接入国家/地区与交易所字典同步",
    icon: <SafetyCertificateOutlined />,
  },
  {
    title: "数据质量",
    value: "98.7",
    suffix: "%",
    description: "完整率",
    status: "发现 14 个轻微问题",
    icon: <CheckCircleOutlined />,
  },
];

const syncTasks = [
  ["国家/地区清单", "可手动同步", "沧海数据", "基础字典表", "success"],
  ["交易所清单", "可手动同步", "沧海数据", "联动国家表", "success"],
  ["股票清单", "按交易所同步", "沧海数据", "联动交易所与国家表", "success"],
  ["指数清单", "按国家同步", "沧海数据", "联动国家表", "success"],
  ["A 股日线行情", "已完成", "2026-04-22 18:18", "5,214 只股票", "success"],
  ["港股日线行情", "已完成", "2026-04-22 18:46", "2,812 只股票", "success"],
  ["美股日线行情", "已完成", "2026-04-22 21:12", "4,820 只股票", "success"],
  ["财务因子", "部分完成", "2026-04-22 21:35", "10,984 只股票", "warning"],
] as const;

const dataSources = [{ name: "沧海数据", status: "正常", calls: "今日调用次数由上游接口统计" }];

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
  { title: "操作", render: () => <Button type="link" size="small">查看</Button> },
];

const priceColumns: ColumnsType<PriceRow> = [
  { title: "股票代码", dataIndex: "code", fixed: "left", width: 110 },
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

export default function DataCenterPage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [modalOpen, setModalOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [logLoading, setLogLoading] = useState(true);
  const [exchangeOptions, setExchangeOptions] = useState<ExchangeOption[]>([]);
  const [countryOptions, setCountryOptions] = useState<CountryOption[]>([]);
  const [exchangeLoading, setExchangeLoading] = useState(false);
  const [countryLoading, setCountryLoading] = useState(false);
  const [eventLogs, setEventLogs] = useState<LogRow[]>([]);
  const [form] = Form.useForm<{ syncItem: string; exchangeCode?: string; countryCode?: string }>();

  const loadLogs = useCallback(async () => {
    setLogLoading(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ items: EventLogItem[] }>("/data-center/event-logs", token);
      setEventLogs(response.items.map(mapEventLogRow));
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载同步日志失败");
    } finally {
      setLogLoading(false);
    }
  }, [messageApi]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  useEffect(() => {
    const loadExchangeOptions = async () => {
      setExchangeLoading(true);
      try {
        const token = getAccessToken();
        const response = await apiGet<{ items: ExchangeOption[] }>("/data-center/exchange-options", token);
        setExchangeOptions(response.items);
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载交易所选项失败");
      } finally {
        setExchangeLoading(false);
      }
    };

    void loadExchangeOptions();
  }, [messageApi]);

  useEffect(() => {
    const loadCountryOptions = async () => {
      setCountryLoading(true);
      try {
        const token = getAccessToken();
        const response = await apiGet<{ items: CountryOption[] }>("/data-center/country-options", token);
        setCountryOptions(response.items);
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载国家/地区选项失败");
      } finally {
        setCountryLoading(false);
      }
    };

    void loadCountryOptions();
  }, [messageApi]);

  const logColumns: ColumnsType<LogRow> = useMemo(
    () => [
      { title: "时间", dataIndex: "time", width: 180 },
      { title: "任务名称", dataIndex: "task", width: 180 },
      { title: "同步项", dataIndex: "dataset", width: 140 },
      { title: "触发方式", dataIndex: "trigger", width: 100 },
      { title: "耗时", dataIndex: "cost", width: 110 },
      {
        title: "状态",
        dataIndex: "status",
        width: 100,
        render: (value: LogRow["status"]) => (
          <Tag color={value === "成功" ? "green" : value === "运行中" ? "blue" : "red"}>{value}</Tag>
        ),
      },
      {
        title: "说明",
        dataIndex: "message",
        ellipsis: true,
      },
    ],
    [],
  );

  const handleSync = async () => {
    const values = await form.validateFields();
    setSyncing(true);
    try {
      const token = getAccessToken();
      const response = await apiPost<{
        message: string;
        result: { syncItemLabel: string; recordsAffected: number };
      }>(
        "/data-center/sync",
        {
          syncItem: values.syncItem,
          exchangeCode: values.exchangeCode,
          countryCode: values.countryCode,
        },
        token,
      );
      messageApi.success(
        `${response.message}，共处理 ${response.result.recordsAffected} 条记录`,
      );
      setModalOpen(false);
      form.resetFields();
      await loadLogs();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "同步失败");
      await loadLogs();
    } finally {
      setSyncing(false);
    }
  };

  return (
    <AppShell>
      {contextHolder}
      <section className="dashboard-heading">
        <div>
          <Title level={1}>数据中心</Title>
          <Text className="page-description">
            管理 A 股、港股、美股等多市场行情、基础信息与财务因子数据，监控同步状态、交易日历一致性和数据质量。
          </Text>
        </div>
        <Space>
          <Button type="primary" icon={<SyncOutlined />} onClick={() => setModalOpen(true)}>
            同步数据
          </Button>
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
                {item.value}
                {item.suffix ?? ""}
              </strong>
              <Text className="metric-hint">
                {item.description}，{item.status}
              </Text>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[20, 20]} className="dashboard-main-row equal-height-row">
        <Col xs={24} xl={15}>
          <Card
            className="dashboard-card data-sync-panel"
            title="数据同步概览"
            extra={<Button type="link" onClick={() => void loadLogs()}>刷新日志</Button>}
          >
            <div className="sync-timeline">
              {logLoading ? (
                <div className="sync-task">
                  <Badge status="processing" />
                  <div>
                    <strong>正在加载日志</strong>
                    <Text>请稍候...</Text>
                  </div>
                </div>
              ) : eventLogs.length > 0 ? (
                eventLogs.map((log) => (
                  <div className="sync-task" key={log.key}>
                    <Badge status={log.status === "成功" ? "success" : log.status === "运行中" ? "processing" : "error"} />
                    <div>
                      <strong>{log.task}</strong>
                      <Text>
                        {log.time} · {log.dataset} · {log.message}
                      </Text>
                    </div>
                  </div>
                ))
              ) : (
                <div className="sync-task">
                  <Badge status="default" />
                  <div>
                    <strong>暂无同步日志</strong>
                    <Text>完成首次同步后，这里会显示最新执行记录。</Text>
                  </div>
                </div>
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={9}>
          <Card className="dashboard-card" title="数据源状态">
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
                  <Progress percent={percent} showInfo={false} status={percent < 96 ? "exception" : "success"} />
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
          <Select
            defaultValue="all"
            options={[
              { label: "全部市场", value: "all" },
              { label: "A 股", value: "cn" },
              { label: "港股", value: "hk" },
              { label: "美股", value: "us" },
            ]}
          />
          <Select
            defaultValue="daily"
            options={[
              { label: "日线行情", value: "daily" },
              { label: "基础信息", value: "basic" },
              { label: "财务因子", value: "financial" },
              { label: "复权因子", value: "adjust" },
            ]}
          />
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

      <Modal
        title="同步数据"
        open={modalOpen}
        okText="开始同步"
        cancelText="取消"
        confirmLoading={syncing}
        onOk={() => void handleSync()}
        onCancel={() => {
          if (!syncing) {
            setModalOpen(false);
          }
        }}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ syncItem: "country_list" }}
        >
          <Form.Item
            label="同步项"
            name="syncItem"
            rules={[{ required: true, message: "请选择同步项" }]}
          >
            <Select
              options={syncItemOptions}
              onChange={(value) => {
                if (value !== "stock_list") {
                  form.setFieldValue("exchangeCode", undefined);
                }
                if (value !== "index_list") {
                  form.setFieldValue("countryCode", undefined);
                }
              }}
            />
          </Form.Item>
          <Form.Item
            noStyle
            shouldUpdate={(prev, next) => prev.syncItem !== next.syncItem}
          >
            {({ getFieldValue }) =>
              getFieldValue("syncItem") === "stock_list" ? (
                <Form.Item
                  label="交易所"
                  name="exchangeCode"
                  rules={[{ required: true, message: "请选择交易所" }]}
                >
                  <Select
                    showSearch
                    loading={exchangeLoading}
                    options={exchangeOptions}
                    placeholder="请选择交易所"
                    optionFilterProp="label"
                  />
                </Form.Item>
              ) : null
            }
          </Form.Item>
          <Form.Item
            noStyle
            shouldUpdate={(prev, next) => prev.syncItem !== next.syncItem}
          >
            {({ getFieldValue }) =>
              getFieldValue("syncItem") === "index_list" ? (
                <Form.Item
                  label="国家/地区"
                  name="countryCode"
                  rules={[{ required: true, message: "请选择国家/地区" }]}
                >
                  <Select
                    showSearch
                    loading={countryLoading}
                    options={countryOptions}
                    placeholder="请选择国家/地区"
                    optionFilterProp="label"
                  />
                </Form.Item>
              ) : null
            }
          </Form.Item>
        </Form>
      </Modal>
    </AppShell>
  );
}

function mapEventLogRow(item: EventLogItem): LogRow {
  return {
    key: String(item.id),
    time: formatDisplayTime(item.time),
    task:
      item.eventName === "sync_country_list"
        ? "国家/地区同步"
        : item.eventName === "sync_exchange_list"
          ? "交易所同步"
          : item.eventName === "sync_stock_list"
            ? "股票清单同步"
            : item.eventName === "sync_index_list"
              ? "指数清单同步"
          : item.eventName,
    dataset:
      item.target === "country_list"
        ? "国家/地区清单"
        : item.target === "exchange_list"
          ? "交易所清单"
          : item.target === "stock_list"
            ? "股票清单"
            : item.target === "index_list"
              ? "指数清单"
          : item.target || "-",
    trigger: "手动",
    cost: item.durationMs ? `${item.durationMs} ms` : "-",
    status: item.status === "success" ? "成功" : item.status === "running" ? "运行中" : "失败",
    message: item.message,
  };
}

function formatDisplayTime(value: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }

  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}
