"use client";

import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, Card, Input, Modal, message, Select, Space, Table, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
import type { SorterResult } from "antd/es/table/interface";
import type { ChangeEvent } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { apiGet, apiPost } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

const { Text, Title } = Typography;

type EvaluationStatus = "not_evaluated" | "evaluating" | "queued" | "running" | "success" | "failure";

type StrategyEvaluation = {
  id: number;
  status: EvaluationStatus;
  score: number | null;
  conclusion: string | null;
  generalityConclusion: string | null;
  stabilityConclusion: string | null;
  riskConclusion: string | null;
  summary: string | null;
  errorMessage: string | null;
  updatedAt: string | null;
};

type LabStrategyRow = {
  id: number;
  name: string;
  type: string;
  source: string;
  status: string;
  countryRegion: string;
  assetName: string | null;
  assetIdentifier: string | null;
  assetType: "stock" | "index" | null;
  updatedAt: string | null;
  evaluationStatus: EvaluationStatus;
  evaluationStatusLabel: string;
  evaluation: StrategyEvaluation | null;
};

type LabStrategiesResponse = {
  items: LabStrategyRow[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
  };
  filters: {
    sources: string[];
    evaluationStatuses: EvaluationStatus[];
  };
};

type EvaluationCandidate = {
  label: string;
  value: string;
  name?: string | null;
  assetIdentifier?: string | null;
  latestDate?: string | null;
};

type EvaluationCandidateResponse = {
  countryCode: string;
  assetType: "stock" | "index";
  items: EvaluationCandidate[];
};

type QueryState = {
  page: number;
  pageSize: number;
  keyword: string;
  source?: string;
  evaluationStatus?: EvaluationStatus;
  sortBy?: "score";
  sortOrder?: "asc" | "desc";
};

const defaultQueryState: QueryState = {
  page: 1,
  pageSize: 10,
  keyword: "",
};

