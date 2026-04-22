"use client";

import {
  ApiOutlined,
  AppstoreOutlined,
  BarChartOutlined,
  BellOutlined,
  BulbOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  HistoryOutlined,
  MoonOutlined,
  RobotOutlined,
  SettingOutlined,
  SunOutlined,
} from "@ant-design/icons";
import { Avatar, Button, Layout, Menu, Space, Switch, Typography } from "antd";
import { useThemeMode } from "@/app/providers";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const navItems = [
  { key: "overview", icon: <AppstoreOutlined />, label: "总览" },
  { key: "data", icon: <DatabaseOutlined />, label: "数据中心" },
  { key: "sources", icon: <ApiOutlined />, label: "数据源管理" },
  { key: "builder", icon: <BulbOutlined />, label: "策略搭建" },
  { key: "backtest", icon: <BarChartOutlined />, label: "回测实验室" },
  { key: "agent", icon: <RobotOutlined />, label: "AI Agent 任务" },
  { key: "library", icon: <ExperimentOutlined />, label: "策略库" },
  { key: "history", icon: <HistoryOutlined />, label: "实验历史" },
  { key: "settings", icon: <SettingOutlined />, label: "系统设置" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { mode, toggleMode } = useThemeMode();
  const isDark = mode === "dark";

  return (
    <Layout className={`app-shell app-shell-${mode}`}>
      <Sider className="sidebar" width={248}>
        <div className="brand-block">
          <span className="brand-mark">G</span>
          <div>
            <strong>Genesis</strong>
            <small>AI 量化策略平台</small>
          </div>
        </div>
        <Menu
          className="side-menu"
          items={navItems}
          mode="inline"
          selectedKeys={["overview"]}
        />
      </Sider>

      <Layout className="workspace">
        <Header className="topbar">
          <div>
            <Text className="topbar-label">当前工作区</Text>
            <strong>默认策略空间</strong>
          </div>
          <Space size={18} className="topbar-meta">
            <Switch
              checked={isDark}
              checkedChildren={<MoonOutlined />}
              unCheckedChildren={<SunOutlined />}
              onChange={toggleMode}
              title="切换明暗模式"
            />
            <Button icon={<BellOutlined />} shape="circle" type="text" />
            <Avatar className="avatar">研</Avatar>
          </Space>
        </Header>
        <Content className="content-area">{children}</Content>
      </Layout>
    </Layout>
  );
}
