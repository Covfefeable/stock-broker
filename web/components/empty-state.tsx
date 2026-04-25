"use client";

import type { ReactNode } from "react";
import Lottie from "lottie-react";
import findDataAnimation from "@/lib/lottie/find-data.json";

type EmptyStateProps = {
  title?: ReactNode;
  description?: ReactNode;
  className?: string;
  compact?: boolean;
};

export function EmptyState({ title = "暂无数据", description, className = "", compact = false }: EmptyStateProps) {
  return (
    <div className={`app-empty-state ${compact ? "app-empty-state-compact" : ""} ${className}`.trim()}>
      <Lottie animationData={findDataAnimation} autoplay loop className="app-empty-state-lottie" />
      <div className="app-empty-state-copy">
        <strong>{title}</strong>
        {description ? <span>{description}</span> : null}
      </div>
    </div>
  );
}