const evaluationStatusMeta: Record<EvaluationStatus, { label: string; color: string }> = {
  not_evaluated: { label: "未评估", color: "default" },
  evaluating: { label: "评估中", color: "processing" },
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

export default function BacktestLabPage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [loading, setLoading] = useState(true);
  const [evaluatingId, setEvaluatingId] = useState<number | null>(null);
  const [items, setItems] = useState<LabStrategyRow[]>([]);
  const [sources, setSources] = useState<string[]>([]);
  const [statuses, setStatuses] = useState<EvaluationStatus[]>([]);
  const [pagination, setPagination] = useState<LabStrategiesResponse["pagination"]>({
    page: 1,
    pageSize: 10,
    total: 0,
  });
  const [queryState, setQueryState] = useState<QueryState>(defaultQueryState);
  const [draftKeyword, setDraftKeyword] = useState("");
  const [draftSource, setDraftSource] = useState<string | undefined>();
  const [draftEvaluationStatus, setDraftEvaluationStatus] = useState<EvaluationStatus | undefined>();
  const [evaluateModalOpen, setEvaluateModalOpen] = useState(false);
  const [evaluateTarget, setEvaluateTarget] = useState<LabStrategyRow | null>(null);
  const [candidateOptions, setCandidateOptions] = useState<EvaluationCandidate[]>([]);
  const [candidateCountryCode, setCandidateCountryCode] = useState("");
  const [selectedCandidateValues, setSelectedCandidateValues] = useState<string[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [aiSelecting, setAiSelecting] = useState(false);

  const loadStrategies = useCallback(async (nextState: QueryState) => {
    setLoading(true);
    try {
      const token = getAccessToken();
      const params = new URLSearchParams({
        page: String(nextState.page),
        pageSize: String(nextState.pageSize),
      });
      if (nextState.keyword) params.set("keyword", nextState.keyword);
      if (nextState.source) params.set("source", nextState.source);
      if (nextState.evaluationStatus) params.set("evaluationStatus", nextState.evaluationStatus);
      if (nextState.sortBy) params.set("sortBy", nextState.sortBy);
      if (nextState.sortOrder) params.set("sortOrder", nextState.sortOrder);
      const response = await apiGet<LabStrategiesResponse>(`/backtest-lab/strategies?${params.toString()}`, token);
      setItems(response.items);
      setSources(response.filters.sources);
      setStatuses(response.filters.evaluationStatuses);
      setPagination(response.pagination);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载回测实验室失败。");
    } finally {
      setLoading(false);
    }
  }, [messageApi]);

  useEffect(() => {
    void loadStrategies(queryState);
  }, [loadStrategies, queryState]);

  const applyFilters = () => {
    setQueryState({
      page: 1,
      pageSize: queryState.pageSize,
      keyword: draftKeyword.trim(),
      source: draftSource,
      evaluationStatus: draftEvaluationStatus,
      sortBy: queryState.sortBy,
      sortOrder: queryState.sortOrder,
    });
  };

  const resetFilters = () => {
    setDraftKeyword("");
    setDraftSource(undefined);
    setDraftEvaluationStatus(undefined);
    setQueryState(defaultQueryState);
  };

  const openEvaluateModal = useCallback(async (record: LabStrategyRow) => {
    setEvaluateTarget(record);
    setEvaluateModalOpen(true);
    setSelectedCandidateValues([]);
    setCandidateOptions([]);
    setCandidateCountryCode(record.countryRegion || "");
    setLoadingCandidates(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<EvaluationCandidateResponse>(
        `/backtest-lab/strategies/${record.id}/candidate-assets`,
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
  }, [messageApi]);

  const handleAiSelectCandidates = useCallback(async () => {
    if (!evaluateTarget) return;
    setAiSelecting(true);
    try {
      const token = getAccessToken();
      const response = await apiPost<{ items: EvaluationCandidate[]; selection?: { message?: string } }>(
        `/backtest-lab/strategies/${evaluateTarget.id}/candidate-assets/ai`,
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
  }, [evaluateTarget, messageApi]);

  const handleEvaluate = useCallback(async () => {
    if (!evaluateTarget) return;
    setEvaluatingId(evaluateTarget.id);
    try {
      const token = getAccessToken();
      await apiPost(
        `/backtest-lab/strategies/${evaluateTarget.id}/evaluate`,
        { assetIdentifiers: selectedCandidateValues },
        token,
      );
      messageApi.success("策略重新评估任务已提交，可在任务中心查看进度。");
      setEvaluateModalOpen(false);
      setEvaluateTarget(null);
      setCandidateOptions([]);
      setCandidateCountryCode("");
      setSelectedCandidateValues([]);
      await loadStrategies(queryState);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "提交策略重新评估失败。");
    } finally {
      setEvaluatingId(null);
    }
  }, [evaluateTarget, loadStrategies, messageApi, queryState, selectedCandidateValues]);

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

  const columns = useMemo<ColumnsType<LabStrategyRow>>(
    () => [
      {
        title: "策略名称",
        dataIndex: "name",
        width: 260,
        render: (value: string) => (
          <Tooltip title={value}>
            <strong className="single-line-text">{value}</strong>
          </Tooltip>
        ),
      },
      {
        title: "来源",
        dataIndex: "source",
        width: 110,
        render: (value: string) => <Tag color={value === "AI 生成" ? "purple" : "blue"}>{value}</Tag>,
      },
      {
        title: "类型",
        dataIndex: "type",
        width: 120,
        render: (value: string) => <Tag>{value}</Tag>,
      },
      {
        title: "原始标的",
        key: "asset",
        width: 220,
        render: (_, record) => (
          <div className="backtest-lab-asset">
            <span>{record.assetName || "-"}</span>
            <Text type="secondary">{record.assetIdentifier || "-"}</Text>
          </div>
        ),
      },
      {
        title: "评估状态",
        dataIndex: "evaluationStatus",
        width: 120,
        render: (value: EvaluationStatus) => {
          const meta = evaluationStatusMeta[value] || evaluationStatusMeta.not_evaluated;
          return <Tag color={meta.color}>{meta.label}</Tag>;
        },
      },
      {
        title: "综合评分",
        key: "score",
        width: 120,
        sorter: true,
        sortOrder:
          queryState.sortBy === "score"
            ? queryState.sortOrder === "asc"
              ? "ascend"
              : "descend"
            : null,
        render: (_, record) =>
          record.evaluation?.score !== null && record.evaluation?.score !== undefined ? (
            <Text className="positive-text">{record.evaluation.score.toFixed(2)}</Text>
          ) : (
            <Text type="secondary">-</Text>
          ),
      },
      {
        title: "通用性结论",
        key: "generality",
        width: 150,
        render: (_, record) => record.evaluation?.generalityConclusion || "-",
      },
      {
        title: "稳定性结论",
        key: "stability",
        width: 150,
        render: (_, record) => record.evaluation?.stabilityConclusion || "-",
      },
      {
        title: "风险结论",
        key: "risk",
        width: 150,
        render: (_, record) => record.evaluation?.riskConclusion || "-",
      },
      {
        title: "评估结论",
        key: "conclusion",
        width: 130,
        render: (_, record) =>
          record.evaluation?.conclusion ? (
            <Tag color={conclusionColor[record.evaluation.conclusion] || "default"}>{record.evaluation.conclusion}</Tag>
          ) : (
            "-"
          ),
      },
      {
        title: "最近评估时间",
        key: "evaluatedAt",
        width: 180,
        render: (_, record) => formatDateTime(record.evaluation?.updatedAt || null),
      },
      {
        title: "操作",
        key: "actions",
        width: 220,
        fixed: "right",
        render: (_, record) => (
          <Space size={12} className="table-action-links">
            <Button
              type="link"
              disabled={record.evaluationStatus === "queued" || record.evaluationStatus === "running"}
              loading={evaluatingId === record.id}
              onClick={() => void openEvaluateModal(record)}
            >
              重新评估
            </Button>
            <Link href={`/backtest-lab/${record.id}`}>查看详情</Link>
            <Link href={`/strategy-builder/${record.id}`}>查看策略</Link>
          </Space>
        ),
      },
    ],
    [evaluatingId, openEvaluateModal, queryState.sortBy, queryState.sortOrder],
  );

  const handleTableChange = (
    nextPagination: TablePaginationConfig,
    _filters: Record<string, unknown>,
    sorter: SorterResult<LabStrategyRow> | SorterResult<LabStrategyRow>[],
  ) => {
    const activeSorter = Array.isArray(sorter) ? sorter[0] : sorter;
    const nextSortOrder = activeSorter?.order === "ascend" ? "asc" : activeSorter?.order === "descend" ? "desc" : undefined;
    setQueryState((current) => ({
      ...current,
      page: nextPagination.current || current.page,
      pageSize: nextPagination.pageSize || current.pageSize,
      sortBy: nextSortOrder ? "score" : undefined,
      sortOrder: nextSortOrder,
    }));
  };

  return (
    <AppShell>
      {contextHolder}
      <section className="dashboard-heading">
        <div>
          <Title level={1}>回测实验室</Title>
          <Text className="page-description">对已生成策略进行跨标的、跨时间区间与交易健康度的综合评估。</Text>
        </div>
      </section>

      <Card className="dashboard-card strategy-page-card" bordered>
        <div className="strategy-filter-bar">
          <Input
            allowClear
            className="strategy-filter-keyword"
            placeholder="搜索策略名称、类型或来源"
            prefix={<SearchOutlined />}
            value={draftKeyword}
            onChange={(event: ChangeEvent<HTMLInputElement>) => setDraftKeyword(event.target.value)}
          />
          <Select
            allowClear
            className="strategy-filter-select"
            options={sources.map((value) => ({ label: value, value }))}
            placeholder="来源"
            value={draftSource}
            onChange={setDraftSource}
          />
          <Select
            allowClear
            className="strategy-filter-select"
            options={statuses.map((value) => ({ label: evaluationStatusMeta[value]?.label || value, value }))}
            placeholder="评估状态"
            value={draftEvaluationStatus}
            onChange={setDraftEvaluationStatus}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={applyFilters}>
            查询
          </Button>
          <Button icon={<ReloadOutlined />} onClick={resetFilters}>
            重置
          </Button>
        </div>

        <Table<LabStrategyRow>
          rowKey="id"
          columns={columns}
          dataSource={items}
          loading={loading}
          locale={{
            emptyText: <EmptyState title="暂无可评估策略" description="请先在策略搭建页创建策略。" compact />,
          }}
          pagination={tablePagination}
          onChange={handleTableChange}
          scroll={{ x: 1820 }}
        />
      </Card>
      <Modal
        title="重新评估策略"
        open={evaluateModalOpen}
        okText="开始重新评估"
        cancelText="取消"
        width={720}
        confirmLoading={evaluatingId === evaluateTarget?.id}
        okButtonProps={{ disabled: selectedCandidateValues.length === 0 }}
        onCancel={() => {
          setEvaluateModalOpen(false);
          setEvaluateTarget(null);
          setCandidateOptions([]);
          setCandidateCountryCode("");
          setSelectedCandidateValues([]);
        }}
        onOk={() => void handleEvaluate()}
      >
        <div className="evaluation-target-panel">
          <div>
            <Text type="secondary">国家/地区</Text>
            <strong>{candidateCountryCode || evaluateTarget?.countryRegion || "-"}</strong>
          </div>
          <div>
            <Text type="secondary">标的类型</Text>
            <strong>{evaluateTarget?.assetType === "stock" ? "股票" : "指数"}</strong>
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
        <Text type="secondary">
          这里只能选择同国家/地区、同类型且已经同步过历史日线数据的标的。
        </Text>
      </Modal>
    </AppShell>
  );
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
