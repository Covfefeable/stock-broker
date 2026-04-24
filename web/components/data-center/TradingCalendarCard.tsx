"use client";

import { useEffect, useMemo, useState } from "react";
import { Button, Calendar, Card, Modal, Select, Space, Tag, Typography, message } from "antd";
import type { CountryOption, ExchangeOption, SyncEnqueueResponse, TradingCalendarDay } from "@/components/data-center/types";
import { getAccessToken } from "@/lib/auth";
import { apiGet, apiPost } from "@/lib/api";

const { Text } = Typography;

type Props = {
  countryOptions: CountryOption[];
  exchangeOptions: ExchangeOption[];
};

type CalendarValue = {
  year: () => number;
  month: () => number;
  format: (pattern: string) => string;
  date: () => number;
};

export function TradingCalendarCard({ countryOptions, exchangeOptions }: Props) {
  const [messageApi, contextHolder] = message.useMessage();
  const [modal, modalHolder] = Modal.useModal();
  const [countryCode, setCountryCode] = useState<string>();
  const [exchangeCode, setExchangeCode] = useState<string>();
  const [panelMonth, setPanelMonth] = useState<Date>(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [items, setItems] = useState<TradingCalendarDay[]>([]);
  const [loading, setLoading] = useState(false);
  const [queried, setQueried] = useState(false);

  const filteredExchangeOptions = useMemo(() => {
    if (!countryCode) {
      return [];
    }
    return exchangeOptions.filter((item) => item.countryCode === countryCode);
  }, [countryCode, exchangeOptions]);

  useEffect(() => {
    if (!countryCode) {
      setExchangeCode(undefined);
      setItems([]);
      return;
    }

    if (filteredExchangeOptions.length === 0) {
      setExchangeCode(undefined);
      setItems([]);
      return;
    }

    if (exchangeCode && !filteredExchangeOptions.some((item) => item.value === exchangeCode)) {
      setExchangeCode(undefined);
      setItems([]);
    }
  }, [countryCode, exchangeCode, filteredExchangeOptions]);

  const dayMap = useMemo(() => {
    const map = new Map<string, TradingCalendarDay>();
    for (const item of items) {
      map.set(item.date, item);
    }
    return map;
  }, [items]);

  const tradingCount = useMemo(() => items.filter((item) => item.status === 1).length, [items]);
  const closedCount = useMemo(() => items.filter((item) => item.status === 0).length, [items]);
  const panelMonthKey = `${panelMonth.getFullYear()}-${panelMonth.getMonth()}`;

  async function queryCalendar(nextMonth: Date, nextExchangeCode: string, withSyncPrompt = true) {
    setLoading(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ items: TradingCalendarDay[] }>(
        `/data-center/trading-calendar?exchangeCode=${encodeURIComponent(nextExchangeCode)}&year=${nextMonth.getFullYear()}&month=${nextMonth.getMonth() + 1}`,
        token,
      );
      setQueried(true);
      setItems(response.items);
      if (response.items.length === 0 && withSyncPrompt) {
        messageApi.warning("当前月份暂无交易日历数据。");
        promptSync("calendar", nextExchangeCode);
      }
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载交易日历失败");
    } finally {
      setLoading(false);
    }
  }

  async function enqueueSync(syncItem: "exchange_list" | "trading_calendar", exchangeValue?: string) {
    const token = getAccessToken();
    const payload =
      syncItem === "trading_calendar"
        ? { syncItem, exchangeCode: exchangeValue }
        : { syncItem };
    const response = await apiPost<SyncEnqueueResponse>("/data-center/sync", payload, token);
    messageApi.success(`${response.message}，请稍后进行查询。`);
  }

  function promptSync(kind: "exchange" | "calendar", exchangeValue?: string) {
    const config =
      kind === "exchange"
        ? {
            title: "当前国家下暂无交易所数据",
            content: "是否现在同步交易所清单？同步完成后再回来查询交易日历即可。",
            onOk: () => enqueueSync("exchange_list"),
          }
        : {
            title: "当前交易所暂无交易日历数据",
            content: "是否现在同步交易日历？同步完成后再回来查询即可。",
            onOk: () => enqueueSync("trading_calendar", exchangeValue),
          };

    modal.confirm({
      ...config,
      okText: "同步",
      cancelText: "取消",
    });
  }

  async function handleQuery() {
    if (!countryCode) {
      messageApi.warning("请先选择国家/地区。");
      return;
    }
    if (filteredExchangeOptions.length === 0) {
      promptSync("exchange");
      return;
    }
    if (!exchangeCode) {
      messageApi.warning("请先选择交易所。");
      return;
    }

    try {
      await queryCalendar(panelMonth, exchangeCode, true);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载交易日历失败");
    }
  }

  return (
    <>
      {contextHolder}
      {modalHolder}
      <Card className="dashboard-card trading-calendar-card" title="交易日历">
        <div className="trading-calendar-toolbar">
        <Select
          showSearch
          value={countryCode}
          options={countryOptions}
          placeholder="请选择国家/地区"
          optionFilterProp="label"
          className="trading-calendar-select"
          onChange={(value: string) => {
            const nextExchangeOptions = exchangeOptions.filter((item) => item.countryCode === value);
            setCountryCode(value);
            setItems([]);
            setQueried(false);
            if (nextExchangeOptions.length === 0) {
              promptSync("exchange");
            }
          }}
        />
        <Select
          showSearch
          value={exchangeCode}
          options={filteredExchangeOptions}
          placeholder={countryCode ? "请选择交易所" : "请先选择国家/地区"}
          optionFilterProp="label"
          className="trading-calendar-select"
          onChange={(value: string) => {
            setExchangeCode(value);
            setItems([]);
            setQueried(false);
          }}
        />
        <Button type="primary" className="trading-calendar-query-button" onClick={() => void handleQuery()}>
          查询
        </Button>
        </div>

        <div className="trading-calendar-summary">
          <Space size={8} wrap>
            <Tag color="green">交易日 {tradingCount}</Tag>
            <Tag color="default">休市日 {closedCount}</Tag>
            <Tag color="blue">
              {new Intl.DateTimeFormat("zh-CN", {
                year: "numeric",
                month: "2-digit",
              }).format(panelMonth)}
            </Tag>
            {loading ? <Tag color="processing">加载中</Tag> : null}
          </Space>
        </div>

        <Calendar
          fullscreen={false}
          onPanelChange={(value: CalendarValue) => {
            const nextMonth = new Date(value.year(), value.month(), 1);
            setPanelMonth(nextMonth);
            if (exchangeCode && queried) {
              void queryCalendar(nextMonth, exchangeCode, true);
            } else {
              setItems([]);
            }
          }}
          dateFullCellRender={(value: CalendarValue) => {
            const key = value.format("YYYY-MM-DD");
            const item = dayMap.get(key);
            const isCurrentMonth = `${value.year()}-${value.month()}` === panelMonthKey;
            const cellClassName = [
              "trading-calendar-cell",
              isCurrentMonth ? "" : "trading-calendar-cell-other-month",
              item?.status === 1
                ? "trading-calendar-cell-open"
                : item?.status === 0
                  ? "trading-calendar-cell-closed"
                  : "",
            ]
              .filter(Boolean)
              .join(" ");

            return (
              <div className={cellClassName}>
                <div className="trading-calendar-cell-date">{value.date()}</div>
                <div className="trading-calendar-cell-status">
                  {item?.status === 1 ? "开市" : item?.status === 0 ? "休市" : ""}
                </div>
              </div>
            );
          }}
        />

        {!exchangeCode ? (
          <div className="trading-calendar-empty">
            <Text type="secondary">请选择国家/地区和交易所，然后查询交易日历。</Text>
          </div>
        ) : queried && !loading && items.length === 0 ? (
          <div className="trading-calendar-empty">
            <Text type="secondary">当前月份暂无交易日历数据，请同步后再查询。</Text>
          </div>
        ) : null}
      </Card>
    </>
  );
}
