import { Card, Table } from "antd";
import { issueColumns } from "@/components/data-center/constants";
import type { IssueRow } from "@/components/data-center/types";

type Props = {
  issues: IssueRow[];
};

export function DataQualityIssuesCard({ issues }: Props) {
  return (
    <Card className="dashboard-card" title="数据质量问题">
      <Table columns={issueColumns} dataSource={issues} pagination={false} size="small" />
    </Card>
  );
}
