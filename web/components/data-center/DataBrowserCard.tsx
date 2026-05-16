"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, Modal, Select, Segmented, Space, Statistic, Typography, message } from "antd";
import { useThemeMode } from "@/app/providers";
import { KlineChart } from "@/components/data-center/KlineChart";
import { EmptyState } from "@/components/empty-state";
import type {
  BrowserBar,
  BrowserMeta,
  CountryOption,
  EtfDailyCoverage,
  EtfOption,
  ExchangeOption,
  IndexDailyCoverage,
  IndexOption,
  StockDailyCoverage,
  StockOption,
  SyncEnqueueResponse,
} from "@/components/data-center/types";
import { getAccessToken } from "@/lib/auth";
import { apiGet, apiPost } from "@/lib/api";

const { Text, Title } = Typography;

type BrowserMode = "stock" | "etf" | "index";
type RecentBrowserAsset = {
  type: BrowserMode;
  countryCode: string;
  exchangeCode?: string;
  ticker: string;
  name: string;
  latestDate?: string | null;
  count?: number;
};

type Props = {
  countryOptions: CountryOption[];
  exchangeOptions: ExchangeOption[];
};

const RECENT_BROWSER_ASSETS_KEY = "stock-broker:data-browser:recent-assets";
const RECENT_BROWSER_ASSETS_LIMIT = 9;

