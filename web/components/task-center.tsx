"use client";

import {
  CheckCircleFilled,
  ClockCircleFilled,
  ExclamationCircleFilled,
  RobotOutlined,
  StopOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { Drawer, Progress, Segmented, Space, Tag, Typography, notification } from "antd";
import Lottie from "lottie-react";
import type { LottieRefCurrentProps } from "lottie-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import sphereAnimation from "@/lib/lottie/sphere.json";
import { normalizeDisplayText } from "@/components/data-center/utils";
import { getAccessToken } from "@/lib/auth";
import { apiGet } from "@/lib/api";

const { Text, Title } = Typography;

type TaskStatus = "queued" | "running" | "success" | "failure" | "stopped";
type TaskType = "sync" | "agent";
type TaskFilter = "active" | "finished" | "all";

type TaskItem = {
  taskId: string;
  entityType?: "agent_task" | null;
  entityId?: number | null;
  name: string;
  type: TaskType;
  status: TaskStatus;
  startedAt: string | null;
  updatedAt: string | null;
  progressCurrent?: number;
  progressTotal?: number;
  progressText?: string | null;
  recordsAffected?: number | null;
  durationMs?: number | null;
  assetName?: string | null;
  assetIdentifier?: string | null;
  bestAnnualReturn?: number | null;
  bestMaxDrawdown?: number | null;
  bestSharpe?: number | null;
  logs: string[];
};

type TaskSnapshotResponse = {
  items: TaskItem[];
};

type TaskSocketMessage =
  | {
      type: "snapshot";
      payload: {
        tasks: TaskItem[];
      };
    }
  | {
      type: "task.updated";
      payload: TaskItem;
      userId?: number | null;
    }
  | {
      type: "error";
      message: string;
    };

const FINISHED_TASK_LIMIT = 30;

const statusMeta: Record<TaskStatus, { label: string; color: string; icon: React.ReactNode }> = {
  queued: {
    label: "排队中",
    color: "default",
    icon: <ClockCircleFilled />,
  },
  running: {
    label: "进行中",
    color: "processing",
    icon: <SyncOutlined spin />,
  },
  success: {
    label: "已完成",
    color: "success",
    icon: <CheckCircleFilled />,
  },
  failure: {
    label: "失败",
    color: "error",
    icon: <ExclamationCircleFilled />,
  },
  stopped: {
    label: "已停止",
    color: "warning",
    icon: <StopOutlined />,
  },
};

export function TaskCenter() {
  const [notificationApi, notificationHolder] = notification.useNotification();
  const [open, setOpen] = useState(false);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [filter, setFilter] = useState<TaskFilter>("active");
  const lottieRef = useRef<LottieRefCurrentProps>(null);
  const statusRef = useRef<Record<string, TaskStatus>>({});

  const activeTasks = useMemo(
    () => tasks.filter((task) => task.status === "queued" || task.status === "running"),
    [tasks],
  );
  const finishedTasks = useMemo(
    () => tasks.filter((task) => task.status === "success" || task.status === "failure" || task.status === "stopped"),
    [tasks],
  );
  const runningCount = activeTasks.length;

  const visibleTasks = useMemo(() => {
    if (filter === "active") {
      return activeTasks;
    }
    if (filter === "finished") {
      return finishedTasks.slice(0, FINISHED_TASK_LIMIT);
    }
    return [...activeTasks, ...finishedTasks.slice(0, FINISHED_TASK_LIMIT)];
  }, [activeTasks, filter, finishedTasks]);

  const groupedTasks = useMemo(
    () => ({
      sync: visibleTasks.filter((task) => task.type === "sync"),
      agent: visibleTasks.filter((task) => task.type === "agent"),
    }),
    [visibleTasks],
  );

  useEffect(() => {
    lottieRef.current?.setSpeed(runningCount > 0 ? runningCount : 0.3);
  }, [runningCount]);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      return;
    }

    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;

    const connect = async () => {
      try {
        const response = await apiGet<TaskSnapshotResponse>("/task-center/tasks", token);
        if (!cancelled) {
          setTasks(sortTasks(response.items));
          statusRef.current = Object.fromEntries(response.items.map((item) => [item.taskId, item.status]));
        }
      } catch {
        if (!cancelled) {
          setTasks([]);
        }
      }

      if (cancelled) {
        return;
      }

      socket = new WebSocket(buildTaskCenterWsUrl(token));

      socket.onmessage = (event) => {
        if (cancelled) {
          return;
        }

        try {
          const message = JSON.parse(event.data) as TaskSocketMessage;
          if (message.type === "snapshot") {
            setTasks(sortTasks(message.payload.tasks));
            statusRef.current = Object.fromEntries(message.payload.tasks.map((item) => [item.taskId, item.status]));
            return;
          }

          if (message.type === "task.updated") {
            const previousStatus = statusRef.current[message.payload.taskId];
            statusRef.current[message.payload.taskId] = message.payload.status;
            setTasks((current) => mergeTask(current, message.payload));
            if (previousStatus !== message.payload.status && message.payload.status !== "queued") {
              notificationApi.open({
                key: message.payload.taskId,
                message: message.payload.name,
                description: normalizeDisplayText(
                  message.payload.progressText || statusMeta[message.payload.status].label,
                ),
                placement: "topRight",
                duration: 3,
              });
            }
            return;
          }

          if (message.type === "error") {
            console.error("[task-center]", message.message);
          }
        } catch (error) {
          console.error("[task-center] invalid websocket payload", error);
        }
      };

      socket.onclose = () => {
        if (!cancelled) {
          reconnectTimer = window.setTimeout(() => {
            void connect();
          }, 2000);
        }
      };

      socket.onerror = () => {
        socket?.close();
      };
    };

    void connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
      }
      socket?.close();
    };
  }, []);

  return (
    <>
      {notificationHolder}
      <div className="task-center-fab-wrap">
        <button
          className="task-center-fab"
          type="button"
          aria-label="打开任务中心"
          onClick={() => setOpen(true)}
        >
          <Lottie
            lottieRef={lottieRef}
            animationData={sphereAnimation}
            autoplay
            loop
            className="task-center-fab-lottie"
          />
        </button>
      </div>

      <Drawer
        title="任务中心"
        placement="right"
        open={open}
        onClose={() => setOpen(false)}
        width={760}
        className="task-center-drawer"
        extra={
          <Segmented<TaskFilter>
            size="small"
            value={filter}
            onChange={(value) => setFilter(value as TaskFilter)}
            options={[
              { label: `进行中 ${runningCount}`, value: "active" },
              { label: `已完成 ${finishedTasks.length}`, value: "finished" },
              { label: `全部 ${tasks.length}`, value: "all" },
            ]}
          />
        }
      >
        <div className="task-center-grid">
          <TaskSection
            title="同步任务"
            helper={filter !== "active" ? `已完成仅展示最新 ${FINISHED_TASK_LIMIT} 个` : undefined}
            tasks={groupedTasks.sync}
            emptyText="当前筛选下暂无同步任务"
          />
          <TaskSection
            title="AI Agent 任务"
            helper={filter !== "active" ? `已完成仅展示最新 ${FINISHED_TASK_LIMIT} 个` : undefined}
            tasks={groupedTasks.agent}
            emptyText="当前筛选下暂无 AI Agent 任务"
          />
        </div>
      </Drawer>
    </>
  );
}

