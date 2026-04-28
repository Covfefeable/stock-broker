import type { Metadata } from "next";
import { AppSplash } from "@/components/app-splash";
import { AppProviders } from "./providers";
import "./styles/base.css";
import "./styles/shell.css";
import "./styles/data-center.css";
import "./styles/settings.css";
import "./styles/backtest.css";
import "./styles/auth.css";
import "./styles/strategy.css";
import "./styles/agent.css";

export const metadata: Metadata = {
  title: "Genesis 量化策略平台",
  description: "股票策略搭建、回测与 AI Agent 自动探索平台",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body data-theme="dark" suppressHydrationWarning>
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{var t=localStorage.getItem('genesis-theme-mode');document.body.dataset.theme=(t==='light'||t==='dark')?t:'dark'}catch(e){document.body.dataset.theme='dark'}",
          }}
        />
        <div
          id="initial-splash"
          style={{
            alignItems: "center",
            background: "var(--app-bg, #0f172a)",
            color: "var(--text-main, #e5e7eb)",
            display: "flex",
            fontFamily: "system-ui, sans-serif",
            inset: 0,
            justifyContent: "center",
            position: "fixed",
            zIndex: 9998,
          }}
        >
          <div style={{ opacity: 0.86, textAlign: "center" }}>
            <div style={{ color: "#6366f1", fontSize: 28, fontWeight: 700, marginBottom: 8 }}>Genesis</div>
            <div style={{ color: "var(--text-muted, #8d99ae)", fontSize: 13 }}>正在加载工作台</div>
          </div>
        </div>
        <AppProviders>
          <AppSplash>{children}</AppSplash>
        </AppProviders>
      </body>
    </html>
  );
}
