import { Badge, Card, Typography } from "antd";

const { Text } = Typography;

export function SourceStatusCard() {
  return (
    <Card className="dashboard-card" title="数据源状态">
      <div className="source-list">
        <div className="source-item source-item-simple">
          <div>
            <strong>沧海数据</strong>
          </div>
          <div className="source-meta">
            <Badge status="success" text="正常" />
            <Text>今日调用次数由上游接口统计</Text>
          </div>
        </div>
      </div>
    </Card>
  );
}
