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

const { Text, Title } = Typography;

type TaskStatus = "queued" | "running" | "success" | "failure";
type TaskType = "sync" | "agent";

type TaskItem = {
  id: string;
  name: string;
  type: TaskType;
  status: TaskStatus;
  startedAt: string;
  updatedAt: string;
  progressCurrent?: number;
  progressTotal?: number;
  progressText?: string;
  logs: string[];
};

const mockTasks: TaskItem[] = [
  {
    id: "sync-stock-daily-1",
    name: "股票历史日线同步",
    type: "sync",
    status: "running",
    startedAt: "今天 10:12",
    updatedAt: "刚刚",
    progressCurrent: 18,
    progressTotal: 54,
    progressText: "正在补全 XNAS / AAPL",
    logs: ["任务已提交", "已加载股票清单", "正在补全最新缺失日期"],
  },
  {
    id: "sync-country-1",
    name: "国家/地区清单同步",
    type: "sync",
    status: "success",
    startedAt: "今天 09:42",
    updatedAt: "今天 09:42",
    progressCurrent: 1,
    progressTotal: 1,
    progressText: "同步完成",
    logs: ["任务已提交", "共更新 38 条记录"],
  },
  {
    id: "agent-run-1",
    name: "AI Agent 策略探索",
    type: "agent",
    status: "queued",
    startedAt: "今天 10:20",
    updatedAt: "刚刚",
    progressText: "等待执行器启动",
    logs: ["Agent 任务已创建，等待调度"],
  },
];

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
  const lottieRef = useRef<LottieRefCurrentProps>(null);

  const runningCount = useMemo(
    () => mockTasks.filter((task) => task.status === "queued" || task.status === "running").length,
    [],
  );

  const groupedTasks = useMemo(
    () => ({
      sync: mockTasks.filter((task) => task.type === "sync"),
      agent: mockTasks.filter((task) => task.type === "agent"),
    }),
    [],
  );

  useEffect(() => {
    lottieRef.current?.setSpeed(runningCount > 0 ? runningCount : 0.3);
  }, [runningCount]);

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
                <TaskCard key={task.id} task={task} />
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
                <TaskCard key={task.id} task={task} />
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
        <span>开始时间：{task.startedAt}</span>
        <span>最近更新：{task.updatedAt}</span>
      </div>

      {percent !== undefined ? (
        <Progress percent={percent} size="small" showInfo={false} strokeColor="#6366f1" />
      ) : null}

      {task.progressText ? <Text className="task-center-progress-text">{task.progressText}</Text> : null}

      <div className="task-center-log-list">
        {task.logs.map((log, index) => (
          <div key={`${task.id}-${index}`} className="task-center-log-item">
            <span className="task-center-log-dot" />
            <span>{log}</span>
          </div>
        ))}
      </div>

      <Button type="link" className="task-center-action">
        查看详情
      </Button>
    </div>
  );
}
