import { Button, Card, DatePicker, Input, Select, Table } from "antd";
import { priceColumns } from "@/components/data-center/constants";
import type { PriceRow } from "@/components/data-center/types";

const { RangePicker } = DatePicker;

type Props = {
  prices: PriceRow[];
};

export function DataBrowserCard({ prices }: Props) {
  return (
    <Card className="dashboard-card data-browser-card" title="行情数据浏览器">
      <div className="data-filter-row">
        <Input.Search placeholder="输入股票代码或名称" allowClear />
        <Select
          defaultValue="all"
          options={[
            { label: "全部市场", value: "all" },
            { label: "A 股", value: "cn" },
            { label: "港股", value: "hk" },
            { label: "美股", value: "us" },
          ]}
        />
        <Select
          defaultValue="daily"
          options={[
            { label: "日线行情", value: "daily" },
            { label: "基础信息", value: "basic" },
            { label: "财务因子", value: "financial" },
            { label: "复权因子", value: "adjust" },
          ]}
        />
        <RangePicker />
        <Button type="primary">查询</Button>
      </div>
      <Table columns={priceColumns} dataSource={prices} pagination={{ pageSize: 5 }} size="middle" scroll={{ x: 1180 }} />
    </Card>
  );
}
