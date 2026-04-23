"use client";

import Lottie from "lottie-react";
import loadingAnimation from "@/lib/lottie/loading.json";

type AppLoaderProps = {
  message?: string;
  fullscreen?: boolean;
  compact?: boolean;
};

export function AppLoader({
  message = "正在加载工作台",
  fullscreen = false,
  compact = false,
}: AppLoaderProps) {
  return (
    <div className={fullscreen ? "app-loader app-loader-fullscreen" : "app-loader"}>
      <div className={`app-loader-panel ${compact ? "app-loader-panel-compact" : ""}`}>
        <Lottie animationData={loadingAnimation} autoplay loop className="app-loader-lottie" />
        <div className="app-loader-copy">
          <strong>Genesis</strong>
          <span>{message}</span>
        </div>
      </div>
    </div>
  );
}
