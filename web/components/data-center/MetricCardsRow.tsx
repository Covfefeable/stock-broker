import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import { Card, Col, Row, Typography } from "antd";
import type { OverviewMetrics } from "@/components/data-center/types";
import { formatInteger } from "@/components/data-center/utils";

const { Text } = Typography;

type Props = {
  metrics: OverviewMetrics;
  loading: boolean;
};

export function MetricCardsRow({ metrics, loading }: Props) {
  const metricCards = [
    {
      title: "股票标的",
      value: formatInteger(metrics.stocksCount),
      suffix: "只",
      icon: <DatabaseOutlined />,
      className: "",
    },
    {
      title: "历史日线",
      value: formatInteger(metrics.stockDailyBarsCount),
      suffix: "条",
      icon: <ClockCircleOutlined />,
      className: "",
    },
    {
      title: "交易所数量",
      value: formatInteger(metrics.exchangeCount),
      suffix: "个",
      icon: <SafetyCertificateOutlined />,
      className: "",
    },
    {
      title: "已同步股票/指数",
      value: formatInteger(metrics.syncedAssetsCount),
      suffix: "个",
      icon: <CheckCircleOutlined />,
      className: "positive-text",
    },
  ];

  return (
    <Row gutter={[20, 20]} className="equal-height-row">
      {metricCards.map((item) => (
        <Col xs={24} md={12} xl={6} key={item.title}>
          <Card className="metric-card dashboard-card" loading={loading}>
            <div className="metric-card-head">
              <Text>{item.title}</Text>
              <span className="metric-icon">{item.icon}</span>
            </div>
            <strong className={item.className}>
              {item.value}
              {item.suffix}
            </strong>
          </Card>
        </Col>
      ))}
    </Row>
  );
}
