"use client";

import {
  BellOutlined,
  DatabaseOutlined,
  LockOutlined,
  RobotOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import {
  Button,
  Divider,
  Form,
  Input,
  Menu,
  Space,
  Switch,
  Table,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";

const { Text, Title } = Typography;

const sectionNav = [
  { key: "data-sources", icon: <DatabaseOutlined />, label: "数据源配置" },
  { key: "ai", icon: <RobotOutlined />, label: "AI 配置" },
  { key: "notice", icon: <BellOutlined />, label: "通知" },
  { key: "account", icon: <LockOutlined />, label: "账号偏好" },
];

const presetDataSources = [
  { key: "tushare", name: "Tushare", markets: "A 股行情 / 基础信息" },
  { key: "akshare", name: "AkShare", markets: "A 股 / 港股 / 指数补充" },
  { key: "polygon", name: "Polygon", markets: "美股行情" },
  { key: "hkex", name: "HKEX 文件源", markets: "港股基础数据" },
  { key: "financial", name: "财务数据源", markets: "全球财务因子" },
];

type AiModelRow = {
  key: string;
  name: string;
  model: string;
  baseUrl: string;
  apiKey: string;
};

const initialAiModelRows: AiModelRow[] = [
  {
    key: "openai",
    name: "OpenAI",
    model: "gpt-4.1",
    baseUrl: "https://api.openai.com/v1",
    apiKey: "",
  },
];

export default function SettingsPage() {
  const [aiModels, setAiModels] = useState<AiModelRow[]>(initialAiModelRows);
  const [notificationSettings, setNotificationSettings] = useState({
    dataSync: false,
    agentGoal: false,
    backtest: false,
  });

  const updateNotificationSetting = async (
    key: keyof typeof notificationSettings,
    checked: boolean,
  ) => {
    if (!checked) {
      setNotificationSettings((current) => ({ ...current, [key]: false }));
      return;
    }

    if (!("Notification" in window)) {
      setNotificationSettings((current) => ({ ...current, [key]: false }));
      return;
    }

    let permission = window.Notification.permission;
    if (permission === "default") {
      permission = await window.Notification.requestPermission();
    }

    setNotificationSettings((current) => ({
      ...current,
      [key]: permission === "granted",
    }));
  };

  const updateAiModel = (key: string, field: keyof Omit<AiModelRow, "key">, value: string) => {
    setAiModels((rows) => rows.map((row) => (row.key === key ? { ...row, [field]: value } : row)));
  };

  const aiModelColumns = useMemo<ColumnsType<AiModelRow>>(
    () => [
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
            placeholder="sk-..."
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
            disabled={aiModels.length <= 1}
            onClick={() => setAiModels((rows) => rows.filter((row) => row.key !== record.key))}
          >
            删除
          </Button>
        ),
      },
    ],
    [aiModels.length],
  );

  return (
    <AppShell>
      <section className="dashboard-heading">
        <div>
          <Title level={1}>系统设置</Title>
          <Text className="page-description">配置预设数据源密钥、通知和账号偏好。</Text>
        </div>
        <Space>
          <Button>恢复默认</Button>
          <Button type="primary" icon={<SaveOutlined />}>保存设置</Button>
        </Space>
      </section>

      <div className="settings-layout">
        <aside className="settings-nav">
          <Menu
            mode="inline"
            selectedKeys={["data-sources"]}
            items={sectionNav}
            onClick={({ key }) => {
              document.getElementById(`settings-${key}`)?.scrollIntoView({
                behavior: "smooth",
                block: "start",
              });
            }}
          />
        </aside>

        <main className="settings-content">
          <SettingsSection
            description="配置系统内置数据源的访问密钥。数据源列表由平台预设，不允许在此自定义新增。"
            icon={<DatabaseOutlined />}
            id="data-sources"
            title="数据源配置"
          >
            <Form layout="vertical">
              <div className="data-source-config-list">
                {presetDataSources.map((source) => (
                  <div className="data-source-config-item" key={source.key}>
                    <div>
                      <strong>{source.name}</strong>
                      <Text>{source.markets}</Text>
                    </div>
                    <Form.Item name={[source.key, "apiKey"]} label="API Key">
                      <Input.Password placeholder="请输入 API Key" />
                    </Form.Item>
                  </div>
                ))}
              </div>
            </Form>
          </SettingsSection>

          <SettingsSection
            description="配置一个或多个 OpenAI 兼容模型，用于策略生成、回测结果分析和 Agent 自动迭代。"
            icon={<RobotOutlined />}
            id="ai"
            title="AI 配置"
          >
            <Table
              columns={aiModelColumns}
              dataSource={aiModels}
              pagination={false}
              rowKey="key"
              scroll={{ x: 980 }}
            />
            <Button
              className="settings-table-action"
              onClick={() =>
                setAiModels((rows) => [
                  ...rows,
                  {
                    key: `model-${Date.now()}`,
                    name: "",
                    model: "",
                    baseUrl: "",
                    apiKey: "",
                  },
                ])
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
              checked={notificationSettings.dataSync}
              description="同步失败、部分成功或质量问题升级时，通过浏览器桌面通知提醒。"
              onChange={(checked) => updateNotificationSetting("dataSync", checked)}
              title="数据同步异常"
            />
            <SettingSwitch
              checked={notificationSettings.agentGoal}
              description="找到满足目标的策略时，通过浏览器桌面通知提醒。"
              onChange={(checked) => updateNotificationSetting("agentGoal", checked)}
              title="Agent 达标提醒"
            />
            <SettingSwitch
              checked={notificationSettings.backtest}
              description="耗时回测完成后，通过浏览器桌面通知提醒。"
              onChange={(checked) => updateNotificationSetting("backtest", checked)}
              title="回测完成提醒"
            />
          </SettingsSection>

          <SettingsSection
            description="控制当前账号的会话和显示偏好。"
            icon={<LockOutlined />}
            id="account"
            title="账号偏好"
          >
            <SettingSwitch checked description="关闭浏览器后保持当前登录状态。" title="保持登录状态" />
          </SettingsSection>
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
  checked?: boolean;
  description: string;
  onChange?: (checked: boolean) => void;
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
