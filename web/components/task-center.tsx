"use client";

import {
  CheckCircleFilled,
  ClockCircleFilled,
  ExclamationCircleFilled,
  RobotOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { Button, Divider, Drawer, Empty, Progress, Space, Tag, Typography } from "antd";
import Lottie from "lottie-react";
import type { LottieRefCurrentProps } from "lottie-react";
import { useEffect, useMemo, useRef, useState } from "react";
import sphereAnimation from "@/lib/lottie/sphere.json";
import { getAccessToken } from "@/lib/auth";
import { apiGet } from "@/lib/api";

const { Text, Title } = Typography;

type TaskStatus = "queued" | "running" | "success" | "failure";
type TaskType = "sync" | "agent";

type TaskItem = {
  taskId: string;
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

const statusMeta: Record<
  TaskStatus,
  { label: string; color: string; icon: React.ReactNode }
> = {
  queued: {
    label: "排队中",
    color: "default",
    icon: <ClockCircleFilled />,
  },
  running: {
    label: "运行中",
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
};

export function TaskCenter() {
  const [open, setOpen] = useState(false);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const lottieRef = useRef<LottieRefCurrentProps>(null);

  const runningCount = useMemo(
    () => tasks.filter((task) => task.status === "queued" || task.status === "running").length,
    [tasks],
  );

  const groupedTasks = useMemo(
    () => ({
      sync: tasks.filter((task) => task.type === "sync"),
      agent: tasks.filter((task) => task.type === "agent"),
    }),
    [tasks],
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
          setTasks(response.items);
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
            return;
          }

          if (message.type === "task.updated") {
            setTasks((current) => mergeTask(current, message.payload));
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
        width={420}
        className="task-center-drawer"
      >
        <section className="task-center-section">
          <div className="task-center-section-head">
            <Title level={5}>同步任务</Title>
            <Text>{groupedTasks.sync.length} 个</Text>
          </div>
          {groupedTasks.sync.length ? (
            <Space orientation="vertical" size={12} className="task-center-list">
              {groupedTasks.sync.map((task) => (
                <TaskCard key={task.taskId} task={task} />
              ))}
            </Space>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无同步任务" />
          )}
        </section>

        <Divider className="task-center-divider" />

        <section className="task-center-section">
          <div className="task-center-section-head">
            <Title level={5}>AI Agent 任务</Title>
            <Text>{groupedTasks.agent.length} 个</Text>
          </div>
          {groupedTasks.agent.length ? (
            <Space orientation="vertical" size={12} className="task-center-list">
              {groupedTasks.agent.map((task) => (
                <TaskCard key={task.taskId} task={task} />
              ))}
            </Space>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无 AI Agent 任务" />
          )}
        </section>
      </Drawer>
    </>
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

      {task.progressText ? <Text className="task-center-progress-text">{task.progressText}</Text> : null}

      {task.recordsAffected !== undefined && task.recordsAffected !== null ? (
        <Text className="task-center-progress-text">处理记录：{task.recordsAffected}</Text>
      ) : null}

      <div className="task-center-log-list">
        {task.logs.length ? (
          task.logs.map((log, index) => (
            <div key={`${task.taskId}-${index}`} className="task-center-log-item">
              <span className="task-center-log-dot" />
              <span>{log}</span>
            </div>
          ))
        ) : (
          <div className="task-center-log-item">
            <span className="task-center-log-dot" />
            <span>暂无日志</span>
          </div>
        )}
      </div>

      <Button type="link" className="task-center-action">
        查看详情
      </Button>
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
    if (!log || seen.has(log)) continue;
    seen.add(log);
    result.push(log);
  }
  return result.slice(-3);
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
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";

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
