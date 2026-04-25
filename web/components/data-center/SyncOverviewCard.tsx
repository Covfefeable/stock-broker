import { Badge, Button, Card, Typography } from "antd";
import { EmptyState } from "@/components/empty-state";
import type { TimelineLogRow } from "@/components/data-center/types";

const { Text } = Typography;

type Props = {
  logLoading: boolean;
  loadingMore: boolean;
  hasMore: boolean;
  eventLogs: TimelineLogRow[];
  onRefresh: () => void;
  onLoadMore: () => void;
};

export function SyncOverviewCard({ logLoading, loadingMore, hasMore, eventLogs, onRefresh, onLoadMore }: Props) {
  return (
    <Card
      className="dashboard-card data-sync-panel"
      title="数据同步概览"
      extra={
        <Button type="link" onClick={onRefresh}>
          刷新日志
        </Button>
      }
    >
      <div
        className="sync-timeline sync-timeline-scroll"
        onScroll={(event) => {
          const node = event.currentTarget;
          const nearBottom = node.scrollTop + node.clientHeight >= node.scrollHeight - 40;
          if (nearBottom && hasMore && !loadingMore && !logLoading) {
            onLoadMore();
          }
        }}
      >
        {logLoading ? (
          <div className="sync-task">
            <Badge status="processing" />
            <div>
              <strong>正在加载日志</strong>
              <Text>请稍候...</Text>
            </div>
          </div>
        ) : eventLogs.length > 0 ? (
          eventLogs.map((log) => (
            <div className="sync-task" key={log.key}>
              <Badge
                status={
                  log.status === "成功"
                    ? "success"
                    : log.status === "运行中"
                      ? "processing"
                      : log.status === "部分成功"
                        ? "warning"
                        : "error"
                }
              />
              <div>
                <strong>{log.task}</strong>
                <Text>
                  {log.time} · {log.dataset} · {log.message}
                </Text>
              </div>
            </div>
          ))
        ) : (
          <EmptyState title="暂无同步日志" description="完成首次同步后，这里会显示最新执行记录。" compact />
        )}
        {!logLoading && loadingMore ? (
          <div className="sync-task sync-task-loading-more">
            <Badge status="processing" />
            <div>
              <strong>正在加载更多日志</strong>
              <Text>请稍候...</Text>
            </div>
          </div>
        ) : null}
      </div>
    </Card>
  );
}