function TaskSection({
  title,
  helper,
  tasks,
  emptyText,
}: {
  title: string;
  helper?: string;
  tasks: TaskItem[];
  emptyText: string;
}) {
  return (
    <section className="task-center-section">
      <div className="task-center-section-head">
        <div className="task-center-section-copy">
          <Title level={5}>{title}</Title>
          {helper ? <Text className="task-center-subtle">{helper}</Text> : null}
        </div>
        <Text>{tasks.length} 项</Text>
      </div>
      {tasks.length ? (
        <Space orientation="vertical" size={12} className="task-center-list">
          {tasks.map((task) => (
            <TaskCard key={task.taskId} task={task} />
          ))}
        </Space>
      ) : (
        <EmptyState title={emptyText} compact />
      )}
    </section>
  );
}

function TaskCard({ task }: { task: TaskItem }) {
  const meta = statusMeta[task.status];
  const percent =
    task.progressCurrent !== undefined && task.progressTotal
      ? Math.min(100, Math.round((task.progressCurrent / task.progressTotal) * 100))
      : undefined;

  return (
    <div className="task-center-card">
      <div className="task-center-card-head">
        <div className="task-center-card-title">
          {task.type === "agent" ? <RobotOutlined /> : <SyncOutlined />}
          <strong>{task.name}</strong>
        </div>
        <Tag icon={meta.icon} color={meta.color}>
          {meta.label}
        </Tag>
      </div>

      <div className="task-center-meta">
        <span>开始时间：{formatDisplayTime(task.startedAt)}</span>
        <span>最近更新：{formatDisplayTime(task.updatedAt)}</span>
      </div>

      {percent !== undefined ? (
        <Progress percent={percent} size="small" showInfo={false} strokeColor="#6366f1" />
      ) : null}

      {task.type === "agent" ? (
        <AgentTaskSummary task={task} />
      ) : (
        <>
          {task.progressText ? (
            <Text className="task-center-progress-text">{normalizeDisplayText(task.progressText)}</Text>
          ) : null}

          {task.recordsAffected !== undefined && task.recordsAffected !== null ? (
            <Text className="task-center-progress-text">处理记录：{task.recordsAffected}</Text>
          ) : null}

          <div className="task-center-log-list">
            {task.logs.length ? (
              task.logs.map((log, index) => (
                <div key={`${task.taskId}-${index}`} className="task-center-log-item">
                  <span className="task-center-log-dot" />
                  <span>{normalizeDisplayText(log)}</span>
                </div>
              ))
            ) : (
              <div className="task-center-log-item">
                <span className="task-center-log-dot" />
                <span>暂无日志</span>
              </div>
            )}
          </div>
        </>
      )}

    </div>
  );
}

