import { Badge, Card, Progress, Typography } from "antd";
import { EmptyState } from "@/components/empty-state";
import type { DataSourceStatusItem, ExchangeCoverageRow } from "@/components/data-center/types";
import { formatInteger, formatPercent } from "@/components/data-center/utils";

const { Text } = Typography;

type Props = {
  item: DataSourceStatusItem | null;
  exchangeCoverage: ExchangeCoverageRow[];
  loading: boolean;
};

function getStatusMeta(status: DataSourceStatusItem["status"] | undefined) {
  if (status === "normal") {
    return { badge: "success" as const, text: "正常" };
  }
  if (status === "abnormal") {
    return { badge: "error" as const, text: "异常" };
  }
  if (status === "checking") {
    return { badge: "processing" as const, text: "检测中" };
  }
  return { badge: "default" as const, text: "未知" };
}

export function SourceStatusCard({ item, exchangeCoverage, loading }: Props) {
  const statusMeta = getStatusMeta(item?.status);

  return (
    <Card className="dashboard-card source-status-card" title="数据源状态" loading={loading}>
      <div className="source-status-panel">
        <div className="source-status-head">
          <div className="source-status-copy">
            <strong>{item?.sourceName ?? "沧海数据"}</strong>
            <Text>{item?.message || "等待下一次检测结果"}</Text>
          </div>
          <Badge status={statusMeta.badge} text={statusMeta.text} />
        </div>

        <div className="source-status-metrics">
          <div className="source-status-metric">
            <span>延迟</span>
            <strong>{item?.latencyMs != null ? `${item.latencyMs} ms` : "-"}</strong>
          </div>
          <div className="source-status-metric">
            <span>检测时间</span>
            <strong>{formatClockTime(item?.checkedAt ?? null)}</strong>
          </div>
          <div className="source-status-metric">
            <span>HTTP 状态</span>
            <strong>{item?.httpStatus ?? "-"}</strong>
          </div>
        </div>

        <div className="source-status-coverage">
          <Text className="source-status-coverage-title">交易所覆盖率</Text>
          {exchangeCoverage.length > 0 ? (
            exchangeCoverage.map((item) => (
              <div className="quality-progress" key={item.exchangeCode}>
                <div>
                  <Text>
                    {item.exchangeName} ({item.exchangeCode})
                  </Text>
                  <strong>{formatPercent(item.percent)}%</strong>
                </div>
                <Progress percent={item.percent} showInfo={false} status={item.percent < 96 ? "exception" : "success"} />
                <Text type="secondary">
                  {formatInteger(item.actual)} / {formatInteger(item.expected)} 只股票
                </Text>
              </div>
            ))
          ) : (
            <EmptyState title="暂无交易所覆盖率数据" description="同步交易所和股票清单后会显示覆盖率。" compact />
          )}
        </div>
      </div>
    </Card>
  );
}

function formatClockTime(value: string | null): string {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }

  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}