export function DataBrowserCard({ countryOptions, exchangeOptions }: Props) {
  const { mode } = useThemeMode();
  const [messageApi, messageHolder] = message.useMessage();
  const [modal, modalHolder] = Modal.useModal();

  const [browserMode, setBrowserMode] = useState<BrowserMode>("stock");
  const [countryCode, setCountryCode] = useState<string>();
  const [exchangeCode, setExchangeCode] = useState<string>();
  const [ticker, setTicker] = useState<string>();
  const [stockOptions, setStockOptions] = useState<StockOption[]>([]);
  const [etfOptions, setEtfOptions] = useState<EtfOption[]>([]);
  const [indexOptions, setIndexOptions] = useState<IndexOption[]>([]);
  const [stockCoverage, setStockCoverage] = useState<StockDailyCoverage>({ existingDates: [], latestDate: null, count: 0 });
  const [etfCoverage, setEtfCoverage] = useState<EtfDailyCoverage>({ existingDates: [], latestDate: null, count: 0 });
  const [indexCoverage, setIndexCoverage] = useState<IndexDailyCoverage>({ existingDates: [], latestDate: null, count: 0 });
  const [bars, setBars] = useState<BrowserBar[]>([]);
  const [meta, setMeta] = useState<BrowserMeta | null>(null);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [coverageLoading, setCoverageLoading] = useState(false);
  const [chartLoading, setChartLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [recentAssets, setRecentAssets] = useState<RecentBrowserAsset[]>([]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      const raw = window.localStorage.getItem(RECENT_BROWSER_ASSETS_KEY);
      if (!raw) {
        return;
      }
      const parsed = JSON.parse(raw) as RecentBrowserAsset[];
      if (Array.isArray(parsed)) {
        setRecentAssets(parsed.filter((item) => item?.type && item?.countryCode && item?.ticker).slice(0, RECENT_BROWSER_ASSETS_LIMIT));
      }
    } catch {
      setRecentAssets([]);
    }
  }, []);

  const saveRecentAsset = useCallback((asset: RecentBrowserAsset) => {
    setRecentAssets((current) => {
      const key = `${asset.type}:${asset.countryCode}:${asset.exchangeCode || ""}:${asset.ticker}`;
      const next = [
        asset,
        ...current.filter((item) => `${item.type}:${item.countryCode}:${item.exchangeCode || ""}:${item.ticker}` !== key),
      ].slice(0, RECENT_BROWSER_ASSETS_LIMIT);
      if (typeof window !== "undefined") {
        window.localStorage.setItem(RECENT_BROWSER_ASSETS_KEY, JSON.stringify(next));
      }
      return next;
    });
  }, []);

  const filteredExchangeOptions = useMemo(() => {
    if (!countryCode) {
      return [];
    }
    return exchangeOptions.filter((item) => item.countryCode === countryCode);
  }, [countryCode, exchangeOptions]);

  const enqueueSync = useCallback(
    async (
      payload:
        | { syncItem: "exchange_list" }
        | { syncItem: "stock_list"; exchangeCode: string }
        | { syncItem: "etf_list"; exchangeCode: string }
        | { syncItem: "index_list"; countryCode: string }
        | { syncItem: "stock_daily_history"; exchangeCode: string; ticker: string; dateMode: "auto_fill" }
        | { syncItem: "etf_daily_history"; exchangeCode: string; ticker: string; dateMode: "auto_fill" }
        | { syncItem: "index_daily_history"; countryCode: string; ticker: string; dateMode: "auto_fill" },
    ) => {
      const token = getAccessToken();
      const enqueue = await apiPost<SyncEnqueueResponse>("/data-center/sync", payload, token);
      messageApi.success(`${enqueue.message}，请稍后进行查询。`);
    },
    [messageApi],
  );

  const promptSyncForMissingLevel = useCallback(
    (kind: "exchange" | "stock" | "etf" | "index", nextCountryCode?: string, nextExchangeCode?: string) => {
      const config =
        kind === "exchange"
          ? {
              title: "当前国家下暂无交易所数据",
              content: "是否现在同步交易所清单？同步完成后再回来继续筛选即可。",
              run: () => enqueueSync({ syncItem: "exchange_list" }),
            }
          : kind === "stock"
            ? {
                title: "当前交易所下暂无股票清单数据",
                content: "是否现在同步该交易所的股票清单？同步完成后再回来继续筛选即可。",
                run: () => enqueueSync({ syncItem: "stock_list", exchangeCode: nextExchangeCode || "" }),
              }
            : kind === "etf"
              ? {
                  title: "当前交易所下暂无 ETF 清单数据",
                  content: "是否现在同步该交易所的 ETF 清单？同步完成后再回来继续筛选即可。",
                  run: () => enqueueSync({ syncItem: "etf_list", exchangeCode: nextExchangeCode || "" }),
                }
              : {
                title: "当前国家下暂无指数清单数据",
                content: "是否现在同步该国家/地区的指数清单？同步完成后再回来继续筛选即可。",
                run: () => enqueueSync({ syncItem: "index_list", countryCode: nextCountryCode || "" }),
              };

      modal.confirm({
        title: config.title,
        content: config.content,
        okText: "同步",
        cancelText: "取消",
        onOk: async () => {
          setSyncing(true);
          try {
            await config.run();
          } catch (error) {
            messageApi.error(error instanceof Error ? error.message : "提交同步任务失败");
          } finally {
            setSyncing(false);
          }
        },
      });
    },
    [enqueueSync, messageApi, modal],
  );

  const loadStockOptions = useCallback(async (nextExchangeCode: string) => {
    if (!nextExchangeCode) {
      setStockOptions([]);
      return [];
    }

    setOptionsLoading(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ items: StockOption[] }>(
        `/data-center/stock-options?exchangeCode=${encodeURIComponent(nextExchangeCode)}`,
        token,
      );
      setStockOptions(response.items);
      return response.items;
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载股票选项失败");
      return [];
    } finally {
      setOptionsLoading(false);
    }
  }, [messageApi]);

  const loadIndexOptions = useCallback(async (nextCountryCode: string) => {
    if (!nextCountryCode) {
      setIndexOptions([]);
      return [];
    }

    setOptionsLoading(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ items: IndexOption[] }>(
        `/data-center/index-options?countryCode=${encodeURIComponent(nextCountryCode)}`,
        token,
      );
      setIndexOptions(response.items);
      return response.items;
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载指数选项失败");
      return [];
    } finally {
      setOptionsLoading(false);
    }
  }, [messageApi]);

  const loadEtfOptions = useCallback(async (nextExchangeCode: string) => {
    if (!nextExchangeCode) {
      setEtfOptions([]);
      return [];
    }

    setOptionsLoading(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ items: EtfOption[] }>(
        `/data-center/etf-options?exchangeCode=${encodeURIComponent(nextExchangeCode)}`,
        token,
      );
      setEtfOptions(response.items);
      return response.items;
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载 ETF 选项失败");
      return [];
    } finally {
      setOptionsLoading(false);
    }
  }, [messageApi]);

  const promptSyncIfNeeded = useCallback(async (kind: BrowserMode, nextCountryCode?: string, nextExchangeCode?: string, nextTicker?: string) => {
    if (!nextTicker) {
      return;
    }

    setCoverageLoading(true);
    try {
      const token = getAccessToken();
      const response =
        kind === "stock"
          ? await apiGet<{ coverage: StockDailyCoverage }>(
              `/data-center/stock-daily-coverage?exchangeCode=${encodeURIComponent(nextExchangeCode || "")}&ticker=${encodeURIComponent(nextTicker)}`,
              token,
            )
          : kind === "etf"
            ? await apiGet<{ coverage: EtfDailyCoverage }>(
                `/data-center/etf-daily-coverage?exchangeCode=${encodeURIComponent(nextExchangeCode || "")}&ticker=${encodeURIComponent(nextTicker)}`,
                token,
              )
            : await apiGet<{ coverage: IndexDailyCoverage }>(
              `/data-center/index-daily-coverage?countryCode=${encodeURIComponent(nextCountryCode || "")}&ticker=${encodeURIComponent(nextTicker)}`,
              token,
            );

      const coverage = response.coverage;
      if (kind === "stock") {
        setStockCoverage(coverage as StockDailyCoverage);
      } else if (kind === "etf") {
        setEtfCoverage(coverage as EtfDailyCoverage);
      } else {
        setIndexCoverage(coverage as IndexDailyCoverage);
      }

      if (coverage.latestDate) {
        return;
      }

      modal.confirm({
        title: kind === "stock" ? "该股票尚未同步日线数据" : kind === "etf" ? "该 ETF 尚未同步日线数据" : "该指数尚未同步日线数据",
        content: "是否现在发起同步？同步任务会进入后台执行，完成后再回来查询即可。",
        okText: "同步",
        cancelText: "取消",
        onOk: async () => {
          setSyncing(true);
          try {
            await enqueueSync(
              kind === "stock"
                ? {
                    syncItem: "stock_daily_history",
                    exchangeCode: nextExchangeCode || "",
                    ticker: nextTicker,
                    dateMode: "auto_fill",
                  }
                : kind === "etf"
                  ? {
                      syncItem: "etf_daily_history",
                      exchangeCode: nextExchangeCode || "",
                      ticker: nextTicker,
                      dateMode: "auto_fill",
                    }
                : {
                    syncItem: "index_daily_history",
                    countryCode: nextCountryCode || "",
                    ticker: nextTicker,
                    dateMode: "auto_fill",
                  },
            );
          } catch (error) {
            messageApi.error(error instanceof Error ? error.message : "提交同步任务失败");
          } finally {
            setSyncing(false);
          }
        },
      });
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载已同步覆盖情况失败");
    } finally {
      setCoverageLoading(false);
    }
  }, [enqueueSync, messageApi, modal]);

  const handleModeChange = useCallback((value: BrowserMode) => {
    setBrowserMode(value);
    setCountryCode(undefined);
    setExchangeCode(undefined);
    setTicker(undefined);
    setStockOptions([]);
    setEtfOptions([]);
    setIndexOptions([]);
    setStockCoverage({ existingDates: [], latestDate: null, count: 0 });
    setEtfCoverage({ existingDates: [], latestDate: null, count: 0 });
    setIndexCoverage({ existingDates: [], latestDate: null, count: 0 });
    setBars([]);
    setMeta(null);
  }, []);

  const handleCountryChange = useCallback(async (value: string) => {
    setCountryCode(value);
    setExchangeCode(undefined);
    setTicker(undefined);
    setBars([]);
    setMeta(null);
    setStockCoverage({ existingDates: [], latestDate: null, count: 0 });
    setEtfCoverage({ existingDates: [], latestDate: null, count: 0 });
    setIndexCoverage({ existingDates: [], latestDate: null, count: 0 });
    if (browserMode === "stock" || browserMode === "etf") {
      setStockOptions([]);
      setEtfOptions([]);
      const nextExchangeOptions = exchangeOptions.filter((item) => item.countryCode === value);
      if (!nextExchangeOptions.length) {
        promptSyncForMissingLevel("exchange", value);
      }
      return;
    }
    const items = await loadIndexOptions(value);
    if (!items.length) {
      promptSyncForMissingLevel("index", value);
    }
  }, [browserMode, exchangeOptions, loadIndexOptions, promptSyncForMissingLevel]);

  const handleExchangeChange = useCallback(async (value: string) => {
    setExchangeCode(value);
    setTicker(undefined);
    setBars([]);
    setMeta(null);
    setStockCoverage({ existingDates: [], latestDate: null, count: 0 });
    setEtfCoverage({ existingDates: [], latestDate: null, count: 0 });
    const items = browserMode === "etf" ? await loadEtfOptions(value) : await loadStockOptions(value);
    if (!items.length) {
      promptSyncForMissingLevel(browserMode === "etf" ? "etf" : "stock", undefined, value);
    }
  }, [browserMode, loadEtfOptions, loadStockOptions, promptSyncForMissingLevel]);

  const handleTickerChange = useCallback(async (value: string) => {
    setTicker(value);
    setBars([]);
    setMeta(null);
    await promptSyncIfNeeded(browserMode, countryCode, exchangeCode, value);
  }, [browserMode, countryCode, exchangeCode, promptSyncIfNeeded]);

  const loadBrowserBars = useCallback(async (kind: BrowserMode, nextCountryCode: string, nextExchangeCode: string | undefined, nextTicker: string) => {
    setChartLoading(true);
    try {
      const token = getAccessToken();
      const response =
        kind === "stock"
          ? await apiGet<{ meta: BrowserMeta | null; bars: BrowserBar[] }>(
              `/data-center/browser/stock-bars?exchangeCode=${encodeURIComponent(nextExchangeCode || "")}&ticker=${encodeURIComponent(nextTicker)}`,
              token,
            )
          : kind === "etf"
            ? await apiGet<{ meta: BrowserMeta | null; bars: BrowserBar[] }>(
                `/data-center/browser/etf-bars?exchangeCode=${encodeURIComponent(nextExchangeCode || "")}&ticker=${encodeURIComponent(nextTicker)}`,
                token,
              )
            : await apiGet<{ meta: BrowserMeta | null; bars: BrowserBar[] }>(
              `/data-center/browser/index-bars?countryCode=${encodeURIComponent(nextCountryCode)}&ticker=${encodeURIComponent(nextTicker)}`,
              token,
            );
      setMeta(response.meta);
      setBars(response.bars);
      if (response.meta) {
        const coverage = { existingDates: [], latestDate: response.meta.latestDate, count: response.meta.count };
        if (kind === "stock") {
          setStockCoverage(coverage);
        } else if (kind === "etf") {
          setEtfCoverage(coverage);
        } else {
          setIndexCoverage(coverage);
        }
        saveRecentAsset({
          type: kind,
          countryCode: response.meta.countryCode || nextCountryCode,
          exchangeCode: kind === "index" ? undefined : response.meta.exchangeCode || nextExchangeCode,
          ticker: response.meta.ticker,
          name: response.meta.name,
          latestDate: response.meta.latestDate,
          count: response.meta.count,
        });
      }
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载 K 线数据失败");
    } finally {
      setChartLoading(false);
    }
  }, [messageApi, saveRecentAsset]);

  const handleQuery = useCallback(async () => {
    if (browserMode === "stock" || browserMode === "etf") {
      if (!countryCode || !exchangeCode || !ticker) {
        messageApi.warning(`请先完整选择国家、交易所和${browserMode === "etf" ? "ETF" : "股票"}。`);
        return;
      }
      const coverage = browserMode === "etf" ? etfCoverage : stockCoverage;
      if (!coverage.latestDate) {
        await promptSyncIfNeeded(browserMode, countryCode, exchangeCode, ticker);
        return;
      }
      await loadBrowserBars(browserMode, countryCode, exchangeCode, ticker);
      return;
    }

    if (!countryCode || !ticker) {
      messageApi.warning("请先完整选择国家和指数。");
      return;
    }
    if (!indexCoverage.latestDate) {
      await promptSyncIfNeeded("index", countryCode, undefined, ticker);
      return;
    }
    await loadBrowserBars("index", countryCode, undefined, ticker);
  }, [browserMode, countryCode, etfCoverage, exchangeCode, indexCoverage.latestDate, loadBrowserBars, messageApi, promptSyncIfNeeded, stockCoverage, ticker]);

  const handleRecentAssetClick = useCallback(async (asset: RecentBrowserAsset) => {
    setBrowserMode(asset.type);
    setCountryCode(asset.countryCode);
    setExchangeCode(asset.exchangeCode);
    setTicker(asset.ticker);
    setBars([]);
    setMeta(null);
    setStockCoverage({ existingDates: [], latestDate: null, count: 0 });
    setEtfCoverage({ existingDates: [], latestDate: null, count: 0 });
    setIndexCoverage({ existingDates: [], latestDate: null, count: 0 });
    if (asset.type === "stock" && asset.exchangeCode) {
      await loadStockOptions(asset.exchangeCode);
    } else if (asset.type === "etf" && asset.exchangeCode) {
      await loadEtfOptions(asset.exchangeCode);
    } else if (asset.type === "index") {
      await loadIndexOptions(asset.countryCode);
    }
    await loadBrowserBars(asset.type, asset.countryCode, asset.exchangeCode, asset.ticker);
  }, [loadBrowserBars, loadEtfOptions, loadIndexOptions, loadStockOptions]);

  const latestBar = bars[bars.length - 1];

  return (
    <Card
      className="dashboard-card data-browser-card"
      title="行情数据浏览器"
      extra={
        <Segmented<BrowserMode>
          value={browserMode}
          onChange={(value) => handleModeChange(value as BrowserMode)}
          options={[
            { label: "股票", value: "stock" },
            { label: "ETF", value: "etf" },
            { label: "指数", value: "index" },
          ]}
        />
      }
    >
      {messageHolder}
      {modalHolder}

      <div className="data-browser-toolbar">
        <Select
          value={countryCode}
          placeholder="请选择国家/地区"
          options={countryOptions}
          className="data-browser-select"
          showSearch
          optionFilterProp="label"
          onChange={(value) => void handleCountryChange(value)}
        />

        {browserMode === "stock" || browserMode === "etf" ? (
          <>
            <Select
              value={exchangeCode}
              placeholder={countryCode ? "请选择交易所" : "请先选择国家/地区"}
              options={filteredExchangeOptions}
              className="data-browser-select"
              showSearch
              optionFilterProp="label"
              onChange={(value) => void handleExchangeChange(value)}
            />
            <Select
              value={ticker}
              placeholder={exchangeCode ? (browserMode === "etf" ? "请选择 ETF" : "请选择股票") : "请先选择交易所"}
              options={browserMode === "etf" ? etfOptions : stockOptions}
              className="data-browser-select data-browser-select-wide"
              loading={optionsLoading}
              showSearch
              optionFilterProp="label"
              onChange={(value) => void handleTickerChange(value)}
            />
          </>
        ) : (
          <Select
            value={ticker}
            placeholder={countryCode ? "请选择指数" : "请先选择国家/地区"}
            options={indexOptions}
            className="data-browser-select data-browser-select-wide"
            loading={optionsLoading}
            showSearch
            optionFilterProp="label"
            onChange={(value) => void handleTickerChange(value)}
          />
        )}

        <Button className="data-browser-query-button" type="primary" loading={chartLoading || syncing} onClick={() => void handleQuery()}>
          查询
        </Button>
      </div>

      {recentAssets.length ? (
        <div className="data-browser-recent-row">
          <Text type="secondary">最近查看</Text>
          <Space size={[8, 8]} wrap>
            {recentAssets.map((item) => (
              <Button
                key={`${item.type}:${item.countryCode}:${item.exchangeCode || ""}:${item.ticker}`}
                size="small"
                className="data-browser-recent-button"
                onClick={() => void handleRecentAssetClick(item)}
              >
                {item.name} ({item.ticker}) · {item.type === "stock" ? "股票" : item.type === "etf" ? "ETF" : "指数"}
              </Button>
            ))}
          </Space>
        </div>
      ) : null}

      {meta ? (
        <div className="data-browser-meta-row">
          <div className="data-browser-meta-copy">
            <Title level={5}>
              {meta.name} ({meta.ticker})
            </Title>
            <Text type="secondary">
              {browserMode === "stock" ? `${meta.countryCode} · ${meta.exchangeCode}` : browserMode === "etf" ? `${meta.countryCode} · ${meta.exchangeCode} · ETF` : `${meta.countryCode} · 指数`}
            </Text>
          </div>
          <Space size={24} wrap>
            <Statistic title="最新日期" value={meta.latestDate ?? "-"} />
            <Statistic title="数据点" value={meta.count} />
            <Statistic title="收盘价" value={latestBar?.close ?? "-"} precision={latestBar?.close ? 3 : 0} />
            <Statistic title="成交量" value={latestBar?.volume ?? "-"} />
          </Space>
        </div>
      ) : null}

      {chartLoading ? (
        <div className="data-browser-empty-chart">
          <EmptyState title="正在加载 K 线数据" />
        </div>
      ) : (
        <KlineChart bars={bars} dark={mode === "dark"} />
      )}
    </Card>
  );
}
