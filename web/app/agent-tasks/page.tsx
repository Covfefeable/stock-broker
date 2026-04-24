"use client";

import { DeleteOutlined, PlusOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, Card, Input, Popconfirm, Select, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import type { AgentTaskItem, AgentTaskListResponse, AgentTaskStatus } from "@/components/agent-tasks/types";
import { getAccessToken } from "@/lib/auth";
import { apiDelete, apiGet } from "@/lib/api";

const { Title, Text } = Typography;

type QueryState = {
  page: number;
  pageSize: number;
  keyword: string;
  assetType?: "stock" | "index";
  countryCode?: string;
  status?: AgentTaskStatus;
};

const defaultQueryState: QueryState = {
  page: 1,
  pageSize: 10,
  keyword: "",
};

const statusMeta: Record<AgentTaskStatus, { label: string; color: string }> = {
  queued: { label: "排队中", color: "default" },
  running: { label: "运行中", color: "processing" },
  success: { label: "已完成", color: "success" },
  failure: { label: "失败", color: "error" },
};

export default function AgentTasksPage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState<AgentTaskItem[]>([]);
  const [countryOptions, setCountryOptions] = useState<string[]>([]);
  const [statusOptions, setStatusOptions] = useState<string[]>([]);
  const [queryState, setQueryState] = useState<QueryState>(defaultQueryState);
  const [keyword, setKeyword] = useState("");
  const [assetType, setAssetType] = useState<"stock" | "index" | undefined>();
  const [countryCode, setCountryCode] = useState<string | undefined>();
  const [status, setStatus] = useState<AgentTaskStatus | undefined>();
  const [pagination, setPagination] = useState<TablePaginationConfig>({
    current: 1,
    pageSize: 10,
    total: 0,
  });

  const loadTasks = useCallback(
    async (nextQuery: QueryState) => {
      setLoading(true);
      try {
        const token = getAccessToken();
        const params = new URLSearchParams({
          page: String(nextQuery.page),
          pageSize: String(nextQuery.pageSize),
        });
        if (nextQuery.keyword) params.set("keyword", nextQuery.keyword);
        if (nextQuery.assetType) params.set("assetType", nextQuery.assetType);
        if (nextQuery.countryCode) params.set("countryCode", nextQuery.countryCode);
        if (nextQuery.status) params.set("status", nextQuery.status);

        const response = await apiGet<AgentTaskListResponse>(`/agent-tasks?${params.toString()}`, token);
        setRows(response.items);
        setCountryOptions(response.filters.countryCodes);
        setStatusOptions(response.filters.statuses);
        setPagination({
          current: response.pagination.page,
          pageSize: response.pagination.pageSize,
          total: response.pagination.total,
        });
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载 Agent 任务失败。");
      } finally {
        setLoading(false);
      }
    },
    [messageApi],
  );

  useEffect(() => {
    void loadTasks(queryState);
  }, [loadTasks, queryState]);

  const handleSearch = () => {
    setQueryState({
      page: 1,
      pageSize: pagination.pageSize || 10,
      keyword: keyword.trim(),
      assetType,
      countryCode,
      status,
    });
  };

  const handleReset = () => {
    setKeyword("");
    setAssetType(undefined);
    setCountryCode(undefined);
    setStatus(undefined);
    setQueryState({
      page: 1,
      pageSize: pagination.pageSize || 10,
      keyword: "",
    });
  };

  const handleDelete = async (taskId: number) => {
    try {
      const token = getAccessToken();
      await apiDelete(`/agent-tasks/${taskId}`, token);
      messageApi.success("Agent 任务已删除。");
      await loadTasks(queryState);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "删除 Agent 任务失败。");
    }
  };

  const columns = useMemo<ColumnsType<AgentTaskItem>>(
    () => [
      {
        title: "任务名称",
        dataIndex: "name",
        key: "name",
        render: (value: string, record) => <Link href={`/agent-tasks/${record.id}`}>{value}</Link>,
      },
      {
        title: "标的",
        key: "asset",
        render: (_, record) => (
          <div className="agent-task-asset-cell">
            <div className="agent-task-asset-name">{record.assetName}</div>
            <Text className="agent-task-asset-code">{record.assetIdentifier}</Text>
          </div>
        ),
      },
      {
        title: "类型",
        dataIndex: "assetType",
        key: "assetType",
        width: 96,
        render: (value) => <Tag>{value === "stock" ? "股票" : "指数"}</Tag>,
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 110,
        render: (value: AgentTaskStatus) => <Tag color={statusMeta[value].color}>{statusMeta[value].label}</Tag>,
      },
      {
        title: "当前迭代",
        key: "iteration",
        width: 120,
        render: (_, record) => `${record.currentIteration} / ${record.maxIterations}`,
      },
      {
        title: "当前最佳收益",
        dataIndex: "bestAnnualReturn",
        key: "bestAnnualReturn",
        width: 130,
        render: (value: number | null) =>
          value !== null ? <Text className="positive-text">{value.toFixed(2)}%</Text> : <Text type="secondary">-</Text>,
      },
      {
        title: "目标收益率",
        dataIndex: "targetAnnualReturn",
        key: "targetAnnualReturn",
        width: 130,
        render: (value: number | null) => (value !== null ? `${value.toFixed(2)}%` : "-"),
      },
      {
        title: "最近更新时间",
        dataIndex: "updatedAt",
        key: "updatedAt",
        width: 180,
        render: (value: string | null) => formatDateTime(value),
      },
      {
        title: "操作",
        key: "actions",
        width: 220,
        render: (_, record) => (
          <Space size={4}>
            <Link href={`/agent-tasks/${record.id}`}>查看</Link>
            <Link href={`/agent-tasks/new?copyId=${record.id}`}>复制</Link>
            <Popconfirm
              title="确定删除这个 Agent 任务吗？"
              okText="删除"
              cancelText="取消"
              onConfirm={() => void handleDelete(record.id)}
            >
              <Button type="link" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [],
  );

  return (
    <AppShell>
      {contextHolder}
      <section className="dashboard-heading">
        <div>
          <Title level={1}>AI Agent 任务</Title>
          <Text className="page-description">创建自动迭代任务，让系统围绕单一股票或指数持续尝试策略并记录每一轮总结。</Text>
        </div>
        <Link href="/agent-tasks/new">
          <Button type="primary" icon={<PlusOutlined />}>
            新建任务
          </Button>
        </Link>
      </section>

      <Card className="dashboard-card strategy-page-card" bordered>
        <div className="strategy-filter-bar">
          <Input
            allowClear
            className="strategy-filter-keyword"
            placeholder="搜索任务名称或标的"
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
          <Select
            allowClear
            className="strategy-filter-select"
            placeholder="股票/指数"
            value={assetType}
            onChange={setAssetType}
            options={[
              { label: "股票", value: "stock" },
              { label: "指数", value: "index" },
            ]}
          />
          <Select
            allowClear
            className="strategy-filter-select"
            placeholder="国家/地区"
            value={countryCode}
            onChange={setCountryCode}
            options={countryOptions.map((item) => ({ label: item, value: item }))}
          />
          <Select
            allowClear
            className="strategy-filter-select"
            placeholder="状态"
            value={status}
            onChange={setStatus}
            options={statusOptions.map((item) => ({
              label: statusMeta[item as AgentTaskStatus]?.label || item,
              value: item,
            }))}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            查询
          </Button>
          <Button icon={<ReloadOutlined />} onClick={handleReset}>
            重置
          </Button>
        </div>

        <Table<AgentTaskItem>
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={loading}
          locale={{ emptyText: "暂无 Agent 任务，请先新建任务。" }}
          pagination={{
            ...pagination,
            showSizeChanger: false,
            onChange: (page, pageSize) =>
              setQueryState((current) => ({
                ...current,
                page,
                pageSize: pageSize || current.pageSize,
              })),
          }}
          scroll={{ x: 1080 }}
        />
      </Card>
    </AppShell>
  );
}

function formatDateTime(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
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
