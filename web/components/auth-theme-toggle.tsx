"use client";

import { MoonOutlined, SunOutlined } from "@ant-design/icons";
import { Button, Tooltip } from "antd";
import { useThemeMode } from "@/app/providers";

export function AuthThemeToggle() {
  const { mode, toggleMode } = useThemeMode();
  const isDark = mode === "dark";

  return (
    <Tooltip title={isDark ? "切换到白天模式" : "切换到黑夜模式"}>
      <Button
        aria-label={isDark ? "切换到白天模式" : "切换到黑夜模式"}
        className="login-theme-toggle"
        icon={isDark ? <SunOutlined /> : <MoonOutlined />}
        onClick={toggleMode}
      />
    </Tooltip>
  );
}
