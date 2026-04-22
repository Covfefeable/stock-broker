"use client";

import Lottie from "lottie-react";
import { useEffect, useState } from "react";
import loadingAnimation from "@/lib/lottie/loading.json";

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
          <div className="app-splash-panel">
            <Lottie
              animationData={loadingAnimation}
              autoplay
              loop={true}
              className="app-splash-lottie"
            />
            <div className="app-splash-copy">
              <strong>Genesis</strong>
              <span>正在准备量化策略工作台</span>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
