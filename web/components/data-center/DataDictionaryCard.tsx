import { Card, Col, Row, Statistic, Typography } from "antd";

const { Text } = Typography;

type Props = {
  countryCount: number;
  exchangeCount: number;
  stocksCount: number;
  syncedStocksCount: number;
};

export function DataDictionaryCard({
  countryCount,
  exchangeCount,
  stocksCount,
  syncedStocksCount,
}: Props) {
  return (
    <Card className="dashboard-card" title="基础字典概览">
      <Row gutter={[16, 16]}>
        <Col xs={12} md={12}>
          <Statistic title="国家/地区" value={countryCount} />
        </Col>
        <Col xs={12} md={12}>
          <Statistic title="交易所" value={exchangeCount} />
        </Col>
        <Col xs={12} md={12}>
          <Statistic title="股票标的" value={stocksCount} />
        </Col>
        <Col xs={12} md={12}>
          <Statistic title="已同步股票" value={syncedStocksCount} />
        </Col>
      </Row>
      <Text className="metric-hint">用于快速判断基础字典与行情同步覆盖的准备情况。</Text>
    </Card>
  );
}
