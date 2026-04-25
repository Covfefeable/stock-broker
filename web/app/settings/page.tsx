"use client";

import {
  BellOutlined,
  DatabaseOutlined,
  HolderOutlined,
  LockOutlined,
  RobotOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import {
  Button,
  Divider,
  Input,
  Menu,
  Space,
  Switch,
  Table,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { AppLoader } from "@/components/app-loader";
import { AppShell } from "@/components/app-shell";
import { getAccessToken } from "@/lib/auth";
import { apiGet, apiRequest } from "@/lib/api";

const { Text, Title } = Typography;

type SectionKey = "data-sources" | "ai" | "notice" | "account";

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
  account: {
    keepSignedIn: boolean;
  };
};

type SettingsState = Omit<SettingsPayload, "ai"> & {
  ai: {
    models: AiModelRow[];
  };
};

const defaultSettings: SettingsState = {
  dataSource: {
    canghaiApiKey: "",
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
  account: {
    keepSignedIn: true,
  },
};

const sectionNav = [
  { key: "data-sources", icon: <DatabaseOutlined />, label: "数据源配置" },
  { key: "ai", icon: <RobotOutlined />, label: "AI 配置" },
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

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const token = getAccessToken();
      const response = await apiGet<{ settings: SettingsPayload }>("/settings/me", token);
        setSettings(mergeSettings(response.settings));
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载系统设置失败");
      } finally {
        setLoading(false);
      }
    };

    void loadSettings();
  }, [messageApi]);

  const aiModelColumns = useMemo<ColumnsType<AiModelRow>>(
    () => [
      {
        title: "",
        width: 46,
        render: (_, record, index) => (
          <span className="settings-drag-handle" title="拖拽排序">
            <HolderOutlined />
            {index === 0 ? <span className="settings-default-model">默认</span> : null}
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
        width: 90,
        render: (_, record) => (
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
        ),
      },
    ],
    [settings.ai.models.length],
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
                    <div>
                      <strong>沧海数据</strong>
                      <Text>当前仅支持该预设数据源接入</Text>
                    </div>
                    <div>
                      <label className="settings-field-label">API Key</label>
                      <Input.Password
                        value={settings.dataSource.canghaiApiKey}
                        onChange={(event) =>
                          setSettings((current) => ({
                            ...current,
                            dataSource: {
                              canghaiApiKey: event.target.value,
                            },
                          }))
                        }
                        placeholder="请输入 API Key"
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
    },
    ai: {
      models,
    },
    notifications: {
      dataSync: payload?.notifications?.dataSync ?? defaultSettings.notifications.dataSync,
      agentGoal: payload?.notifications?.agentGoal ?? defaultSettings.notifications.agentGoal,
      backtest: payload?.notifications?.backtest ?? defaultSettings.notifications.backtest,
    },
    account: {
      keepSignedIn: payload?.account?.keepSignedIn ?? defaultSettings.account.keepSignedIn,
    },
  };
}

function serializeSettings(settings: SettingsPayload) {
  return {
    dataSource: {
      canghaiApiKey: settings.dataSource.canghaiApiKey,
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
    account: settings.account,
  };
}
