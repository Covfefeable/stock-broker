"use client";

import { useEffect, useState } from "react";
import { AppLoader } from "@/components/app-loader";

const MIN_VISIBLE_MS = 720;
const FADE_MS = 320;

export function AppSplash({ children }: { children: React.ReactNode }) {
  const [visible, setVisible] = useState(true);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    const start = performance.now();
    const hide = () => {
      const elapsed = performance.now() - start;
      const delay = Math.max(MIN_VISIBLE_MS - elapsed, 120);

      window.setTimeout(() => {
        setLeaving(true);
        window.setTimeout(() => {
          setVisible(false);
          document.getElementById("initial-splash")?.classList.add("initial-splash-hidden");
        }, FADE_MS);
      }, delay);
    };

    if (document.readyState === "complete") {
      hide();
      return;
    }

    window.addEventListener("load", hide, { once: true });

    return () => {
      window.removeEventListener("load", hide);
    };
  }, []);

  return (
    <>
      {children}
      {visible ? (
        <div className={`app-splash ${leaving ? "app-splash-leaving" : ""}`}>
          <AppLoader message="正在准备量化策略工作台" compact />
        </div>
      ) : null}
    </>
  );
}
