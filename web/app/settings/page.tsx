"use client";

import {
  BellOutlined,
  DatabaseOutlined,
  HolderOutlined,
  InfoCircleOutlined,
  LinkOutlined,
  LockOutlined,
  RobotOutlined,
  SaveOutlined,
  SlidersOutlined,
} from "@ant-design/icons";
import {
  Button,
  Divider,
  Input,
  InputNumber,
  Menu,
  Space,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppLoader } from "@/components/app-loader";
import { AppShell } from "@/components/app-shell";
import { getAccessToken } from "@/lib/auth";
import { apiGet, apiRequest } from "@/lib/api";

const { Text, Title } = Typography;

type SectionKey = "data-sources" | "ai" | "scoring" | "notice" | "account";

type AiModelRow = {
  key: string;
  name: string;
  model: string;
  baseUrl: string;
  apiKey: string;
};

type SettingsPayload = {
  dataSource: {
    canghaiApiKey: string;
    canghaiTokenCheckEnabled: boolean;
  };
  ai: {
    models: Array<{
      name: string;
      model: string;
      baseUrl: string;
      apiKey: string;
    }>;
  };
  notifications: {
    dataSync: boolean;
    agentGoal: boolean;
    backtest: boolean;
  };
  scoring: {
    performanceScoreWeights: {
      annualReturn: number;
      sharpe: number;
      maxDrawdown: number;
    };
  };
  account: {
    keepSignedIn: boolean;
  };
};

type SettingsState = Omit<SettingsPayload, "ai"> & {
  ai: {
    models: AiModelRow[];
  };
};

type CanghaiStatusResponse = {
  sourceKey: string;
  sourceName: string;
  scheduledCheckEnabled: boolean;
  status: {
    status: string;
    tokenStatus: string;
    lastCheckedAt: string | null;
    lastSuccessAt: string | null;
    lastFailedAt: string | null;
    latencyMs: number | null;
    httpStatus: number | null;
    message: string | null;
    failureCount: number;
  };
};

const defaultSettings: SettingsState = {
  dataSource: {
    canghaiApiKey: "",
    canghaiTokenCheckEnabled: true,
  },
  ai: {
    models: [
      {
        key: "model-default-0",
        name: "OpenAI",
        model: "gpt-4.1",
        baseUrl: "https://api.openai.com/v1",
        apiKey: "",
      },
    ],
  },
  notifications: {
    dataSync: false,
    agentGoal: false,
    backtest: false,
  },
  scoring: {
    performanceScoreWeights: {
      annualReturn: 0.7,
      sharpe: 5,
      maxDrawdown: 0.2,
    },
  },
  account: {
    keepSignedIn: true,
  },
};

const sectionNav = [
  { key: "data-sources", icon: <DatabaseOutlined />, label: "数据源配置" },
  { key: "ai", icon: <RobotOutlined />, label: "AI 配置" },
  { key: "scoring", icon: <SlidersOutlined />, label: "评分权重" },
  { key: "notice", icon: <BellOutlined />, label: "通知" },
  { key: "account", icon: <LockOutlined />, label: "账号偏好" },
] satisfies Array<{ key: SectionKey; icon: React.ReactNode; label: string }>;

