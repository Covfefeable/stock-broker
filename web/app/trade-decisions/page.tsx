"use client";

import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import {
  Button,
  Card,
  InputNumber,
  Modal,
  Radio,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { apiGet, apiPost } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

const { Text, Title } = Typography;

type AssetType = "stock" | "index";
type PositionStatus = "empty" | "holding";

type OptionItem = {
  label: string;
  value: string;
  countryCode?: string;
  latestDate?: string | null;
};

type StrategyOption = {
  label: string;
  value: number;
  strategyId: number;
  name: string;
  assetType: AssetType;
  assetName: string | null;
  assetIdentifier: string;
  evaluationScore: number | null;
};

type DecisionItem = {
  strategyId: number;
  strategyName: string;
  strategyAssetName: string | null;
  strategyAssetIdentifier: string;
  strategyAssetType: AssetType;
  isSameAsset: boolean;
  evaluationScore: number | null;
  evaluationConclusion: string | null;
  annualReturn: number | null;
  maxDrawdown: number | null;
  sharpe: number | null;
  signalDate: string | null;
  updatedAt: string | null;
  recommendation: {
    action: "buy" | "add" | "sell" | "reduce" | "hold" | "watch";
    label: string;
    size: number;
    ruleName: string | null;
    reason: string;
  };
};

type DecisionResponse = {
  asset: {
    assetType: AssetType;
    countryCode: string;
    exchangeCode?: string | null;
    ticker: string;
    name: string;
    assetIdentifier: string;
    latestDate: string | null;
  };
  summary: {
    label: string;
    description: string;
    counts: {
      buy: number;
      sell: number;
      hold: number;
      watch: number;
    };
  };
  items: DecisionItem[];
};

const actionColorMap: Record<DecisionItem["recommendation"]["action"], string> = {
  buy: "green",
  add: "cyan",
  sell: "red",
  reduce: "orange",
  hold: "blue",
  watch: "default",
};

export default function TradeDecisionsPage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [assetType, setAssetType] = useState<AssetType>("stock");
  const [positionStatus, setPositionStatus] = useState<PositionStatus>("empty");
  const [countryCode, setCountryCode] = useState<string>();
  const [exchangeCode, setExchangeCode] = useState<string>();
  const [ticker, setTicker] = useState<string>();
  const [positionRatioPercent, setPositionRatioPercent] = useState<number | null>(50);
  const [floatingReturnPercent, setFloatingReturnPercent] = useState<number | null>(null);
  const [holdingDays, setHoldingDays] = useState<number | null>(null);
  const [countryOptions, setCountryOptions] = useState<OptionItem[]>([]);
  const [exchangeOptions, setExchangeOptions] = useState<OptionItem[]>([]);
  const [assetOptions, setAssetOptions] = useState<OptionItem[]>([]);
  const [extraStrategyIds, setExtraStrategyIds] = useState<number[]>([]);
  const [extraStrategyOptions, setExtraStrategyOptions] = useState<StrategyOption[]>([]);
  const [extraModalOpen, setExtraModalOpen] = useState(false);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingExtra, setLoadingExtra] = useState(false);
  const [result, setResult] = useState<DecisionResponse | null>(null);

  const filteredExchangeOptions = useMemo(
    () => exchangeOptions.filter((item) => !countryCode || item.countryCode === countryCode),
    [countryCode, exchangeOptions],
  );

  const selectedAssetIdentifier = useMemo(() => {
    if (!ticker) {
      return "";
    }
    return assetType === "stock" && exchangeCode ? `${exchangeCode}:${ticker}` : ticker;
  }, [assetType, exchangeCode, ticker]);

  const loadBaseOptions = useCallback(async () => {
    setLoadingOptions(true);
    try {
      const token = getAccessToken();
      const [countries, exchanges] = await Promise.all([
        apiGet<{ items: OptionItem[] }>("/data-center/country-options", token),
        apiGet<{ items: OptionItem[] }>("/data-center/exchange-options", token),
      ]);
      setCountryOptions(countries.items);
      setExchangeOptions(exchanges.items);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载基础选项失败");
    } finally {
      setLoadingOptions(false);
    }
  }, [messageApi]);

  const loadAssetOptions = useCallback(async () => {
    if (assetType === "stock" && !exchangeCode) {
      setAssetOptions([]);
      return;
    }
    if (assetType === "index" && !countryCode) {
      setAssetOptions([]);
      return;
    }

    setLoadingOptions(true);
    try {
      const token = getAccessToken();
      const path =
        assetType === "stock"
          ? `/data-center/stock-options?exchangeCode=${encodeURIComponent(exchangeCode ?? "")}`
          : `/data-center/index-options?countryCode=${encodeURIComponent(countryCode ?? "")}`;
      const response = await apiGet<{ items: OptionItem[] }>(path, token);
      setAssetOptions(response.items);
      if (response.items.length === 0) {
        messageApi.info("当前下级暂无数据，请先到数据中心同步。");
      }
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载标的选项失败");
    } finally {
      setLoadingOptions(false);
    }
  }, [assetType, countryCode, exchangeCode, messageApi]);

  useEffect(() => {
    void loadBaseOptions();
  }, [loadBaseOptions]);

  useEffect(() => {
    setTicker(undefined);
    setAssetOptions([]);
    setExtraStrategyIds([]);
    setResult(null);
  }, [assetType, countryCode, exchangeCode]);

  useEffect(() => {
    void loadAssetOptions();
  }, [loadAssetOptions]);

  const buildPayload = useCallback(
    (nextExtraIds = extraStrategyIds) => ({
      assetType,
      countryCode,
      exchangeCode: assetType === "stock" ? exchangeCode : undefined,
      ticker,
      position: {
        status: positionStatus,
        ratio: positionStatus === "holding" ? (positionRatioPercent ?? 0) / 100 : 0,
        floatingReturn:
          positionStatus === "holding" && floatingReturnPercent !== null ? floatingReturnPercent / 100 : null,
        holdingDays: positionStatus === "holding" ? holdingDays : null,
      },
      extraStrategyIds: nextExtraIds,
    }),
    [
      assetType,
      countryCode,
      exchangeCode,
      extraStrategyIds,
      floatingReturnPercent,
      holdingDays,
      positionRatioPercent,
      positionStatus,
      ticker,
    ],
  );

  const handleQuery = useCallback(
    async (nextExtraIds = extraStrategyIds) => {
      if (!countryCode || !ticker || (assetType === "stock" && !exchangeCode)) {
        messageApi.warning("请选择完整的标的信息。");
        return;
      }
      if (positionStatus === "holding" && (!positionRatioPercent || positionRatioPercent <= 0)) {
        messageApi.warning("持仓状态下需要填写当前仓位比例。");
        return;
      }

      setLoading(true);
      try {
        const token = getAccessToken();
        const response = await apiPost<DecisionResponse>("/trade-decisions/evaluate", buildPayload(nextExtraIds), token);
        setResult(response);
        if (response.items.length === 0) {
          messageApi.info("没有找到该标的下非归档且已成功评估的策略。");
        }
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "生成交易建议失败");
      } finally {
        setLoading(false);
      }
    },
    [
      assetType,
      buildPayload,
      countryCode,
      exchangeCode,
      extraStrategyIds,
      messageApi,
      positionRatioPercent,
      positionStatus,
      ticker,
    ],
  );

  const loadExtraStrategies = useCallback(async () => {
    setLoadingExtra(true);
    try {
      const token = getAccessToken();
      const params = new URLSearchParams();
      if (selectedAssetIdentifier) {
        params.set("assetType", assetType);
        params.set("assetIdentifier", selectedAssetIdentifier);
      }
      const response = await apiGet<{ items: StrategyOption[] }>(
        `/trade-decisions/strategy-options?${params.toString()}`,
        token,
      );
      setExtraStrategyOptions(response.items);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载可添加策略失败");
    } finally {
      setLoadingExtra(false);
    }
  }, [assetType, messageApi, selectedAssetIdentifier]);

  const handleOpenExtraModal = () => {
    setExtraModalOpen(true);
    void loadExtraStrategies();
  };

  const handleConfirmExtraStrategies = () => {
    setExtraModalOpen(false);
    void handleQuery(extraStrategyIds);
  };

  const columns = useMemo<ColumnsType<DecisionItem>>(
    () => [
      {
        title: "策略名称",
        dataIndex: "strategyName",
        width: 260,
        render: (value: string, record) => (
          <div className="trade-decision-strategy-cell">
            <Tooltip title={value}>
              <a className="dashboard-ellipsis-strong" href={`/strategy-builder/${record.strategyId}`}>
                {value}
              </a>
            </Tooltip>
            <Text type="secondary">
              {record.strategyAssetName || record.strategyAssetIdentifier}
              {!record.isSameAsset ? " · 手动添加" : ""}
            </Text>
          </div>
        ),
      },
      {
        title: "评分",
        dataIndex: "evaluationScore",
        width: 100,
        render: (value: number | null) => (value === null ? "-" : <strong>{value.toFixed(2)}</strong>),
      },
      {
        title: "建议",
        dataIndex: ["recommendation", "label"],
        width: 130,
        render: (_value: string, record) => (
          <Tag color={actionColorMap[record.recommendation.action]}>{record.recommendation.label}</Tag>
        ),
      },
      {
        title: "命中规则",
        dataIndex: ["recommendation", "ruleName"],
        width: 220,
        render: (_value: string | null, record) => (
          <Tooltip title={record.recommendation.reason}>
            <span className="dashboard-ellipsis">{record.recommendation.ruleName || "-"}</span>
          </Tooltip>
        ),
      },
      {
        title: "年化收益",
        dataIndex: "annualReturn",
        width: 110,
        render: (value: number | null) => (value === null ? "-" : <Text className="positive-text">{value}%</Text>),
      },
      {
        title: "最大回撤",
        dataIndex: "maxDrawdown",
        width: 110,
        render: (value: number | null) => (value === null ? "-" : <Text className="negative-text">{value}%</Text>),
      },
      {
        title: "Sharpe",
        dataIndex: "sharpe",
        width: 90,
        render: (value: number | null) => value ?? "-",
      },
      {
        title: "信号日期",
        dataIndex: "signalDate",
        width: 120,
        render: (value: string | null) => value || "-",
      },
    ],
    [],
  );

  return (
    <AppShell>
      {contextHolder}
      <section className="dashboard-heading">
        <div>
          <Title level={1}>交易决策台</Title>
          <Text className="page-description">基于已评估策略和当前仓位，给出同一标的下的买入、卖出或持有建议。</Text>
        </div>
      </section>

      <Card className="dashboard-card trade-decision-card" bordered>
        <div className="trade-decision-form">
          <div className="trade-decision-form-section trade-decision-form-section-main">
            <div className="trade-decision-form-section-head">
              <Text className="trade-decision-form-title">标的信息</Text>
              <Radio.Group
                optionType="button"
                buttonStyle="solid"
                value={assetType}
                onChange={(event) => setAssetType(event.target.value)}
                options={[
                  { label: "股票", value: "stock" },
                  { label: "指数", value: "index" },
                ]}
              />
            </div>
            <div className="trade-decision-field-grid">
              <label>
                <span>国家/地区</span>
                <Select
                  allowClear
                  showSearch
                  loading={loadingOptions}
                  options={countryOptions}
                  placeholder="请选择国家/地区"
                  value={countryCode}
                  onChange={(value) => {
                    setCountryCode(value);
                    setExchangeCode(undefined);
                  }}
                  filterOption={(input, option) =>
                    String(option?.label ?? "").toLowerCase().includes(input.toLowerCase())
                  }
                />
              </label>
              {assetType === "stock" ? (
                <label>
                  <span>交易所</span>
                  <Select
                    allowClear
                    showSearch
                    loading={loadingOptions}
                    options={filteredExchangeOptions}
                    placeholder="请选择交易所"
                    value={exchangeCode}
                    onChange={setExchangeCode}
                    filterOption={(input, option) =>
                      String(option?.label ?? "").toLowerCase().includes(input.toLowerCase())
                    }
                  />
                </label>
              ) : null}
              <label className={assetType === "index" ? "trade-decision-field-wide" : ""}>
                <span>{assetType === "stock" ? "股票" : "指数"}</span>
                <Select
                  allowClear
                  showSearch
                  loading={loadingOptions}
                  options={assetOptions}
                  placeholder={assetType === "stock" ? "请选择股票" : "请选择指数"}
                  value={ticker}
                  onChange={(value) => {
                    setTicker(value);
                    setResult(null);
                    setExtraStrategyIds([]);
                  }}
                  filterOption={(input, option) =>
                    String(option?.label ?? "").toLowerCase().includes(input.toLowerCase())
                  }
                />
              </label>
            </div>
          </div>

          <div className="trade-decision-form-section">
            <div className="trade-decision-form-section-head">
              <Text className="trade-decision-form-title">当前仓位</Text>
              <Radio.Group
                optionType="button"
                buttonStyle="solid"
                value={positionStatus}
                onChange={(event) => setPositionStatus(event.target.value)}
                options={[
                  { label: "空仓", value: "empty" },
                  { label: "持仓中", value: "holding" },
                ]}
              />
            </div>
            {positionStatus === "holding" ? (
              <div className="trade-decision-field-grid trade-decision-position-grid">
                <label>
                  <span>当前仓位比例</span>
                  <InputNumber
                    min={1}
                    max={100}
                    value={positionRatioPercent}
                    onChange={setPositionRatioPercent}
                    addonAfter="%"
                    placeholder="例如 60"
                  />
                </label>
                <label>
                  <span>当前浮动收益</span>
                  <InputNumber
                    value={floatingReturnPercent}
                    onChange={setFloatingReturnPercent}
                    addonAfter="%"
                    placeholder="例如 8.5"
                  />
                </label>
                <label>
                  <span>已持有交易日</span>
                  <InputNumber min={0} value={holdingDays} onChange={setHoldingDays} placeholder="可选" />
                </label>
              </div>
            ) : (
              <div className="trade-decision-position-empty">
                <Text type="secondary">当前按空仓状态计算，只判断买入规则是否触发。</Text>
              </div>
            )}
          </div>

          <div className="trade-decision-actions">
            <Button type="primary" icon={<SearchOutlined />} loading={loading} onClick={() => void handleQuery()}>
              查询
            </Button>
            <Button icon={<ReloadOutlined />} onClick={handleOpenExtraModal} disabled={!ticker}>
              添加其他策略
            </Button>
          </div>
        </div>
      </Card>

      <Card
        className="dashboard-card trade-decision-result-card"
        bordered
        title="决策结果"
        extra={result?.asset.latestDate ? <Text type="secondary">最新信号日：{result.asset.latestDate}</Text> : null}
      >
        {result ? (
          <>
            <div className="trade-decision-summary">
              <div>
                <Text type="secondary">综合倾向</Text>
                <strong>{result.summary.label}</strong>
              </div>
              <Text>{result.summary.description}</Text>
            </div>
            <Table
              rowKey="strategyId"
              columns={columns}
              dataSource={result.items}
              loading={loading}
              pagination={false}
              scroll={{ x: 1160 }}
              locale={{
                emptyText: (
                  <EmptyState
                    title="暂无可用策略"
                    description="该标的暂无非归档且已成功评估的策略，可以手动添加其他标的策略。"
                    compact
                  />
                ),
              }}
            />
          </>
        ) : (
          <EmptyState title="请选择标的并查询" description="交易决策会按回测实验室总评分从高到低展示。" />
        )}
      </Card>

      <Modal
        title="添加其他标的策略"
        open={extraModalOpen}
        onOk={handleConfirmExtraStrategies}
        onCancel={() => setExtraModalOpen(false)}
        okText="加入并查询"
        cancelText="取消"
        width={720}
      >
        <Select
          mode="multiple"
          showSearch
          className="full-width"
          loading={loadingExtra}
          value={extraStrategyIds}
          options={extraStrategyOptions.map((item) => ({
            label: item.label,
            value: item.strategyId,
          }))}
          onChange={setExtraStrategyIds}
          placeholder="选择其他已通过回测实验室评估的策略"
          filterOption={(input, option) => String(option?.label ?? "").toLowerCase().includes(input.toLowerCase())}
        />
      </Modal>
    </AppShell>
  );
}
