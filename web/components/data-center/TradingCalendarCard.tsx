"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Calendar, Card, Select, Space, Tag, Typography, message } from "antd";
import type { CountryOption, ExchangeOption, TradingCalendarDay } from "@/components/data-center/types";
import { getAccessToken } from "@/lib/auth";
import { apiGet } from "@/lib/api";

const { Text } = Typography;

type Props = {
  countryOptions: CountryOption[];
  exchangeOptions: ExchangeOption[];
};

export function TradingCalendarCard({ countryOptions, exchangeOptions }: Props) {
  const [messageApi, contextHolder] = message.useMessage();
  const [countryCode, setCountryCode] = useState<string>();
  const [exchangeCode, setExchangeCode] = useState<string>();
  const [panelMonth, setPanelMonth] = useState<Date>(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [items, setItems] = useState<TradingCalendarDay[]>([]);
  const [loading, setLoading] = useState(false);

  const filteredExchangeOptions = useMemo(() => {
    if (!countryCode) {
      return [];
    }
    return exchangeOptions.filter((item) => item.countryCode === countryCode);
  }, [countryCode, exchangeOptions]);

  useEffect(() => {
    if (!countryCode && countryOptions.length > 0) {
      setCountryCode(countryOptions[0].value);
    }
  }, [countryCode, countryOptions]);

  useEffect(() => {
    if (!countryCode) {
      setExchangeCode(undefined);
      return;
    }
    if (filteredExchangeOptions.length === 0) {
      setExchangeCode(undefined);
      return;
    }
    if (!exchangeCode || !filteredExchangeOptions.some((item) => item.value === exchangeCode)) {
      setExchangeCode(filteredExchangeOptions[0].value);
    }
  }, [countryCode, exchangeCode, filteredExchangeOptions]);

  const loadCalendar = useCallback(async () => {
    if (!exchangeCode) {
      setItems([]);
      return;
    }

    setLoading(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ items: TradingCalendarDay[] }>(
        `/data-center/trading-calendar?exchangeCode=${encodeURIComponent(exchangeCode)}&year=${panelMonth.getFullYear()}&month=${panelMonth.getMonth() + 1}`,
        token,
      );
      setItems(response.items);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载交易日历失败");
    } finally {
      setLoading(false);
    }
  }, [exchangeCode, messageApi, panelMonth]);

  useEffect(() => {
    void loadCalendar();
  }, [loadCalendar]);

  const dayMap = useMemo(() => {
    const map = new Map<string, TradingCalendarDay>();
    for (const item of items) {
      map.set(item.date, item);
    }
    return map;
  }, [items]);

  const tradingCount = useMemo(() => items.filter((item) => item.status === 1).length, [items]);
  const closedCount = useMemo(() => items.filter((item) => item.status === 0).length, [items]);

  return (
    <Card className="dashboard-card trading-calendar-card" title="交易日历" loading={loading}>
      {contextHolder}
      <div className="trading-calendar-toolbar">
        <Select
          showSearch
          value={countryCode}
          options={countryOptions}
          placeholder="请选择国家/地区"
          optionFilterProp="label"
          className="trading-calendar-select"
          onChange={(value) => setCountryCode(value)}
        />
        <Select
          showSearch
          value={exchangeCode}
          options={filteredExchangeOptions}
          placeholder={countryCode ? "请选择交易所" : "请先选择国家/地区"}
          optionFilterProp="label"
          className="trading-calendar-select"
          onChange={(value) => setExchangeCode(value)}
        />
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
        </Space>
      </div>

      {exchangeCode ? (
        <Calendar
          fullscreen={false}
          onPanelChange={(value) => {
            const nextMonth = new Date(value.year(), value.month(), 1);
            setPanelMonth(nextMonth);
          }}
          dateFullCellRender={(value) => {
            const key = value.format("YYYY-MM-DD");
            const item = dayMap.get(key);
            const isCurrentMonth = value.month() === panelMonth.getMonth();
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
      ) : (
        <div className="trading-calendar-empty">
          <Text type="secondary">请先选择国家/地区和交易所。</Text>
        </div>
      )}
    </Card>
  );
}