function AgentTaskSummary({ task }: { task: TaskItem }) {
  return (
    <div className="task-center-agent-summary">
      <div className="task-center-agent-asset">
        <Text className="task-center-subtle">标的</Text>
        <strong>{task.assetName || "-"}</strong>
        {task.assetIdentifier ? <Text className="task-center-subtle">{task.assetIdentifier}</Text> : null}
      </div>
      <div className="task-center-agent-metrics">
        <AgentSummaryMetric label="最佳收益" value={formatPercent(task.bestAnnualReturn)} positive />
        <AgentSummaryMetric label="最大回撤" value={formatPercent(task.bestMaxDrawdown)} negative />
        <AgentSummaryMetric label="Sharpe" value={task.bestSharpe == null ? "-" : task.bestSharpe.toFixed(2)} />
      </div>
      {task.progressText ? (
        <Text className="task-center-progress-text">{normalizeDisplayText(task.progressText)}</Text>
      ) : null}
    </div>
  );
}

function AgentSummaryMetric({
  label,
  value,
  positive,
  negative,
}: {
  label: string;
  value: string;
  positive?: boolean;
  negative?: boolean;
}) {
  return (
    <div className="task-center-agent-metric">
      <span>{label}</span>
      <strong className={positive ? "positive-text" : negative ? "negative-text" : undefined}>{value}</strong>
    </div>
  );
}

function mergeTask(current: TaskItem[], incoming: TaskItem): TaskItem[] {
  const existing = current.find((item) => item.taskId === incoming.taskId);
  if (!existing) {
    return sortTasks([incoming, ...current]);
  }

  const merged: TaskItem = {
    ...existing,
    ...incoming,
    logs: dedupeLogs([...(existing.logs ?? []), ...(incoming.logs ?? [])]),
  };

  return sortTasks(current.map((item) => (item.taskId === incoming.taskId ? merged : item)));
}

function sortTasks(items: TaskItem[]): TaskItem[] {
  return [...items].sort((left, right) => {
    const rightTime = new Date(right.updatedAt ?? right.startedAt ?? 0).getTime();
    const leftTime = new Date(left.updatedAt ?? left.startedAt ?? 0).getTime();
    return rightTime - leftTime;
  });
}

function dedupeLogs(logs: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const log of logs) {
    if (!log || seen.has(log)) {
      continue;
    }
    seen.add(log);
    result.push(log);
  }
  return result.slice(-6);
}

function formatPercent(value: number | null | undefined): string {
  return value == null ? "-" : `${value.toFixed(2)}%`;
}

function buildTaskCenterWsUrl(token: string): string {
  const configuredBase = process.env.NEXT_PUBLIC_WS_BASE_URL?.replace(/\/$/, "");
  if (configuredBase) {
    return `${configuredBase}/ws/tasks?token=${encodeURIComponent(token)}`;
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://localhost:8000/ws/tasks?token=${encodeURIComponent(token)}`;
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
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}
