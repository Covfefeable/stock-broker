"use client";

import { InfoCircleOutlined, PlusOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Slider,
  Space,
  Switch,
  Table,
  Tag,
  TimePicker,
  Tooltip,
  Typography,
  message,
} from "antd";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
import dayjs, { type Dayjs } from "dayjs";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import type { AgentTaskItem } from "@/components/agent-tasks/types";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

const { Text, Title } = Typography;

type FrequencyType = "monthly" | "weekly" | "daily" | "hourly";
type PlanStatus = "enabled" | "disabled" | "paused_failed";

type ScheduledPlan = {
  id: number;
  name: string;
  agentTaskId: number;
  agentTaskName?: string | null;
  frequencyType: FrequencyType;
  timezone: string;
  timeOfDay?: string | null;
  minuteOfHour?: number | null;
  monthDays: number[];
  useLastDay: boolean;
  weekdays: number[];
  saveTopN: number;
  scoreThresholdEnabled: boolean;
  scoreThreshold?: number | null;
  status: PlanStatus;
  failureCount: number;
  lastRunAt?: string | null;
  nextRunAt?: string | null;
  lastSuccessAt?: string | null;
  lastErrorMessage?: string | null;
  updatedAt?: string | null;
};

type PlanListResponse = {
  items: ScheduledPlan[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
  };
};

type AgentOptionsResponse = {
  items: AgentTaskItem[];
};

type QueryState = {
  page: number;
  pageSize: number;
  keyword: string;
  status?: PlanStatus;
  frequencyType?: FrequencyType;
};

type PlanFormValues = {
  name: string;
  agentTaskId: number;
  frequencyType: FrequencyType;
  timeOfDay?: Dayjs;
  minuteOfHour?: number;
  monthDays?: number[];
  useLastDay?: boolean;
  weekdays?: number[];
  saveTopN: number;
  scoreThresholdEnabled?: boolean;
  scoreThreshold?: number;
  status: PlanStatus;
};

const defaultQueryState: QueryState = {
  page: 1,
  pageSize: 10,
  keyword: "",
};

const statusMeta: Record<PlanStatus, { label: string; color: string }> = {
  enabled: { label: "已启用", color: "success" },
  disabled: { label: "未启用", color: "default" },
  paused_failed: { label: "连续失败暂停", color: "error" },
};

const frequencyOptions: Array<{ label: string; value: FrequencyType }> = [
  { label: "每月", value: "monthly" },
  { label: "每周", value: "weekly" },
  { label: "每日", value: "daily" },
  { label: "每小时", value: "hourly" },
];

const weekdayOptions = [
  { label: "周一", value: 1 },
  { label: "周二", value: 2 },
  { label: "周三", value: 3 },
  { label: "周四", value: 4 },
  { label: "周五", value: 5 },
  { label: "周六", value: 6 },
  { label: "周日", value: 7 },
];

