"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Col, Form, Row, message } from "antd";
import { AppShell } from "@/components/app-shell";
import { DataBrowserCard } from "@/components/data-center/DataBrowserCard";
import { DataCenterHeader } from "@/components/data-center/DataCenterHeader";
import { ExchangeCoverageCard } from "@/components/data-center/ExchangeCoverageCard";
import { MetricCardsRow } from "@/components/data-center/MetricCardsRow";
import { SourceStatusCard } from "@/components/data-center/SourceStatusCard";
import { SyncDataModal } from "@/components/data-center/SyncDataModal";
import { SyncOverviewCard } from "@/components/data-center/SyncOverviewCard";
import { TradingCalendarCard } from "@/components/data-center/TradingCalendarCard";
import type {
  CountryOption,
  DataSourceStatusItem,
  EventLogItem,
  ExchangeOption,
  IndexDailyCoverage,
  IndexOption,
  OverviewMetrics,
  StockDailyCoverage,
  StockOption,
  SyncEnqueueResponse,
  SyncFormValues,
  TimelineLogRow,
} from "@/components/data-center/types";
import { defaultMetrics, mapEventLogRow } from "@/components/data-center/utils";
import { getAccessToken } from "@/lib/auth";
import { apiGet, apiPost } from "@/lib/api";

const emptyStockCoverage: StockDailyCoverage = { existingDates: [], latestDate: null, count: 0 };
const emptyIndexCoverage: IndexDailyCoverage = { existingDates: [], latestDate: null, count: 0 };

