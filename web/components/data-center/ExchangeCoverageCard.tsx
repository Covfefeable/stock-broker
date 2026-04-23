import { Card, Progress, Space, Typography } from "antd";
import type { ExchangeCoverageRow } from "@/components/data-center/types";
import { formatInteger, formatPercent } from "@/components/data-center/utils";

const { Text } = Typography;

type Props = {
  latestTradeDate: string | null;
  exchangeCoverage: ExchangeCoverageRow[];
};

export function ExchangeCoverageCard({ latestTradeDate, exchangeCoverage }: Props) {
  return (
    <Card
      className="dashboard-card"
      title="交易所覆盖率"
      extra={latestTradeDate ? <Text type="secondary">最新日线日期：{latestTradeDate}</Text> : undefined}
    >
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
          <Text type="secondary">暂无可用于计算覆盖率的交易所数据。</Text>
        )}
      </Space>
    </Card>
  );
}
