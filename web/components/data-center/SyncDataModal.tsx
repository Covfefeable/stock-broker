import { DatePicker, Form, Modal, Radio, Select, Typography } from "antd";
import type {
  CountryOption,
  EtfDailyCoverage,
  EtfOption,
  ExchangeOption,
  IndexDailyCoverage,
  IndexOption,
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
  etfOptions: EtfOption[];
  indexOptions: IndexOption[];
  stockDailyCoverage: StockDailyCoverage;
  etfDailyCoverage: EtfDailyCoverage;
  indexDailyCoverage: IndexDailyCoverage;
  onSubmit: () => void;
  onCancel: () => void;
  onSyncItemChange: (value: SyncFormValues["syncItem"]) => void;
  onExchangeChange: (value: string) => void;
  onCountryChange: (value: string) => void;
  onStockTickerChange: (value: string, exchangeCode: string) => void;
  onEtfTickerChange: (value: string, exchangeCode: string) => void;
  onIndexTickerChange: (value: string, countryCode: string) => void;
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
  etfOptions,
  indexOptions,
  stockDailyCoverage,
  etfDailyCoverage,
  indexDailyCoverage,
  onSubmit,
  onCancel,
  onSyncItemChange,
  onExchangeChange,
  onCountryChange,
  onStockTickerChange,
  onEtfTickerChange,
  onIndexTickerChange,
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
            ["stock_list", "etf_list", "trading_calendar"].includes(getFieldValue("syncItem")) ? (
              <Form.Item label="交易所" name="exchangeCode" rules={[{ required: true, message: "请选择交易所" }]}>
                <Select
                  showSearch
                  loading={exchangeLoading}
                  options={exchangeOptions}
                  placeholder="请选择交易所"
                  optionFilterProp="label"
                />
              </Form.Item>
            ) : null
          }
        </Form.Item>

        <Form.Item noStyle shouldUpdate={(prev, next) => prev.syncItem !== next.syncItem}>
          {({ getFieldValue }) =>
            getFieldValue("syncItem") === "index_list" || getFieldValue("syncItem") === "index_daily_history" ? (
              <Form.Item label="国家/地区" name="countryCode" rules={[{ required: true, message: "请选择国家/地区" }]}>
                <Select
                  showSearch
                  loading={countryLoading}
                  options={countryOptions}
                  placeholder="请选择国家/地区"
                  optionFilterProp="label"
                  onChange={getFieldValue("syncItem") === "index_daily_history" ? onCountryChange : undefined}
                />
              </Form.Item>
            ) : null
          }
        </Form.Item>

        <Form.Item noStyle shouldUpdate={(prev, next) => prev.syncItem !== next.syncItem || prev.exchangeCode !== next.exchangeCode}>
          {({ getFieldValue }) =>
            getFieldValue("syncItem") === "stock_daily_history" || getFieldValue("syncItem") === "etf_daily_history" ? (
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

                <Form.Item
                  label={getFieldValue("syncItem") === "etf_daily_history" ? "ETF" : "股票"}
                  name="ticker"
                  rules={[{ required: true, message: getFieldValue("syncItem") === "etf_daily_history" ? "请选择 ETF" : "请选择股票" }]}
                >
                  <Select
                    showSearch
                    loading={stockLoading}
                    options={getFieldValue("syncItem") === "etf_daily_history" ? etfOptions : stockOptions}
                    placeholder={
                      getFieldValue("exchangeCode")
                        ? getFieldValue("syncItem") === "etf_daily_history"
                          ? "请选择 ETF"
                          : "请选择股票"
                        : "请先选择交易所"
                    }
                    optionFilterProp="label"
                    onChange={(value) =>
                      getFieldValue("syncItem") === "etf_daily_history"
                        ? onEtfTickerChange(value, getFieldValue("exchangeCode"))
                        : onStockTickerChange(value, getFieldValue("exchangeCode"))
                    }
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
                    ? `正在加载该${getFieldValue("syncItem") === "etf_daily_history" ? "ETF" : "股票"}的已同步日期...`
                    : (getFieldValue("syncItem") === "etf_daily_history" ? etfDailyCoverage : stockDailyCoverage).latestDate
                      ? `已同步 ${(getFieldValue("syncItem") === "etf_daily_history" ? etfDailyCoverage : stockDailyCoverage).count} 个交易日，最新日期为 ${(getFieldValue("syncItem") === "etf_daily_history" ? etfDailyCoverage : stockDailyCoverage).latestDate}（北京时间）。`
                      : `该${getFieldValue("syncItem") === "etf_daily_history" ? "ETF" : "股票"}尚无历史日线数据，自动补全将执行全量同步。`}
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
                            const coverage = getFieldValue("syncItem") === "etf_daily_history" ? etfDailyCoverage : stockDailyCoverage;
                            return coverage.existingDates.includes(current.format("YYYY-MM-DD"));
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

        <Form.Item noStyle shouldUpdate={(prev, next) => prev.syncItem !== next.syncItem || prev.countryCode !== next.countryCode}>
          {({ getFieldValue }) =>
            getFieldValue("syncItem") === "index_daily_history" ? (
              <>
                <Form.Item label="指数" name="ticker" rules={[{ required: true, message: "请选择指数" }]}>
                  <Select
                    showSearch
                    loading={stockLoading}
                    options={indexOptions}
                    placeholder={getFieldValue("countryCode") ? "请选择指数" : "请先选择国家/地区"}
                    optionFilterProp="label"
                    onChange={(value) => onIndexTickerChange(value, getFieldValue("countryCode"))}
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
                    ? "正在加载该指数的已同步日期..."
                    : indexDailyCoverage.latestDate
                      ? `已同步 ${indexDailyCoverage.count} 个交易日，最新日期为 ${indexDailyCoverage.latestDate}（北京时间）。`
                      : "该指数尚无历史日线数据，自动补全将执行全量同步。"}
                </Text>

                <Form.Item
                  noStyle
                  shouldUpdate={(prev, next) =>
                    prev.dateMode !== next.dateMode ||
                    prev.countryCode !== next.countryCode ||
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
                            return indexDailyCoverage.existingDates.includes(current.format("YYYY-MM-DD"));
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
