"use client";

import { Card, Col, Form, Row, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { issues, prices } from "@/components/data-center/constants";
import { DataBrowserCard } from "@/components/data-center/DataBrowserCard";
import { DataCenterHeader } from "@/components/data-center/DataCenterHeader";
import { DataQualityIssuesCard } from "@/components/data-center/DataQualityIssuesCard";
import { ExchangeCoverageCard } from "@/components/data-center/ExchangeCoverageCard";
import { MetricCardsRow } from "@/components/data-center/MetricCardsRow";
import { SourceStatusCard } from "@/components/data-center/SourceStatusCard";
import { SyncDataModal } from "@/components/data-center/SyncDataModal";
import { SyncOverviewCard } from "@/components/data-center/SyncOverviewCard";
import type {
  CountryOption,
  EventLogItem,
  ExchangeOption,
  OverviewMetrics,
  StockDailyCoverage,
  StockOption,
  SyncFormValues,
  TaskStatusResponse,
  TimelineLogRow,
} from "@/components/data-center/types";
import { defaultMetrics, mapEventLogRow } from "@/components/data-center/utils";
import { getAccessToken } from "@/lib/auth";
import { apiGet, apiPost } from "@/lib/api";

const TASK_POLL_INTERVAL_MS = 2000;
const TASK_POLL_TIMEOUT_MS = 3 * 60 * 1000;

export default function DataCenterPage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm<SyncFormValues>();

  const [modalOpen, setModalOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [batchSyncing, setBatchSyncing] = useState(false);
  const [logLoading, setLogLoading] = useState(true);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [exchangeLoading, setExchangeLoading] = useState(false);
  const [countryLoading, setCountryLoading] = useState(false);
  const [stockLoading, setStockLoading] = useState(false);
  const [coverageLoading, setCoverageLoading] = useState(false);

  const [metrics, setMetrics] = useState<OverviewMetrics>(defaultMetrics);
  const [exchangeOptions, setExchangeOptions] = useState<ExchangeOption[]>([]);
  const [countryOptions, setCountryOptions] = useState<CountryOption[]>([]);
  const [stockOptions, setStockOptions] = useState<StockOption[]>([]);
  const [dailyCoverage, setDailyCoverage] = useState<StockDailyCoverage>({
    existingDates: [],
    latestDate: null,
    count: 0,
  });
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

  const loadStockDailyCoverage = useCallback(
    async (exchangeCode: string, ticker: string) => {
      if (!exchangeCode || !ticker) {
        setDailyCoverage({ existingDates: [], latestDate: null, count: 0 });
        return;
      }
      setCoverageLoading(true);
      try {
        const token = getAccessToken();
        const response = await apiGet<{ coverage: StockDailyCoverage }>(
          `/data-center/stock-daily-coverage?exchangeCode=${encodeURIComponent(exchangeCode)}&ticker=${encodeURIComponent(ticker)}`,
          token,
        );
        setDailyCoverage(response.coverage);
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载历史日线覆盖情况失败");
      } finally {
        setCoverageLoading(false);
      }
    },
    [messageApi],
  );

  useEffect(() => {
    void Promise.all([loadOverview(), loadLogs(), loadExchangeOptions(), loadCountryOptions()]);
  }, [loadCountryOptions, loadExchangeOptions, loadLogs, loadOverview]);

  const resetDailyHistoryFields = useCallback(() => {
    form.setFieldValue("ticker", undefined);
    form.setFieldValue("dateMode", "auto_fill");
    form.setFieldValue("dateRange", undefined);
    setDailyCoverage({ existingDates: [], latestDate: null, count: 0 });
    setStockOptions([]);
  }, [form]);

  const pollTaskUntilFinished = useCallback(
    async (taskId: string, submittedMessage: string) => {
      const token = getAccessToken();
      const startedAt = Date.now();
      messageApi.success(`${submittedMessage}，任务 ID：${taskId}`);

      while (Date.now() - startedAt < TASK_POLL_TIMEOUT_MS) {
        await sleep(TASK_POLL_INTERVAL_MS);
        const status = await apiGet<TaskStatusResponse>(`/tasks/${encodeURIComponent(taskId)}`, token);
        if (!status.ready) {
          continue;
        }

        await Promise.all([loadLogs(), loadOverview()]);

        if (status.successful) {
          const recordsAffected = status.result?.recordsAffected ?? 0;
          messageApi.success(`任务执行完成，共处理 ${recordsAffected} 条记录`);
        } else {
          messageApi.error(status.error ?? "任务执行失败");
        }
        return;
      }

      messageApi.warning(`任务 ${taskId} 仍在执行，可稍后刷新同步日志查看结果`);
    },
    [loadLogs, loadOverview, messageApi],
  );

  const handleSyncSubmit = useCallback(async () => {
    const values = await form.validateFields();
    setSyncing(true);
    try {
      const token = getAccessToken();
      const response = await apiPost<{ message: string; taskId: string }>(
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
      setDailyCoverage({ existingDates: [], latestDate: null, count: 0 });
      setStockOptions([]);
      void pollTaskUntilFinished(response.taskId, response.message);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "同步失败");
      void Promise.all([loadLogs(), loadOverview()]);
    } finally {
      setSyncing(false);
    }
  }, [form, loadLogs, loadOverview, messageApi, pollTaskUntilFinished]);

  const handleBatchSync = useCallback(async () => {
    setBatchSyncing(true);
    try {
      const token = getAccessToken();
      const response = await apiPost<{ message: string; taskId: string }>(
        "/data-center/sync/stocks/batch-auto-fill",
        {},
        token,
      );
      void pollTaskUntilFinished(response.taskId, response.message);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "批量同步失败");
      void Promise.all([loadLogs(), loadOverview()]);
    } finally {
      setBatchSyncing(false);
    }
  }, [loadLogs, loadOverview, messageApi, pollTaskUntilFinished]);

  const handleSyncItemChange = useCallback(
    (value: SyncFormValues["syncItem"]) => {
      if (value !== "stock_list") {
        form.setFieldValue("exchangeCode", undefined);
      }
      if (value !== "index_list") {
        form.setFieldValue("countryCode", undefined);
      }
      if (value !== "stock_daily_history") {
        resetDailyHistoryFields();
      }
    },
    [form, resetDailyHistoryFields],
  );

  const handleDailyExchangeChange = useCallback(
    (value: string) => {
      form.setFieldValue("ticker", undefined);
      setDailyCoverage({ existingDates: [], latestDate: null, count: 0 });
      void loadStockOptions(value);
    },
    [form, loadStockOptions],
  );

  const handleTickerChange = useCallback(
    (value: string, exchangeCode: string) => {
      void loadStockDailyCoverage(exchangeCode, value);
    },
    [loadStockDailyCoverage],
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

      <Row gutter={[20, 20]} className="dashboard-main-row equal-height-row">
        <Col xs={24} xl={15}>
          <SyncOverviewCard logLoading={logLoading} eventLogs={eventLogs} onRefresh={() => void loadLogs()} />
        </Col>
        <Col xs={24} xl={9}>
          <SourceStatusCard />
        </Col>
      </Row>

      <Row gutter={[20, 20]} className="dashboard-secondary-row equal-height-row">
        <Col xs={24} xl={10}>
          <ExchangeCoverageCard latestTradeDate={metrics.latestTradeDate} exchangeCoverage={exchangeCoverage} />
        </Col>
        <Col xs={24} xl={14}>
          <DataQualityIssuesCard issues={issues} />
        </Col>
      </Row>

      <DataBrowserCard prices={prices} />

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
        dailyCoverage={dailyCoverage}
        onSubmit={() => void handleSyncSubmit()}
        onCancel={() => {
          if (!syncing) setModalOpen(false);
        }}
        onSyncItemChange={handleSyncItemChange}
        onExchangeChange={handleDailyExchangeChange}
        onTickerChange={handleTickerChange}
      />
    </AppShell>
  );
}

function sleep(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
