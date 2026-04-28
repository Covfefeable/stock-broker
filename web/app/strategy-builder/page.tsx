"use client";

import { PlusOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, Card, Input, Modal, message, Select, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType, TablePaginationConfig, TableProps } from "antd/es/table";
import type { ChangeEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { getAccessToken } from "@/lib/auth";
import { apiDelete, apiGet, apiPost } from "@/lib/api";

const { Text, Title } = Typography;

type StrategyRow = {
  id: number;
  name: string;
  type: string;
  source: string;
  status: string;
  countryRegion: string;
  annualReturn: string | null;
  drawdown: string | null;
  updatedAt: string | null;
};

type StrategyListResponse = {
  items: StrategyRow[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
  };
  filters: {
    countryRegions: string[];
    types: string[];
    sources: string[];
    statuses: string[];
  };
};

type QueryState = {
  page: number;
  pageSize: number;
  keyword: string;
  countryRegion?: string;
  type?: string;
  source?: string;
  status?: string;
  sortField?: string;
  sortOrder?: "ascend" | "descend";
};

type StrategyFilters = StrategyListResponse["filters"];

const defaultFilters: StrategyFilters = {
  countryRegions: [],
  types: [],
  sources: [],
  statuses: [],
};

const statusColorMap: Record<string, string> = {
  已发布: "green",
  草稿: "gold",
  已归档: "default",
  测试中: "processing",
};

const defaultQueryState: QueryState = {
  page: 1,
  pageSize: 10,
  keyword: "",
  countryRegion: undefined,
  type: undefined,
  source: undefined,
  status: undefined,
  sortField: undefined,
  sortOrder: undefined,
};

export default function StrategyBuilderPage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [modal, modalHolder] = Modal.useModal();
  const [loading, setLoading] = useState(true);
  const [archivingId, setArchivingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [items, setItems] = useState<StrategyRow[]>([]);
  const [filters, setFilters] = useState<StrategyFilters>(defaultFilters);
  const [pagination, setPagination] = useState<StrategyListResponse["pagination"]>({
    page: 1,
    pageSize: 10,
    total: 0,
  });
  const [draftKeyword, setDraftKeyword] = useState("");
  const [draftCountryRegion, setDraftCountryRegion] = useState<string | undefined>();
  const [draftType, setDraftType] = useState<string | undefined>();
  const [draftSource, setDraftSource] = useState<string | undefined>();
  const [draftStatus, setDraftStatus] = useState<string | undefined>();
  const [queryState, setQueryState] = useState<QueryState>(defaultQueryState);

  const loadStrategies = useCallback(async (nextState: QueryState) => {
    setLoading(true);
    try {
      const token = getAccessToken();
      const params = new URLSearchParams({
        page: String(nextState.page),
        pageSize: String(nextState.pageSize),
      });
      if (nextState.keyword) {
        params.set("keyword", nextState.keyword);
      }
      if (nextState.countryRegion) {
        params.set("countryRegion", nextState.countryRegion);
      }
      if (nextState.type) {
        params.set("type", nextState.type);
      }
      if (nextState.source) {
        params.set("source", nextState.source);
      }
      if (nextState.status) {
        params.set("status", nextState.status);
      }
      if (nextState.sortField) {
        params.set("sortField", nextState.sortField);
      }
      if (nextState.sortOrder) {
        params.set("sortOrder", nextState.sortOrder);
      }

      const response = await apiGet<StrategyListResponse>(`/strategies?${params.toString()}`, token);
      setItems(response.items);
      setFilters(response.filters);
      setPagination(response.pagination);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载策略列表失败");
    } finally {
      setLoading(false);
    }
  }, [messageApi]);

  useEffect(() => {
    void loadStrategies(queryState);
  }, [loadStrategies, queryState]);

  const applyFilters = () => {
    setQueryState((current) => ({
      ...current,
      page: 1,
      keyword: draftKeyword.trim(),
      countryRegion: draftCountryRegion,
      type: draftType,
      source: draftSource,
      status: draftStatus,
    }));
  };

  const resetFilters = () => {
    setDraftKeyword("");
    setDraftCountryRegion(undefined);
    setDraftType(undefined);
    setDraftSource(undefined);
    setDraftStatus(undefined);
    setQueryState(defaultQueryState);
  };

  const handleArchive = async (strategyId: number) => {
    setArchivingId(strategyId);
    try {
      const token = getAccessToken();
      await apiPost<{ message: string }>(`/strategies/${strategyId}/archive`, {}, token);
      messageApi.success("策略已归档。");
      await loadStrategies(queryState);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "归档策略失败");
    } finally {
      setArchivingId(null);
    }
  };

  const handleDelete = (strategyId: number) => {
    modal.confirm({
      title: "确认删除策略？",
      content: "删除后不可恢复，策略配置和规则引擎内容都会一起移除。",
      okText: "删除",
      cancelText: "取消",
      okButtonProps: { danger: true },
      onOk: async () => {
        setDeletingId(strategyId);
        try {
          const token = getAccessToken();
          await apiDelete(`/strategies/${strategyId}`, token);
          messageApi.success("策略已删除。");
          await loadStrategies(queryState);
        } catch (error) {
          messageApi.error(error instanceof Error ? error.message : "删除策略失败");
        } finally {
          setDeletingId(null);
        }
      },
    });
  };

  const handleTableChange: TableProps<StrategyRow>["onChange"] = (
    nextPagination,
    _tableFilters,
    sorter,
  ) => {
    const sorterValue = Array.isArray(sorter) ? sorter[0] : sorter;
    setQueryState((current) => ({
      ...current,
      page: nextPagination.current ?? 1,
      pageSize: nextPagination.pageSize ?? current.pageSize,
      sortField:
        sorterValue?.columnKey === "annualReturnValue" || sorterValue?.field === "annualReturn"
          ? "annualReturn"
          : undefined,
      sortOrder:
        (sorterValue?.columnKey === "annualReturnValue" || sorterValue?.field === "annualReturn") && sorterValue.order
          ? (sorterValue.order as "ascend" | "descend")
          : undefined,
    }));
  };

  const tablePagination = useMemo<TablePaginationConfig>(
    () => ({
      current: pagination.page,
      pageSize: pagination.pageSize,
      total: pagination.total,
      showSizeChanger: false,
      showTotal: (total: number, range: [number, number]) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
    }),
    [pagination],
  );

  const columns = useMemo<ColumnsType<StrategyRow>>(
    () => [
      {
        title: "策略名称",
        dataIndex: "name",
        render: (value: string) => <strong>{value}</strong>,
      },
      {
        title: "类型",
        dataIndex: "type",
        width: 120,
        render: (value: string) => <Tag>{value}</Tag>,
      },
      {
        title: "来源",
        dataIndex: "source",
        width: 110,
        render: (value: string) => <Tag color={value === "AI 生成" ? "purple" : "blue"}>{value}</Tag>,
      },
      {
        title: "状态",
        dataIndex: "status",
        width: 110,
        render: (value: string) => <Tag color={statusColorMap[value] ?? "default"}>{value}</Tag>,
      },
      {
        title: "国家/地区",
        dataIndex: "countryRegion",
        width: 120,
      },
      {
        title: "年化收益",
        dataIndex: "annualReturn",
        width: 120,
        sorter: true,
        sortOrder: queryState.sortField === "annualReturn" ? queryState.sortOrder : null,
        key: "annualReturnValue",
        render: (value: string | null) =>
          value ? <Text className="positive-text">{value}</Text> : <Text type="secondary">-</Text>,
      },
      {
        title: "最大回撤",
        dataIndex: "drawdown",
        width: 110,
        render: (value: string | null) =>
          value ? <Text className="negative-text">{value}</Text> : <Text type="secondary">-</Text>,
      },
      {
        title: "最近更新",
        dataIndex: "updatedAt",
        width: 180,
        render: (value: string | null) =>
          value
            ? new Intl.DateTimeFormat("zh-CN", {
                year: "numeric",
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                hour12: false,
                timeZone: "Asia/Shanghai",
              }).format(new Date(value))
            : "-",
      },
      {
        title: "操作",
        key: "action",
        width: 280,
        fixed: "right",
        render: (_value: unknown, record: StrategyRow) => (
          <Space size={4}>
            <Button size="small" type="link" href={`/strategy-builder/${record.id}`}>
              查看
            </Button>
            <Button size="small" type="link" href={`/backtest-lab/${record.id}`}>
              查看回测
            </Button>
            <Button
              size="small"
              type="link"
              disabled={record.status === "已归档"}
              loading={archivingId === record.id}
              onClick={() => void handleArchive(record.id)}
            >
              归档
            </Button>
            <Button
              size="small"
              type="link"
              danger
              loading={deletingId === record.id}
              onClick={() => handleDelete(record.id)}
            >
              删除
            </Button>
          </Space>
        ),
      },
    ],
    [archivingId, deletingId, handleArchive, handleDelete, queryState.sortField, queryState.sortOrder],
  );

  return (
    <AppShell>
      {contextHolder}
      {modalHolder}
      <section className="dashboard-heading">
        <div>
          <Title level={1}>策略搭建</Title>
          <Text className="page-description">按筛选条件查看策略清单，进入详情继续编辑或新建策略。</Text>
        </div>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} href="/strategy-builder/new">
            新建策略
          </Button>
        </Space>
      </section>

      <Card className="dashboard-card strategy-page-card" bordered>
        <div className="strategy-filter-bar">
          <Input
            allowClear
            className="strategy-filter-keyword"
            placeholder="搜索策略名称、类型或国家/地区"
            prefix={<SearchOutlined />}
            value={draftKeyword}
            onChange={(event: ChangeEvent<HTMLInputElement>) => setDraftKeyword(event.target.value)}
          />
          <Select
            allowClear
            className="strategy-filter-select"
            options={filters.countryRegions.map((value) => ({ label: value, value }))}
            placeholder="国家/地区"
            value={draftCountryRegion}
            onChange={setDraftCountryRegion}
          />
          <Select
            allowClear
            className="strategy-filter-select"
            options={filters.types.map((value) => ({ label: value, value }))}
            placeholder="类型"
            value={draftType}
            onChange={setDraftType}
          />
          <Select
            allowClear
            className="strategy-filter-select"
            options={filters.sources.map((value) => ({ label: value, value }))}
            placeholder="来源"
            value={draftSource}
            onChange={setDraftSource}
          />
          <Select
            allowClear
            className="strategy-filter-select"
            options={filters.statuses.map((value) => ({ label: value, value }))}
            placeholder="状态"
            value={draftStatus}
            onChange={setDraftStatus}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={applyFilters}>
            查询
          </Button>
          <Button icon={<ReloadOutlined />} onClick={resetFilters}>
            重置
          </Button>
        </div>

        <div className="strategy-list-summary">
          <Text className="page-description">共 {pagination.total} 条策略记录</Text>
        </div>

        <Table
          rowKey="id"
          columns={columns}
          dataSource={items}
          loading={loading}
          locale={{
            emptyText: <EmptyState title="暂无策略" description="请先新建策略。" compact />,
          }}
          pagination={tablePagination}
          onChange={handleTableChange}
          scroll={{ x: 1340 }}
        />
      </Card>
    </AppShell>
  );
}
