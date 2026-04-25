import { Card, Progress, Space, Typography } from "antd";
import { EmptyState } from "@/components/empty-state";
import type { ExchangeCoverageRow } from "@/components/data-center/types";
import { formatInteger, formatPercent } from "@/components/data-center/utils";

const { Text } = Typography;

type Props = {
  exchangeCoverage: ExchangeCoverageRow[];
};

export function ExchangeCoverageCard({ exchangeCoverage }: Props) {
  return (
    <Card className="dashboard-card" title="交易所覆盖率">
      <Space orientation="vertical" size={16} className="full-width">
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
      </Space>
    </Card>
  );
}
