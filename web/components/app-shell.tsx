"use client";

import {
  AppstoreOutlined,
  BarChartOutlined,
  BellOutlined,
  BulbOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  DatabaseOutlined,
  FundProjectionScreenOutlined,
  MoonOutlined,
  RobotOutlined,
  SettingOutlined,
  SunOutlined,
} from "@ant-design/icons";
import { Avatar, Button, Layout, Menu, Space, Switch, Typography } from "antd";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useThemeMode } from "@/app/providers";
import { AuthGuard } from "@/components/auth-guard";
import { TaskCenter } from "@/components/task-center";
import { clearAccessToken, type AuthUser } from "@/lib/auth";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const navItems = [
  { key: "/", icon: <AppstoreOutlined />, label: <Link href="/">总览</Link> },
  { key: "/data-center", icon: <DatabaseOutlined />, label: <Link href="/data-center">数据中心</Link> },
  { key: "/strategy-builder", icon: <BulbOutlined />, label: <Link href="/strategy-builder">策略搭建</Link> },
  { key: "/backtest-lab", icon: <BarChartOutlined />, label: <Link href="/backtest-lab">回测实验室</Link> },
  { key: "/agent-tasks", icon: <RobotOutlined />, label: <Link href="/agent-tasks">AI Agent 任务</Link> },
  { key: "/settings", icon: <SettingOutlined />, label: <Link href="/settings">系统设置</Link> },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { mode, toggleMode } = useThemeMode();
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const isDark = mode === "dark";
  const selectedKey = navItems.some((item) => item.key === pathname) ? pathname : "/";

  return (
    <AuthGuard>
      {(user) => (
        <Layout className={`app-shell app-shell-${mode}`}>
          <Sider className="sidebar" width={248} collapsed={collapsed} collapsedWidth={80} trigger={null}>
            <div className="brand-block">
              <span className="brand-mark">
                <FundProjectionScreenOutlined />
              </span>
              <div className="brand-copy">
                <strong>Genesis</strong>
                <small>AI 量化策略平台</small>
              </div>
            </div>
            <Menu
              className="side-menu"
              items={navItems}
              mode="inline"
              selectedKeys={[selectedKey]}
            />
          </Sider>

          <Layout className="workspace">
            <Header className="topbar">
              <div className="topbar-left">
                <Button
                  icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                  onClick={() => setCollapsed((current) => !current)}
                  shape="circle"
                  title={collapsed ? "展开侧边栏" : "收起侧边栏"}
                  type="text"
                />
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
                <span className="topbar-user-name">{user.username}</span>
                <Avatar className="avatar">{getInitial(user)}</Avatar>
                <Button
                  onClick={() => {
                    clearAccessToken();
                    router.replace("/login");
                  }}
                  type="text"
                >
                  退出
                </Button>
              </Space>
            </Header>
            <Content className="content-area">{children}</Content>
            <TaskCenter />
          </Layout>
        </Layout>
      )}
    </AuthGuard>
  );
}

function getInitial(user: AuthUser) {
  return user.username.trim().slice(0, 1).toUpperCase() || "U";
}