export default function ScheduledPlansPage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm<PlanFormValues>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPlan, setEditingPlan] = useState<ScheduledPlan | null>(null);
  const [rows, setRows] = useState<ScheduledPlan[]>([]);
  const [agentOptions, setAgentOptions] = useState<AgentTaskItem[]>([]);
  const [queryState, setQueryState] = useState<QueryState>(defaultQueryState);
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState<PlanStatus | undefined>();
  const [frequencyType, setFrequencyType] = useState<FrequencyType | undefined>();
  const [pagination, setPagination] = useState<TablePaginationConfig>({
    current: 1,
    pageSize: 10,
    total: 0,
  });

  const watchedFrequency = Form.useWatch("frequencyType", form);
  const thresholdEnabled = Form.useWatch("scoreThresholdEnabled", form);

  const loadPlans = useCallback(
    async (nextQuery: QueryState) => {
      setLoading(true);
      try {
        const token = getAccessToken();
        const params = new URLSearchParams({
          page: String(nextQuery.page),
          pageSize: String(nextQuery.pageSize),
        });
        if (nextQuery.keyword) params.set("keyword", nextQuery.keyword);
        if (nextQuery.status) params.set("status", nextQuery.status);
        if (nextQuery.frequencyType) params.set("frequencyType", nextQuery.frequencyType);
        const response = await apiGet<PlanListResponse>(`/scheduled-plans?${params.toString()}`, token);
        setRows(response.items);
        setPagination({
          current: response.pagination.page,
          pageSize: response.pagination.pageSize,
          total: response.pagination.total,
        });
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载计划任务失败。");
      } finally {
        setLoading(false);
      }
    },
    [messageApi],
  );

  const loadAgentOptions = useCallback(async () => {
    try {
      const token = getAccessToken();
      const response = await apiGet<AgentOptionsResponse>("/scheduled-plans/agent-options", token);
      setAgentOptions(response.items);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载 Agent 任务选项失败。");
    }
  }, [messageApi]);

  useEffect(() => {
    void loadPlans(queryState);
  }, [loadPlans, queryState]);

  useEffect(() => {
    void loadAgentOptions();
  }, [loadAgentOptions]);

  const handleSearch = () => {
    setQueryState({
      page: 1,
      pageSize: pagination.pageSize || 10,
      keyword: keyword.trim(),
      status,
      frequencyType,
    });
  };

  const handleReset = () => {
    setKeyword("");
    setStatus(undefined);
    setFrequencyType(undefined);
    setQueryState({ page: 1, pageSize: pagination.pageSize || 10, keyword: "" });
  };

  const openCreateModal = () => {
    setEditingPlan(null);
    form.setFieldsValue({
      name: "",
      agentTaskId: undefined,
      frequencyType: "daily",
      timeOfDay: dayjs("12:00", "HH:mm"),
      minuteOfHour: 0,
      monthDays: [1],
      useLastDay: false,
      weekdays: [1],
      saveTopN: 1,
      scoreThresholdEnabled: false,
      scoreThreshold: undefined,
      status: "enabled",
    });
    setModalOpen(true);
  };

  const openEditModal = (plan: ScheduledPlan) => {
    setEditingPlan(plan);
    form.setFieldsValue({
      name: plan.name,
      agentTaskId: plan.agentTaskId,
      frequencyType: plan.frequencyType,
      timeOfDay: plan.timeOfDay ? dayjs(plan.timeOfDay, "HH:mm") : dayjs("12:00", "HH:mm"),
      minuteOfHour: plan.minuteOfHour ?? 0,
      monthDays: plan.monthDays || [],
      useLastDay: plan.useLastDay,
      weekdays: plan.weekdays || [],
      saveTopN: plan.saveTopN,
      scoreThresholdEnabled: plan.scoreThresholdEnabled,
      scoreThreshold: plan.scoreThreshold ?? undefined,
      status: plan.status,
    });
    setModalOpen(true);
  };

  const submitPlan = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const token = getAccessToken();
      const payload = normalizePlanPayload(values);
      if (editingPlan) {
        await apiPut(`/scheduled-plans/${editingPlan.id}`, payload, token);
        messageApi.success("计划任务已更新。");
      } else {
        await apiPost("/scheduled-plans", payload, token);
        messageApi.success("计划任务已创建。");
      }
      setModalOpen(false);
      await loadPlans(queryState);
    } catch (error) {
      if (error instanceof Error) {
        messageApi.error(error.message);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleStatusChange = async (plan: ScheduledPlan) => {
    try {
      const token = getAccessToken();
      const action = plan.status === "enabled" ? "disable" : "enable";
      await apiPost(`/scheduled-plans/${plan.id}/${action}`, {}, token);
      messageApi.success(plan.status === "enabled" ? "计划任务已停用。" : "计划任务已启用。");
      await loadPlans(queryState);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "更新计划状态失败。");
    }
  };

  const handleRunNow = async (plan: ScheduledPlan) => {
    try {
      const token = getAccessToken();
      await apiPost(`/scheduled-plans/${plan.id}/run-now`, {}, token);
      messageApi.success("计划任务已触发。");
      await loadPlans(queryState);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "触发计划任务失败。");
    }
  };

  const handleDelete = async (plan: ScheduledPlan) => {
    try {
      const token = getAccessToken();
      await apiDelete(`/scheduled-plans/${plan.id}`, token);
      messageApi.success("计划任务已删除。");
      await loadPlans(queryState);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "删除计划任务失败。");
    }
  };

  const columns = useMemo<ColumnsType<ScheduledPlan>>(
    () => [
      {
        title: "计划名称",
        dataIndex: "name",
        key: "name",
        width: 220,
        render: (value: string) => <Text className="single-line-text">{value}</Text>,
      },
      {
        title: "关联 Agent 任务",
        dataIndex: "agentTaskName",
        key: "agentTaskName",
        width: 240,
        render: (value: string | null) => <Text className="single-line-text">{value || "-"}</Text>,
      },
      {
        title: "频率",
        key: "frequency",
        width: 180,
        render: (_, record) => formatSchedule(record),
      },
      {
        title: "保存 TopN",
        dataIndex: "saveTopN",
        key: "saveTopN",
        width: 110,
      },
      {
        title: "保存阈值",
        key: "threshold",
        width: 130,
        render: (_, record) => record.scoreThresholdEnabled ? `≥ ${record.scoreThreshold}` : "未启用",
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 150,
        render: (value: PlanStatus, record) => (
          <Tooltip title={record.lastErrorMessage || undefined}>
            <Tag color={statusMeta[value].color}>{statusMeta[value].label}</Tag>
          </Tooltip>
        ),
      },
      {
        title: "上次运行",
        dataIndex: "lastRunAt",
        key: "lastRunAt",
        width: 180,
        render: formatDateTime,
      },
      {
        title: "下次运行",
        dataIndex: "nextRunAt",
        key: "nextRunAt",
        width: 180,
        render: formatDateTime,
      },
      {
        title: "连续失败",
        dataIndex: "failureCount",
        key: "failureCount",
        width: 110,
      },
      {
        title: "操作",
        key: "actions",
        fixed: "right",
        width: 260,
        render: (_, record) => (
          <Space size={10} className="table-action-links">
            <Button type="link" onClick={() => openEditModal(record)}>
              编辑
            </Button>
            <Button type="link" onClick={() => void handleRunNow(record)}>
              立即运行
            </Button>
            <Button type="link" onClick={() => void handleStatusChange(record)}>
              {record.status === "enabled" ? "停用" : "启用"}
            </Button>
            <Popconfirm
              title="确认删除这个计划任务？"
              okText="删除"
              cancelText="取消"
              onConfirm={() => void handleDelete(record)}
            >
              <Button type="link" danger>
                删除
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [queryState],
  );

  return (
    <AppShell>
      {contextHolder}
      <section className="dashboard-heading">
        <div>
          <Title level={1}>计划任务</Title>
          <Text className="page-description">按固定频率触发 Agent 研究任务，并在完成后保存表现最佳的策略。</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
          新建计划
        </Button>
      </section>

      <Card className="dashboard-card strategy-page-card" bordered>
        <div className="strategy-filter-bar">
          <Input
            allowClear
            className="strategy-filter-keyword"
            placeholder="搜索计划名称或 Agent 任务"
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
          <Select
            allowClear
            className="strategy-filter-select"
            placeholder="频率"
            value={frequencyType}
            onChange={setFrequencyType}
            options={frequencyOptions}
          />
          <Select
            allowClear
            className="strategy-filter-select"
            placeholder="状态"
            value={status}
            onChange={setStatus}
            options={Object.entries(statusMeta).map(([value, meta]) => ({ label: meta.label, value }))}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            查询
          </Button>
          <Button icon={<ReloadOutlined />} onClick={handleReset}>
            重置
          </Button>
        </div>

        <Table<ScheduledPlan>
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={loading}
          locale={{ emptyText: <EmptyState title="暂无计划任务" description="请先新建计划。" compact /> }}
          pagination={{
            ...pagination,
            showSizeChanger: false,
          }}
          onChange={(nextPagination) => {
            setQueryState((current) => ({
              ...current,
              page: nextPagination.current || current.page,
              pageSize: nextPagination.pageSize || current.pageSize,
            }));
          }}
          scroll={{ x: 1630 }}
        />
      </Card>

      <Modal
        title={editingPlan ? "编辑计划" : "新建计划"}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => void submitPlan()}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
        width={760}
      >
        <Form<PlanFormValues> form={form} layout="vertical" className="scheduled-plan-form">
          <Form.Item name="name" label="计划名称" rules={[{ required: true, message: "请输入计划名称" }]}>
            <Input placeholder="例如：纳指趋势策略每日研究" />
          </Form.Item>
          <Form.Item name="agentTaskId" label="Agent 任务" rules={[{ required: true, message: "请选择 Agent 任务" }]}>
            <Select
              showSearch
              placeholder="选择 Agent 任务"
              optionFilterProp="label"
              options={agentOptions.map((item) => ({
                label: `${item.name} · ${item.assetName} (${item.assetIdentifier})`,
                value: item.id,
              }))}
            />
          </Form.Item>
          <div className="scheduled-plan-grid">
            <Form.Item name="frequencyType" label="频率" rules={[{ required: true }]}>
              <Select options={frequencyOptions} />
            </Form.Item>
            {watchedFrequency === "hourly" ? (
              <Form.Item name="minuteOfHour" label="分钟" rules={[{ required: true, message: "请选择分钟" }]}>
                <MinuteSelector />
              </Form.Item>
            ) : (
              <Form.Item name="timeOfDay" label="时间" rules={[{ required: true, message: "请选择时间" }]}>
                <TimePicker format="HH:mm" className="scheduled-plan-time-picker" suffixIcon={<span>UTC+8</span>} />
              </Form.Item>
            )}
          </div>
          <ScheduleDetail frequency={watchedFrequency || "daily"} />
          <div className="scheduled-plan-grid">
            <Form.Item name="saveTopN" label="保存最佳策略数量" rules={[{ required: true, message: "请输入 TopN" }]}>
              <InputNumber min={1} max={10} precision={0} className="full-width-input" />
            </Form.Item>
            <Form.Item name="status" label="状态" rules={[{ required: true }]}>
              <Select
                options={[
                  { label: "已启用", value: "enabled" },
                  { label: "未启用", value: "disabled" },
                ]}
              />
            </Form.Item>
          </div>
          <div className="scheduled-threshold-row">
            <Form.Item name="scoreThresholdEnabled" label="启用保存阈值" valuePropName="checked">
              <Switch />
            </Form.Item>
            {thresholdEnabled ? (
              <Form.Item
                name="scoreThreshold"
                label={(
                  <span className="scheduled-label-with-tooltip">
                    综合分数阈值
                    <Tooltip title="仅保存综合分数大于或等于该阈值的迭代策略。">
                      <InfoCircleOutlined />
                    </Tooltip>
                  </span>
                )}
                rules={[{ required: true, message: "请输入阈值" }]}
              >
                <InputNumber min={0} max={100} precision={2} className="scheduled-threshold-input" />
              </Form.Item>
            ) : null}
          </div>
        </Form>
      </Modal>
    </AppShell>
  );
}

function ScheduleDetail({ frequency }: { frequency: FrequencyType }) {
  if (frequency === "monthly") {
    return (
      <div className="scheduled-picker-section">
        <Text type="secondary">天</Text>
        <div className="scheduled-day-grid">
          <Form.Item name="monthDays" noStyle>
            <DaySelector />
          </Form.Item>
          <Form.Item name="useLastDay" valuePropName="checked" noStyle>
            <LastDaySelector />
          </Form.Item>
        </div>
        <Text className="scheduled-helper">并非所有月份都有 31 天。使用“最后一天”选项来选择每个月的最后一天。</Text>
      </div>
    );
  }
  if (frequency === "weekly") {
    return (
      <div className="scheduled-picker-section">
        <Text type="secondary">星期</Text>
        <Form.Item name="weekdays" noStyle>
          <WeekdaySelector />
        </Form.Item>
      </div>
    );
  }
  return null;
}

function DaySelector({ value = [], onChange }: { value?: number[]; onChange?: (value: number[]) => void }) {
  const selected = new Set(value);
  const toggle = (day: number) => {
    const next = new Set(selected);
    if (next.has(day)) {
      next.delete(day);
    } else {
      next.add(day);
    }
    onChange?.(Array.from(next).sort((a, b) => a - b));
  };
  return Array.from({ length: 31 }, (_, index) => index + 1).map((day) => (
    <button
      key={day}
      type="button"
      className={selected.has(day) ? "scheduled-choice scheduled-choice-active" : "scheduled-choice"}
      onClick={() => toggle(day)}
    >
      {day}
    </button>
  ));
}

function LastDaySelector({
  checked,
  value,
  onChange,
}: {
  checked?: boolean;
  value?: boolean;
  onChange?: (value: boolean) => void;
}) {
  const active = Boolean(checked ?? value);
  return (
    <button
      type="button"
      className={active ? "scheduled-choice scheduled-choice-active scheduled-last-day" : "scheduled-choice scheduled-last-day"}
      onClick={() => onChange?.(!active)}
    >
      最后一天
    </button>
  );
}

function WeekdaySelector({ value = [], onChange }: { value?: number[]; onChange?: (value: number[]) => void }) {
  const selected = new Set(value);
  const toggle = (day: number) => {
    const next = new Set(selected);
    if (next.has(day)) {
      next.delete(day);
    } else {
      next.add(day);
    }
    onChange?.(Array.from(next).sort((a, b) => a - b));
  };
  return (
    <div className="scheduled-week-grid">
      {weekdayOptions.map((item) => (
        <button
          key={item.value}
          type="button"
          className={selected.has(item.value) ? "scheduled-choice scheduled-choice-active" : "scheduled-choice"}
          onClick={() => toggle(item.value)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

function MinuteSelector({ value = 0, onChange }: { value?: number; onChange?: (value: number) => void }) {
  return (
    <div className="scheduled-minute-row">
      <InputNumber min={0} max={59} precision={0} value={value} onChange={(next) => onChange?.(Number(next || 0))} />
      <Slider min={0} max={59} value={value} onChange={onChange} />
    </div>
  );
}

function normalizePlanPayload(values: PlanFormValues) {
  return {
    ...values,
    timeOfDay: values.timeOfDay ? values.timeOfDay.format("HH:mm") : undefined,
    monthDays: values.monthDays || [],
    useLastDay: Boolean(values.useLastDay),
    weekdays: values.weekdays || [],
    scoreThresholdEnabled: Boolean(values.scoreThresholdEnabled),
  };
}

function formatSchedule(plan: ScheduledPlan): string {
  if (plan.frequencyType === "hourly") return `每小时第 ${plan.minuteOfHour ?? 0} 分`;
  const time = plan.timeOfDay || "00:00";
  if (plan.frequencyType === "daily") return `每日 ${time}`;
  if (plan.frequencyType === "weekly") {
    const labels = plan.weekdays.map((day) => weekdayOptions.find((item) => item.value === day)?.label || day).join("、");
    return `每周 ${labels} ${time}`;
  }
  const days = [...(plan.monthDays || []).map(String), ...(plan.useLastDay ? ["最后一天"] : [])].join("、");
  return `每月 ${days} ${time}`;
}

function formatDateTime(value?: string | null): string {
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
    hour12: false,
  }).format(date);
}