export default function SettingsPage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [selectedSection, setSelectedSection] = useState<SectionKey>("data-sources");
  const [settings, setSettings] = useState<SettingsState>(defaultSettings);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [draggingModelKey, setDraggingModelKey] = useState<string | null>(null);
  const [testingModelKey, setTestingModelKey] = useState<string | null>(null);
  const [testingCanghaiToken, setTestingCanghaiToken] = useState(false);
  const [canghaiStatus, setCanghaiStatus] = useState<CanghaiStatusResponse | null>(null);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const token = getAccessToken();
        const response = await apiGet<{ settings: SettingsPayload }>("/settings/me", token);
        setSettings(mergeSettings(response.settings));
        const statusResponse = await apiGet<CanghaiStatusResponse>(
          "/settings/data-sources/canghai/status",
          token,
        );
        setCanghaiStatus(statusResponse);
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载系统设置失败");
      } finally {
        setLoading(false);
      }
    };

    void loadSettings();
  }, [messageApi]);

  const handleTestCanghaiToken = useCallback(async () => {
    setTestingCanghaiToken(true);
    try {
      const token = getAccessToken();
      const response = await apiRequest<CanghaiStatusResponse>(
        "/settings/data-sources/canghai/test-token",
        {
          method: "POST",
          body: {
            apiKey: settings.dataSource.canghaiApiKey,
          },
          token,
        },
      );
      setCanghaiStatus(response);
      if (response.status.tokenStatus === "valid") {
        messageApi.success("沧海数据 API Key 检测通过");
      } else {
        messageApi.warning("沧海数据 API Key 检测未通过");
      }
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "沧海数据 API Key 检测失败");
    } finally {
      setTestingCanghaiToken(false);
    }
  }, [messageApi, settings.dataSource.canghaiApiKey]);

  const handleTestAiModel = useCallback(async (record: AiModelRow) => {
    setTestingModelKey(record.key);
    try {
      const token = getAccessToken();
      const response = await apiRequest<{ ok: boolean; message: string; content: string }>("/settings/test-ai-model", {
        method: "POST",
        body: {
          modelConfig: {
            name: record.name,
            model: record.model,
            baseUrl: record.baseUrl,
            apiKey: record.apiKey,
          },
        },
        token,
      });
      messageApi.success(`测试成功：${response.content || response.message}`);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "AI 模型测试失败");
    } finally {
      setTestingModelKey(null);
    }
  }, [messageApi]);

  const aiModelColumns = useMemo<ColumnsType<AiModelRow>>(
    () => [
      {
        title: "",
        width: 86,
        render: (_, record, index) => (
          <span className="settings-drag-handle" title="拖拽排序">
            <HolderOutlined />
            {index === 0 ? <Tag color="blue">默认</Tag> : null}
          </span>
        ),
      },
      {
        title: "名称",
        dataIndex: "name",
        render: (value: string, record) => (
          <Input
            value={value}
            onChange={(event) => updateAiModel(record.key, "name", event.target.value)}
            placeholder="例如 OpenAI"
          />
        ),
      },
      {
        title: "模型名称",
        dataIndex: "model",
        render: (value: string, record) => (
          <Input
            value={value}
            onChange={(event) => updateAiModel(record.key, "model", event.target.value)}
            placeholder="例如 gpt-4.1"
          />
        ),
      },
      {
        title: "Base URL",
        dataIndex: "baseUrl",
        render: (value: string, record) => (
          <Input
            value={value}
            onChange={(event) => updateAiModel(record.key, "baseUrl", event.target.value)}
            placeholder="https://api.openai.com/v1"
          />
        ),
      },
      {
        title: "API Key",
        dataIndex: "apiKey",
        render: (value: string, record) => (
          <Input.Password
            value={value}
            onChange={(event) => updateAiModel(record.key, "apiKey", event.target.value)}
            placeholder="请输入 API Key"
          />
        ),
      },
      {
        title: "操作",
        width: 150,
        fixed: "right",
        render: (_, record) => (
          <Space size={8}>
            <Button
              type="link"
              loading={testingModelKey === record.key}
              onClick={() => void handleTestAiModel(record)}
            >
              测试
            </Button>
            <Button
              type="link"
              danger
              disabled={settings.ai.models.length <= 1}
              onClick={() =>
                setSettings((current) => ({
                  ...current,
                  ai: {
                    models: current.ai.models.filter((row) => row.key !== record.key),
                  },
                }))
              }
            >
              删除
            </Button>
          </Space>
        ),
      },
    ],
    [handleTestAiModel, settings.ai.models.length, testingModelKey],
  );

  const moveAiModel = (fromKey: string, toKey: string) => {
    if (fromKey === toKey) return;
    setSettings((current) => {
      const rows = [...current.ai.models];
      const fromIndex = rows.findIndex((row) => row.key === fromKey);
      const toIndex = rows.findIndex((row) => row.key === toKey);
      if (fromIndex < 0 || toIndex < 0) return current;
      const [moving] = rows.splice(fromIndex, 1);
      rows.splice(toIndex, 0, moving);
      return {
        ...current,
        ai: {
          models: rows,
        },
      };
    });
  };

  const updateAiModel = (key: string, field: keyof Omit<AiModelRow, "key">, value: string) => {
    setSettings((current) => ({
      ...current,
      ai: {
        models: current.ai.models.map((row) => (row.key === key ? { ...row, [field]: value } : row)),
      },
    }));
  };

  const updateScoreWeight = (
    key: keyof SettingsPayload["scoring"]["performanceScoreWeights"],
    value: number | null,
  ) => {
    setSettings((current) => ({
      ...current,
      scoring: {
        performanceScoreWeights: {
          ...current.scoring.performanceScoreWeights,
          [key]: normalizeWeightInput(key, value),
        },
      },
    }));
  };

  const updateNotificationSetting = async (
    key: keyof SettingsPayload["notifications"],
    checked: boolean,
  ) => {
    if (!checked) {
      setSettings((current) => ({
        ...current,
        notifications: {
          ...current.notifications,
          [key]: false,
        },
      }));
      return;
    }

    if (!("Notification" in window)) {
      messageApi.warning("当前浏览器不支持桌面通知");
      return;
    }

    let permission = window.Notification.permission;
    if (permission === "default") {
      permission = await window.Notification.requestPermission();
    }

    if (permission !== "granted") {
      messageApi.warning("浏览器通知权限未开启");
      return;
    }

    setSettings((current) => ({
      ...current,
      notifications: {
        ...current.notifications,
        [key]: true,
      },
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const token = getAccessToken();
      const payload = serializeSettings(settings);
      const response = await apiRequest<{ settings: SettingsPayload }>("/settings/me", {
        method: "PUT",
        body: payload,
        token,
      });
      setSettings(mergeSettings(response.settings));
      messageApi.success("系统设置已保存");
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "保存系统设置失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell>
      {contextHolder}
      <section className="dashboard-heading">
        <div>
          <Title level={1}>系统设置</Title>
          <Text className="page-description">配置沧海数据密钥、AI 模型、通知和账号偏好。</Text>
        </div>
        <Space>
          <Button
            onClick={() => setSettings(defaultSettings)}
            disabled={loading || saving}
          >
            恢复默认
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            onClick={() => void handleSave()}
          >
            保存设置
          </Button>
        </Space>
      </section>

      <div className="settings-layout">
        <aside className="settings-nav">
          <Menu
            mode="inline"
            selectedKeys={[selectedSection]}
            items={sectionNav}
            onClick={({ key }) => {
              setSelectedSection(key as SectionKey);
              document.getElementById(`settings-${key}`)?.scrollIntoView({
                behavior: "smooth",
                block: "start",
              });
            }}
          />
        </aside>

        <main className="settings-content">
          {loading ? (
            <div className="settings-loading">
              <AppLoader message="正在加载系统设置" />
            </div>
          ) : (
            <>
              <SettingsSection
                description="当前仅支持预设的沧海数据接入，请在此配置对应的访问密钥。"
                icon={<DatabaseOutlined />}
                id="data-sources"
                title="数据源配置"
              >
                <div className="data-source-config-list">
                  <div className="data-source-config-item">
                    <div className="data-source-setting-label">
                      <strong>
                        沧海数据 API Key
                        <a
                          className="settings-inline-link"
                          href="https://tsanghi.com/fin/user"
                          rel="noreferrer"
                          target="_blank"
                          title="打开沧海数据用户中心"
                        >
                          <LinkOutlined />
                        </a>
                      </strong>
                    </div>
                    <div className="data-source-setting-control">
                      <Input.Password
                        value={settings.dataSource.canghaiApiKey}
                        onChange={(event) =>
                          setSettings((current) => ({
                            ...current,
                            dataSource: {
                              ...current.dataSource,
                              canghaiApiKey: event.target.value,
                            },
                          }))
                        }
                        placeholder="请输入 API Key"
                      />
                      <div className="data-source-status-panel">
                        <div className="data-source-status-head">
                          <div className="data-source-status-title">
                            <label className="settings-field-label">API Key 状态</label>
                            <Tag color={tokenStatusColor(canghaiStatus?.status.tokenStatus)}>
                              {tokenStatusText(canghaiStatus?.status.tokenStatus)}
                            </Tag>
                          </div>
                          <Button loading={testingCanghaiToken} onClick={() => void handleTestCanghaiToken()}>
                            测试
                          </Button>
                        </div>
                        <div className="data-source-status-grid">
                          <span>最近检测：{formatDateTime(canghaiStatus?.status.lastCheckedAt)}</span>
                          <span>延迟：{formatLatency(canghaiStatus?.status.latencyMs)}</span>
                          <span>HTTP：{canghaiStatus?.status.httpStatus ?? "-"}</span>
                          <span>连续失败：{canghaiStatus?.status.failureCount ?? 0}</span>
                        </div>
                      </div>
                    </div>
                    <div className="data-source-setting-label">
                      <strong>
                        定时检测 API Key 有效性
                        <Tooltip title="仅在当前账号在线时，每 30 分钟检测一次 API Key 有效性。">
                          <InfoCircleOutlined className="settings-help-icon" />
                        </Tooltip>
                      </strong>
                    </div>
                    <div className="data-source-setting-control data-source-switch-control">
                      <Switch
                        checked={settings.dataSource.canghaiTokenCheckEnabled}
                        onChange={(checked) =>
                          setSettings((current) => ({
                            ...current,
                            dataSource: {
                              ...current.dataSource,
                              canghaiTokenCheckEnabled: checked,
                            },
                          }))
                        }
                      />
                    </div>
                  </div>
                </div>
              </SettingsSection>

              <SettingsSection
                description="配置一个或多个 OpenAI 兼容模型，用于策略生成、回测结果分析和 Agent 自动迭代。"
                icon={<RobotOutlined />}
                id="ai"
                title="AI 配置"
              >
                <Table
                  columns={aiModelColumns}
                  dataSource={settings.ai.models}
                  pagination={false}
                  rowKey="key"
                  rowClassName={(record) => (record.key === draggingModelKey ? "settings-dragging-row" : "")}
                  onRow={(record) => ({
                    draggable: true,
                    onDragStart: () => setDraggingModelKey(record.key),
                    onDragOver: (event) => event.preventDefault(),
                    onDrop: () => {
                      if (draggingModelKey) {
                        moveAiModel(draggingModelKey, record.key);
                      }
                      setDraggingModelKey(null);
                    },
                    onDragEnd: () => setDraggingModelKey(null),
                  })}
                  scroll={{ x: 980 }}
                />
                <Button
                  className="settings-table-action"
                  onClick={() =>
                    setSettings((current) => ({
                      ...current,
                      ai: {
                        models: [
                          ...current.ai.models,
                          {
                            key: `model-${Date.now()}`,
                            name: "",
                            model: "",
                            baseUrl: "",
                            apiKey: "",
                          },
                        ],
                      },
                    }))
                  }
                >
                  添加模型
                </Button>
              </SettingsSection>

              <SettingsSection
                description="调整策略综合分的计算权重。Agent、策略评估和样本分都会使用这套统一口径。"
                icon={<SlidersOutlined />}
                id="scoring"
                title="评分权重"
              >
                <div className="settings-weight-grid">
                  <WeightInput
                    title="年化收益权重"
                    description="年化收益越高，该权重越会拉高综合分。"
                    value={settings.scoring.performanceScoreWeights.annualReturn}
                    onChange={(value) => updateScoreWeight("annualReturn", value)}
                  />
                  <WeightInput
                    title="Sharpe 权重"
                    description="用于衡量单位波动下的收益表现，范围 1-10。"
                    min={1}
                    max={10}
                    value={settings.scoring.performanceScoreWeights.sharpe}
                    onChange={(value) => updateScoreWeight("sharpe", value)}
                  />
                  <WeightInput
                    title="最大回撤权重"
                    description="该项会作为扣分项，权重越高，对回撤越敏感。"
                    value={settings.scoring.performanceScoreWeights.maxDrawdown}
                    onChange={(value) => updateScoreWeight("maxDrawdown", value)}
                  />
                </div>
                <Text type="secondary">
                  当前公式：综合分 = 年化收益 * {settings.scoring.performanceScoreWeights.annualReturn}
                  {" + "}Sharpe * {settings.scoring.performanceScoreWeights.sharpe}
                  {" - "}最大回撤 * {settings.scoring.performanceScoreWeights.maxDrawdown}
                </Text>
              </SettingsSection>

              <SettingsSection
                description="以下事件会通过浏览器桌面通知推送。"
                icon={<BellOutlined />}
                id="notice"
                title="通知设置"
              >
                <SettingSwitch
                  checked={settings.notifications.dataSync}
                  description="同步失败、部分成功或质量问题升级时，通过浏览器桌面通知提醒。"
                  onChange={(checked) => void updateNotificationSetting("dataSync", checked)}
                  title="数据同步异常"
                />
                <SettingSwitch
                  checked={settings.notifications.agentGoal}
                  description="找到满足目标的策略时，通过浏览器桌面通知提醒。"
                  onChange={(checked) => void updateNotificationSetting("agentGoal", checked)}
                  title="Agent 达标提醒"
                />
                <SettingSwitch
                  checked={settings.notifications.backtest}
                  description="耗时回测完成后，通过浏览器桌面通知提醒。"
                  onChange={(checked) => void updateNotificationSetting("backtest", checked)}
                  title="回测完成提醒"
                />
              </SettingsSection>

              <SettingsSection
                description="控制当前账号的会话和显示偏好。"
                icon={<LockOutlined />}
                id="account"
                title="账号偏好"
              >
                <SettingSwitch
                  checked={settings.account.keepSignedIn}
                  description="关闭浏览器后保持当前登录状态。"
                  onChange={(checked) =>
                    setSettings((current) => ({
                      ...current,
                      account: {
                        keepSignedIn: checked,
                      },
                    }))
                  }
                  title="保持登录状态"
                />
              </SettingsSection>
            </>
          )}
        </main>
      </div>
    </AppShell>
  );
}

function SettingsSection({
  children,
  description,
  icon,
  id,
  title,
}: {
  children: React.ReactNode;
  description: string;
  icon: React.ReactNode;
  id: string;
  title: string;
}) {
  return (
    <section className="settings-section" id={`settings-${id}`}>
      <div className="settings-section-head">
        <div className="settings-section-title">
          {icon}
          <h2>{title}</h2>
        </div>
        <Text>{description}</Text>
      </div>
      <div className="settings-section-body">{children}</div>
      <Divider />
    </section>
  );
}

function SettingSwitch({
  checked,
  description,
  onChange,
  title,
}: {
  checked: boolean;
  description: string;
  onChange: (checked: boolean) => void;
  title: string;
}) {
  return (
    <div className="setting-line">
      <div>
        <strong>{title}</strong>
        <Text>{description}</Text>
      </div>
      <Switch checked={checked} onChange={onChange} />
    </div>
  );
}

function WeightInput({
  description,
  max = 100,
  min = 0,
  onChange,
  title,
  value,
}: {
  description: string;
  max?: number;
  min?: number;
  onChange: (value: number | null) => void;
  title: string;
  value: number;
}) {
  return (
    <div className="setting-line settings-weight-item">
      <div>
        <strong>{title}</strong>
        <Text>{description}</Text>
      </div>
      <InputNumber
        max={max}
        min={min}
        precision={2}
        step={0.1}
        value={value}
        onChange={onChange}
      />
    </div>
  );
}

function mergeSettings(payload?: Partial<SettingsPayload>): SettingsState {
  const models = payload?.ai?.models?.length
    ? payload.ai.models.map((row, index) => ({
        key: `model-${index}-${row.name || row.model || "item"}`,
        name: row.name ?? "",
        model: row.model ?? "",
        baseUrl: row.baseUrl ?? "",
        apiKey: row.apiKey ?? "",
      }))
    : defaultSettings.ai.models.map((row, index) => ({
        ...row,
        key: row.key || `model-default-${index}`,
      }));

  return {
    dataSource: {
      canghaiApiKey: payload?.dataSource?.canghaiApiKey ?? defaultSettings.dataSource.canghaiApiKey,
      canghaiTokenCheckEnabled:
        payload?.dataSource?.canghaiTokenCheckEnabled ??
        defaultSettings.dataSource.canghaiTokenCheckEnabled,
    },
    ai: {
      models,
    },
    notifications: {
      dataSync: payload?.notifications?.dataSync ?? defaultSettings.notifications.dataSync,
      agentGoal: payload?.notifications?.agentGoal ?? defaultSettings.notifications.agentGoal,
      backtest: payload?.notifications?.backtest ?? defaultSettings.notifications.backtest,
    },
    scoring: {
      performanceScoreWeights: {
        annualReturn: payload?.scoring?.performanceScoreWeights?.annualReturn ?? defaultSettings.scoring.performanceScoreWeights.annualReturn,
        sharpe: payload?.scoring?.performanceScoreWeights?.sharpe ?? defaultSettings.scoring.performanceScoreWeights.sharpe,
        maxDrawdown: payload?.scoring?.performanceScoreWeights?.maxDrawdown ?? defaultSettings.scoring.performanceScoreWeights.maxDrawdown,
      },
    },
    account: {
      keepSignedIn: payload?.account?.keepSignedIn ?? defaultSettings.account.keepSignedIn,
    },
  };
}

function normalizeWeightInput(
  key: keyof SettingsPayload["scoring"]["performanceScoreWeights"],
  value: number | null,
) {
  const number = Number(value ?? 0);
  if (key === "sharpe") {
    return Math.min(10, Math.max(1, number));
  }
  return Math.max(0, number);
}

function serializeSettings(settings: SettingsPayload) {
  return {
    dataSource: {
      canghaiApiKey: settings.dataSource.canghaiApiKey,
      canghaiTokenCheckEnabled: settings.dataSource.canghaiTokenCheckEnabled,
    },
    ai: {
      models: settings.ai.models.map(({ name, model, baseUrl, apiKey }) => ({
        name,
        model,
        baseUrl,
        apiKey,
      })),
    },
    notifications: settings.notifications,
    scoring: settings.scoring,
    account: settings.account,
  };
}

function tokenStatusText(value?: string) {
  if (value === "valid") return "有效";
  if (value === "invalid") return "无效";
  if (value === "expired") return "已过期";
  if (value === "error") return "异常";
  return "未检测";
}

function tokenStatusColor(value?: string) {
  if (value === "valid") return "success";
  if (value === "invalid" || value === "expired") return "error";
  if (value === "error") return "warning";
  return "default";
}

function formatLatency(value?: number | null) {
  return value == null ? "-" : `${value}ms`;
}

function formatDateTime(value?: string | null) {
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
