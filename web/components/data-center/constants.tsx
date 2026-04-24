import type { ColumnsType } from "antd/es/table";
import { Button, Tag, Typography } from "antd";
import type { IssueRow, PriceRow, SyncFormValues } from "@/components/data-center/types";

const { Text } = Typography;

export const issueColumns: ColumnsType<IssueRow> = [
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

export const priceColumns: ColumnsType<PriceRow> = [
  { title: "股票代码", dataIndex: "code", fixed: "left", width: 110 },
  { title: "股票名称", dataIndex: "name", fixed: "left", width: 120 },
  { title: "日期", dataIndex: "date", width: 120 },
  { title: "开盘价", dataIndex: "open" },
  { title: "最高价", dataIndex: "high" },
  { title: "最低价", dataIndex: "low" },
  { title: "收盘价", dataIndex: "close" },
  { title: "成交量", dataIndex: "volume" },
  { title: "成交额", dataIndex: "amount" },
  {
    title: "涨跌幅",
    dataIndex: "change",
    render: (value: string) => <Text className="positive-text">{value}</Text>,
  },
  {
    title: "数据状态",
    dataIndex: "status",
    render: (value: string) => <Tag color="green">{value}</Tag>,
  },
  {
    title: "操作",
    fixed: "right",
    width: 100,
    render: () => <Button type="link" size="small">详情</Button>,
  },
];

export const issues: IssueRow[] = [
  { key: "1", issueType: "缺失交易日", dataset: "港股日线行情", affected: "8 只股票", severity: "轻微", status: "待修复" },
  { key: "2", issueType: "财务字段为空", dataset: "美股财务因子", affected: "232 只股票", severity: "中等", status: "处理中" },
  { key: "3", issueType: "成交量异常", dataset: "A 股日线行情", affected: "3 只股票", severity: "轻微", status: "已标记" },
  { key: "4", issueType: "非交易日多余记录", dataset: "美股日线行情", affected: "1 只股票", severity: "严重", status: "待修复" },
];

export const prices: PriceRow[] = [
  { key: "1", code: "600519.SH", name: "贵州茅台", date: "2026-04-22", open: "1580.20", high: "1602.80", low: "1575.00", close: "1598.50", volume: "32,450", amount: "51.8 亿 CNY", change: "+1.24%", status: "正常" },
  { key: "2", code: "0700.HK", name: "腾讯控股", date: "2026-04-22", open: "392.20", high: "398.40", low: "389.80", close: "396.60", volume: "18,420", amount: "72.9 亿 HKD", change: "+1.88%", status: "正常" },
  { key: "3", code: "AAPL", name: "Apple", date: "2026-04-22", open: "188.40", high: "191.10", low: "187.30", close: "190.82", volume: "48,620,400", amount: "92.8 亿 USD", change: "+1.16%", status: "正常" },
  { key: "4", code: "9988.HK", name: "阿里巴巴-W", date: "2026-04-22", open: "83.50", high: "85.20", low: "82.90", close: "84.85", volume: "298,100", amount: "25.1 亿 HKD", change: "+1.62%", status: "正常" },
  { key: "5", code: "MSFT", name: "Microsoft", date: "2026-04-22", open: "416.80", high: "421.50", low: "415.90", close: "420.70", volume: "19,630,000", amount: "82.6 亿 USD", change: "+0.98%", status: "正常" },
];

export const syncItemOptions: Array<{ label: string; value: SyncFormValues["syncItem"] }> = [
  { label: "国家/地区清单", value: "country_list" },
  { label: "交易所清单", value: "exchange_list" },
  { label: "股票清单", value: "stock_list" },
  { label: "指数清单", value: "index_list" },
  { label: "交易日历", value: "trading_calendar" },
  { label: "股票历史日线", value: "stock_daily_history" },
  { label: "指数历史日线", value: "index_daily_history" },
];
