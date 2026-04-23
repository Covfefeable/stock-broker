import { DatePicker, Form, Modal, Radio, Select, Typography } from "antd";
import type {
  CountryOption,
  ExchangeOption,
  StockDailyCoverage,
  StockOption,
  SyncFormValues,
} from "@/components/data-center/types";
import { syncItemOptions } from "@/components/data-center/constants";

const { Text } = Typography;

type Props = {
  open: boolean;
  syncing: boolean;
  form: ReturnType<typeof Form.useForm<SyncFormValues>>[0];
  exchangeLoading: boolean;
  countryLoading: boolean;
  stockLoading: boolean;
  coverageLoading: boolean;
  exchangeOptions: ExchangeOption[];
  countryOptions: CountryOption[];
  stockOptions: StockOption[];
  dailyCoverage: StockDailyCoverage;
  onSubmit: () => void;
  onCancel: () => void;
  onSyncItemChange: (value: SyncFormValues["syncItem"]) => void;
  onExchangeChange: (value: string) => void;
  onTickerChange: (value: string, exchangeCode: string) => void;
};

export function SyncDataModal({
  open,
  syncing,
  form,
  exchangeLoading,
  countryLoading,
  stockLoading,
  coverageLoading,
  exchangeOptions,
  countryOptions,
  stockOptions,
  dailyCoverage,
  onSubmit,
  onCancel,
  onSyncItemChange,
  onExchangeChange,
  onTickerChange,
}: Props) {
  return (
    <Modal
      title="同步数据"
      open={open}
      okText="开始同步"
      cancelText="取消"
      confirmLoading={syncing}
      onOk={onSubmit}
      onCancel={onCancel}
    >
      <Form form={form} layout="vertical" initialValues={{ syncItem: "country_list", dateMode: "auto_fill" }}>
        <Form.Item label="同步项" name="syncItem" rules={[{ required: true, message: "请选择同步项" }]}>
          <Select options={syncItemOptions} onChange={onSyncItemChange} />
        </Form.Item>

        <Form.Item noStyle shouldUpdate={(prev, next) => prev.syncItem !== next.syncItem}>
          {({ getFieldValue }) =>
            getFieldValue("syncItem") === "stock_list" ? (
              <Form.Item label="交易所" name="exchangeCode" rules={[{ required: true, message: "请选择交易所" }]}>
                <Select showSearch loading={exchangeLoading} options={exchangeOptions} placeholder="请选择交易所" optionFilterProp="label" />
              </Form.Item>
            ) : null
          }
        </Form.Item>

        <Form.Item noStyle shouldUpdate={(prev, next) => prev.syncItem !== next.syncItem}>
          {({ getFieldValue }) =>
            getFieldValue("syncItem") === "index_list" ? (
              <Form.Item label="国家/地区" name="countryCode" rules={[{ required: true, message: "请选择国家/地区" }]}>
                <Select showSearch loading={countryLoading} options={countryOptions} placeholder="请选择国家/地区" optionFilterProp="label" />
              </Form.Item>
            ) : null
          }
        </Form.Item>

        <Form.Item noStyle shouldUpdate={(prev, next) => prev.syncItem !== next.syncItem || prev.exchangeCode !== next.exchangeCode}>
          {({ getFieldValue }) =>
            getFieldValue("syncItem") === "stock_daily_history" ? (
              <>
                <Form.Item label="交易所" name="exchangeCode" rules={[{ required: true, message: "请选择交易所" }]}>
                  <Select
                    showSearch
                    loading={exchangeLoading}
                    options={exchangeOptions}
                    placeholder="请选择交易所"
                    optionFilterProp="label"
                    onChange={onExchangeChange}
                  />
                </Form.Item>

                <Form.Item label="股票" name="ticker" rules={[{ required: true, message: "请选择股票" }]}>
                  <Select
                    showSearch
                    loading={stockLoading}
                    options={stockOptions}
                    placeholder={getFieldValue("exchangeCode") ? "请选择股票" : "请先选择交易所"}
                    optionFilterProp="label"
                    onChange={(value) => onTickerChange(value, getFieldValue("exchangeCode"))}
                  />
                </Form.Item>

                <Form.Item label="日期模式" name="dateMode">
                  <Radio.Group
                    options={[
                      { label: "自动补全数据", value: "auto_fill" },
                      { label: "自选日期", value: "custom" },
                    ]}
                  />
                </Form.Item>

                <Text className="metric-hint">
                  {coverageLoading
                    ? "正在加载该股票的已同步日期..."
                    : dailyCoverage.latestDate
                      ? `已同步 ${dailyCoverage.count} 个交易日，最新日期为 ${dailyCoverage.latestDate}（北京时间）。`
                      : "该股票尚无历史日线数据，自动补全将执行全量同步。"}
                </Text>

                <Form.Item
                  noStyle
                  shouldUpdate={(prev, next) =>
                    prev.dateMode !== next.dateMode ||
                    prev.exchangeCode !== next.exchangeCode ||
                    prev.ticker !== next.ticker
                  }
                >
                  {({ getFieldValue }) =>
                    getFieldValue("dateMode") === "custom" ? (
                      <Form.Item label="日期范围" name="dateRange">
                        <DatePicker.RangePicker
                          className="full-width"
                          disabledDate={(current) => {
                            if (!current) return false;
                            return dailyCoverage.existingDates.includes(current.format("YYYY-MM-DD"));
                          }}
                        />
                      </Form.Item>
                    ) : null
                  }
                </Form.Item>
              </>
            ) : null
          }
        </Form.Item>
      </Form>
    </Modal>
  );
}
