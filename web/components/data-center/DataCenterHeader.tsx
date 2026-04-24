import { SyncOutlined } from "@ant-design/icons";
import { Button, Space, Tooltip, Typography } from "antd";

const { Text, Title } = Typography;

type Props = {
  batchSyncing: boolean;
  onBatchSync: () => void;
  onOpenSyncModal: () => void;
};

export function DataCenterHeader({ batchSyncing, onBatchSync, onOpenSyncModal }: Props) {
  return (
    <section className="dashboard-heading">
      <div>
        <Title level={1}>数据中心</Title>
        <Text className="page-description">
          管理 A 股、港股、美股等多市场行情、基础信息与财务因子数据，监控同步状态和数据覆盖情况。
        </Text>
      </div>
      <Space>
        <Tooltip title="自动同步所有已添加股票和指数自上一个同步日期以来的所有日线数据">
          <Button loading={batchSyncing} onClick={onBatchSync}>
            批量同步股票/指数
          </Button>
        </Tooltip>
        <Button type="primary" icon={<SyncOutlined />} onClick={onOpenSyncModal}>
          同步数据
        </Button>
      </Space>
    </section>
  );
}