export default function DataCenterPage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm<SyncFormValues>();

  const [modalOpen, setModalOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [batchSyncing, setBatchSyncing] = useState(false);
  const [logLoading, setLogLoading] = useState(true);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [sourceStatusLoading, setSourceStatusLoading] = useState(true);
  const [exchangeLoading, setExchangeLoading] = useState(false);
  const [countryLoading, setCountryLoading] = useState(false);
  const [stockLoading, setStockLoading] = useState(false);
  const [coverageLoading, setCoverageLoading] = useState(false);

  const [metrics, setMetrics] = useState<OverviewMetrics>(defaultMetrics);
  const [sourceStatus, setSourceStatus] = useState<DataSourceStatusItem | null>(null);
  const [exchangeOptions, setExchangeOptions] = useState<ExchangeOption[]>([]);
  const [countryOptions, setCountryOptions] = useState<CountryOption[]>([]);
  const [stockOptions, setStockOptions] = useState<StockOption[]>([]);
  const [indexOptions, setIndexOptions] = useState<IndexOption[]>([]);
  const [stockDailyCoverage, setStockDailyCoverage] = useState<StockDailyCoverage>(emptyStockCoverage);
  const [indexDailyCoverage, setIndexDailyCoverage] = useState<IndexDailyCoverage>(emptyIndexCoverage);
  const [eventLogs, setEventLogs] = useState<TimelineLogRow[]>([]);

  const exchangeCoverage = useMemo(
    () => [...metrics.exchangeCoverage].sort((left, right) => right.percent - left.percent),
    [metrics.exchangeCoverage],
  );

  const loadOverview = useCallback(async () => {
    setOverviewLoading(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ metrics: OverviewMetrics }>("/data-center/overview", token);
      setMetrics(response.metrics);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载概览指标失败");
    } finally {
      setOverviewLoading(false);
    }
  }, [messageApi]);

  const loadLogs = useCallback(async () => {
    setLogLoading(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ items: EventLogItem[] }>("/data-center/event-logs", token);
      setEventLogs(response.items.map(mapEventLogRow));
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载同步日志失败");
    } finally {
      setLogLoading(false);
    }
  }, [messageApi]);

  const loadSourceStatus = useCallback(async () => {
    setSourceStatusLoading(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ item: DataSourceStatusItem }>("/data-center/source-status", token);
      setSourceStatus(response.item);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载数据源状态失败");
    } finally {
      setSourceStatusLoading(false);
    }
  }, [messageApi]);

  const loadExchangeOptions = useCallback(async () => {
    setExchangeLoading(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ items: ExchangeOption[] }>("/data-center/exchange-options", token);
      setExchangeOptions(response.items);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载交易所选项失败");
    } finally {
      setExchangeLoading(false);
    }
  }, [messageApi]);

  const loadCountryOptions = useCallback(async () => {
    setCountryLoading(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ items: CountryOption[] }>("/data-center/country-options", token);
      setCountryOptions(response.items);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载国家/地区选项失败");
    } finally {
      setCountryLoading(false);
    }
  }, [messageApi]);

  const loadStockOptions = useCallback(
    async (exchangeCode: string) => {
      if (!exchangeCode) {
        setStockOptions([]);
        return;
      }

      setStockLoading(true);
      try {
        const token = getAccessToken();
        const response = await apiGet<{ items: StockOption[] }>(
          `/data-center/stock-options?exchangeCode=${encodeURIComponent(exchangeCode)}`,
          token,
        );
        setStockOptions(response.items);
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载股票选项失败");
      } finally {
        setStockLoading(false);
      }
    },
    [messageApi],
  );

  const loadIndexOptions = useCallback(
    async (countryCode: string) => {
      if (!countryCode) {
        setIndexOptions([]);
        return;
      }

      setStockLoading(true);
      try {
        const token = getAccessToken();
        const response = await apiGet<{ items: IndexOption[] }>(
          `/data-center/index-options?countryCode=${encodeURIComponent(countryCode)}`,
          token,
        );
        setIndexOptions(response.items);
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载指数选项失败");
      } finally {
        setStockLoading(false);
      }
    },
    [messageApi],
  );

  const loadStockDailyCoverage = useCallback(
    async (exchangeCode: string, ticker: string) => {
      if (!exchangeCode || !ticker) {
        setStockDailyCoverage(emptyStockCoverage);
        return;
      }

      setCoverageLoading(true);
      try {
        const token = getAccessToken();
        const response = await apiGet<{ coverage: StockDailyCoverage }>(
          `/data-center/stock-daily-coverage?exchangeCode=${encodeURIComponent(exchangeCode)}&ticker=${encodeURIComponent(ticker)}`,
          token,
        );
        setStockDailyCoverage(response.coverage);
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载股票历史日线覆盖情况失败");
      } finally {
        setCoverageLoading(false);
      }
    },
    [messageApi],
  );

  const loadIndexDailyCoverage = useCallback(
    async (countryCode: string, ticker: string) => {
      if (!countryCode || !ticker) {
        setIndexDailyCoverage(emptyIndexCoverage);
        return;
      }

      setCoverageLoading(true);
      try {
        const token = getAccessToken();
        const response = await apiGet<{ coverage: IndexDailyCoverage }>(
          `/data-center/index-daily-coverage?countryCode=${encodeURIComponent(countryCode)}&ticker=${encodeURIComponent(ticker)}`,
          token,
        );
        setIndexDailyCoverage(response.coverage);
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载指数历史日线覆盖情况失败");
      } finally {
        setCoverageLoading(false);
      }
    },
    [messageApi],
  );

  useEffect(() => {
    void Promise.all([
      loadOverview(),
      loadLogs(),
      loadSourceStatus(),
      loadExchangeOptions(),
      loadCountryOptions(),
    ]);
  }, [loadCountryOptions, loadExchangeOptions, loadLogs, loadOverview, loadSourceStatus]);

  const resetDailyFields = useCallback(() => {
    form.setFieldValue("ticker", undefined);
    form.setFieldValue("dateMode", "auto_fill");
    form.setFieldValue("dateRange", undefined);
    setStockDailyCoverage(emptyStockCoverage);
    setIndexDailyCoverage(emptyIndexCoverage);
  }, [form]);

  const resetStockDailyFields = useCallback(() => {
    form.setFieldValue("exchangeCode", undefined);
    setStockOptions([]);
    resetDailyFields();
  }, [form, resetDailyFields]);

  const resetIndexDailyFields = useCallback(() => {
    form.setFieldValue("countryCode", undefined);
    setIndexOptions([]);
    resetDailyFields();
  }, [form, resetDailyFields]);

  const handleSyncSubmit = useCallback(async () => {
    const values = await form.validateFields();
    setSyncing(true);
    try {
      const token = getAccessToken();
      const response = await apiPost<SyncEnqueueResponse>(
        "/data-center/sync",
        {
          syncItem: values.syncItem,
          exchangeCode: values.exchangeCode,
          countryCode: values.countryCode,
          ticker: values.ticker,
          dateMode: values.dateMode,
          startDate: values.dateRange?.[0]?.format("YYYY-MM-DD"),
          endDate: values.dateRange?.[1]?.format("YYYY-MM-DD"),
        },
        token,
      );

      setModalOpen(false);
      form.resetFields();
      setStockOptions([]);
      setIndexOptions([]);
      setStockDailyCoverage(emptyStockCoverage);
      setIndexDailyCoverage(emptyIndexCoverage);
      messageApi.success(`${response.message}，任务 ID：${response.taskId}`);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "同步失败");
    } finally {
      setSyncing(false);
    }
  }, [form, messageApi]);

  const handleBatchSync = useCallback(async () => {
    setBatchSyncing(true);
    try {
      const token = getAccessToken();
      const response = await apiPost<SyncEnqueueResponse>("/data-center/sync/stocks/batch-auto-fill", {}, token);
      messageApi.success(`${response.message}，任务 ID：${response.taskId}`);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "批量同步失败");
    } finally {
      setBatchSyncing(false);
    }
  }, [messageApi]);

  const handleSyncItemChange = useCallback(
    (value: SyncFormValues["syncItem"]) => {
      if (value !== "stock_list" && value !== "stock_daily_history" && value !== "trading_calendar") {
        form.setFieldValue("exchangeCode", undefined);
      }
      if (value !== "index_list" && value !== "index_daily_history") {
        form.setFieldValue("countryCode", undefined);
      }
      if (value !== "stock_daily_history") {
        setStockOptions([]);
        setStockDailyCoverage(emptyStockCoverage);
      }
      if (value !== "index_daily_history") {
        setIndexOptions([]);
        setIndexDailyCoverage(emptyIndexCoverage);
      }
      if (value !== "stock_daily_history" && value !== "index_daily_history") {
        form.setFieldValue("ticker", undefined);
        form.setFieldValue("dateMode", "auto_fill");
        form.setFieldValue("dateRange", undefined);
      }
    },
    [form],
  );

  const handleDailyExchangeChange = useCallback(
    (value: string) => {
      form.setFieldValue("ticker", undefined);
      form.setFieldValue("dateRange", undefined);
      setStockDailyCoverage(emptyStockCoverage);
      void loadStockOptions(value);
    },
    [form, loadStockOptions],
  );

  const handleDailyCountryChange = useCallback(
    (value: string) => {
      form.setFieldValue("ticker", undefined);
      form.setFieldValue("dateRange", undefined);
      setIndexDailyCoverage(emptyIndexCoverage);
      void loadIndexOptions(value);
    },
    [form, loadIndexOptions],
  );

  const handleStockTickerChange = useCallback(
    (value: string, exchangeCode: string) => {
      void loadStockDailyCoverage(exchangeCode, value);
    },
    [loadStockDailyCoverage],
  );

  const handleIndexTickerChange = useCallback(
    (value: string, countryCode: string) => {
      void loadIndexDailyCoverage(countryCode, value);
    },
    [loadIndexDailyCoverage],
  );

  return (
    <AppShell>
      {contextHolder}

      <DataCenterHeader
        batchSyncing={batchSyncing}
        onBatchSync={() => void handleBatchSync()}
        onOpenSyncModal={() => setModalOpen(true)}
      />

      <MetricCardsRow metrics={metrics} loading={overviewLoading} />

      <DataBrowserCard countryOptions={countryOptions} exchangeOptions={exchangeOptions} />

      <Row gutter={[20, 20]} className="dashboard-main-row equal-height-row">
        <Col xs={24} xl={15}>
          <SyncOverviewCard
            logLoading={logLoading}
            eventLogs={eventLogs}
            onRefresh={() => void Promise.all([loadLogs(), loadSourceStatus()])}
          />
        </Col>
        <Col xs={24} xl={9}>
          <SourceStatusCard item={sourceStatus} loading={sourceStatusLoading} />
        </Col>
      </Row>

      <Row gutter={[20, 20]} className="dashboard-secondary-row equal-height-row">
        <Col xs={24} xl={10}>
          <ExchangeCoverageCard exchangeCoverage={exchangeCoverage} />
        </Col>
        <Col xs={24} xl={14}>
          <TradingCalendarCard countryOptions={countryOptions} exchangeOptions={exchangeOptions} />
        </Col>
      </Row>

      <SyncDataModal
        open={modalOpen}
        syncing={syncing}
        form={form}
        exchangeLoading={exchangeLoading}
        countryLoading={countryLoading}
        stockLoading={stockLoading}
        coverageLoading={coverageLoading}
        exchangeOptions={exchangeOptions}
        countryOptions={countryOptions}
        stockOptions={stockOptions}
        indexOptions={indexOptions}
        stockDailyCoverage={stockDailyCoverage}
        indexDailyCoverage={indexDailyCoverage}
        onSubmit={() => void handleSyncSubmit()}
        onCancel={() => {
          if (!syncing) {
            setModalOpen(false);
          }
        }}
        onSyncItemChange={handleSyncItemChange}
        onExchangeChange={handleDailyExchangeChange}
        onCountryChange={handleDailyCountryChange}
        onStockTickerChange={handleStockTickerChange}
        onIndexTickerChange={handleIndexTickerChange}
      />
    </AppShell>
  );
}
