"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";

type ThemeMode = "dark" | "light";

type ThemeModeContextValue = {
  mode: ThemeMode;
  toggleMode: () => void;
};

const ThemeModeContext = createContext<ThemeModeContextValue | null>(null);
const THEME_STORAGE_KEY = "genesis-theme-mode";

export function useThemeMode() {
  const value = useContext(ThemeModeContext);

  if (!value) {
    throw new Error("useThemeMode must be used inside AppProviders");
  }

  return value;
}

export function AppProviders({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>("dark");
  const [themeReady, setThemeReady] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    const nextMode = stored === "light" || stored === "dark" ? stored : "dark";
    setMode(nextMode);
    document.body.dataset.theme = nextMode;
    setThemeReady(true);
  }, []);

  useEffect(() => {
    if (!themeReady) {
      return;
    }
    window.localStorage.setItem(THEME_STORAGE_KEY, mode);
    document.body.dataset.theme = mode;
  }, [mode, themeReady]);

  const contextValue = useMemo(
    () => ({
      mode,
      toggleMode: () => setMode((current) => (current === "dark" ? "light" : "dark")),
    }),
    [mode],
  );

  const isDark = mode === "dark";

  return (
    <ThemeModeContext.Provider value={contextValue}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
          token: {
            colorPrimary: "#6366F1",
            colorSuccess: "#10B981",
            colorWarning: "#F59E0B",
            colorError: "#EF4444",
            borderRadius: 8,
            fontFamily: '"DM Sans", "Microsoft YaHei", system-ui, sans-serif',
          },
          components: {
            Button: {
              borderRadius: 6,
              controlHeight: 34,
              controlHeightSM: 28,
            },
            Card: {
              borderRadiusLG: 8,
              paddingLG: 20,
            },
            Layout: {
              bodyBg: isDark ? "#0F172A" : "#FAFAFA",
              headerBg: isDark ? "rgba(15, 23, 42, 0.86)" : "rgba(250, 250, 250, 0.86)",
              siderBg: isDark ? "#111827" : "#FFFFFF",
            },
            Menu: {
              itemBorderRadius: 6,
            },
          },
        }}
      >
        <div className={`theme-root ${isDark ? "theme-dark" : "theme-light"}`}>{children}</div>
      </ConfigProvider>
    </ThemeModeContext.Provider>
  );
}
