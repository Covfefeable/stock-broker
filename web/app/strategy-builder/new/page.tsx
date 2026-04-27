"use client";

import { ArrowLeftOutlined, SaveOutlined } from "@ant-design/icons";
import { Button, Card, Form, Input, Modal, Radio, Select, Space, Typography, message } from "antd";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import type { CountryOption, IndexDailyCoverage, StockDailyCoverage, SyncEnqueueResponse } from "@/components/data-center/types";
import { RuleEngine, createDefaultStrategyDslConfig, normalizeStrategyDslConfig } from "@/components/strategy-builder/rule-engine";
import type { StrategyDslConfig, StrategyPreviewResult } from "@/components/strategy-builder/types";
import { getAccessToken } from "@/lib/auth";
import { apiGet, apiPost } from "@/lib/api";

const { Text, Title } = Typography;

type AssetType = "stock" | "index";

type AssetOption = {
  label: string;
  value: string;
  ticker: string;
  exchangeCode?: string;
  name: string;
  latestDate?: string | null;
};

type CreateStrategyFormValues = {
  name: string;
  type: string;
  countryCode?: string;
  assetType?: AssetType;
  assetIdentifier?: string;
};

const strategyTypeOptions = [
  { label: "动量", value: "动量" },
  { label: "趋势", value: "趋势" },
  { label: "价值", value: "价值" },
  { label: "事件驱动", value: "事件驱动" },
  { label: "低波动", value: "低波动" },
  { label: "成长", value: "成长" },
  { label: "资产配置", value: "资产配置" },
];

export default function NewStrategyPage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [modal, modalHolder] = Modal.useModal();
  const [form] = Form.useForm<CreateStrategyFormValues>();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [loadingCountries, setLoadingCountries] = useState(true);
  const [loadingAssets, setLoadingAssets] = useState(false);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [countryOptions, setCountryOptions] = useState<CountryOption[]>([]);
  const [assetOptions, setAssetOptions] = useState<AssetOption[]>([]);
  const [strategyDsl, setStrategyDsl] = useState<StrategyDslConfig>(() => createDefaultStrategyDslConfig());
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewResult, setPreviewResult] = useState<StrategyPreviewResult | null>(null);
  const [pendingPrefillAssetIdentifier, setPendingPrefillAssetIdentifier] = useState<string | null>(null);

  const assetType = Form.useWatch("assetType", form);
  const countryCode = Form.useWatch("countryCode", form);

  const loadCountryOptions = useCallback(async () => {
    setLoadingCountries(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ items: CountryOption[] }>("/data-center/country-options", token);
      setCountryOptions(response.items);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载国家/地区失败");
    } finally {
      setLoadingCountries(false);
    }
  }, [messageApi]);

  useEffect(() => {
    void loadCountryOptions();
  }, [loadCountryOptions]);

  useEffect(() => {
    const prefillKey = searchParams.get("prefill");
    if (!prefillKey || typeof window === "undefined") {
      return;
    }
    const raw = window.localStorage.getItem(prefillKey);
    if (!raw) {
      return;
    }
    try {
      const draft = JSON.parse(raw) as Partial<CreateStrategyFormValues> & {
        countryCode?: string;
        strategyConfig?: StrategyDslConfig;
      };
      form.setFieldsValue({
        name: draft.name,
        type: draft.type,
        countryCode: draft.countryCode,
        assetType: draft.assetType,
      });
      if (draft.strategyConfig) {
        setStrategyDsl(normalizeStrategyDslConfig(draft.strategyConfig));
      }
      if (draft.assetIdentifier) {
        setPendingPrefillAssetIdentifier(draft.assetIdentifier);
      }
      window.localStorage.removeItem(prefillKey);
      messageApi.success("已填入 AI 生成的策略草稿，检查后点击保存即可新建。");
    } catch {
      messageApi.error("读取策略草稿失败。");
    }
  }, [form, messageApi, searchParams]);

  const enqueueSync = useCallback(
    async (
      payload:
        | { syncItem: "exchange_list" }
        | { syncItem: "index_list"; countryCode: string }
        | { syncItem: "stock_daily_history"; exchangeCode: string; ticker: string; dateMode: "auto_fill" }
        | { syncItem: "index_daily_history"; countryCode: string; ticker: string; dateMode: "auto_fill" },
    ) => {
      const token = getAccessToken();
      const response = await apiPost<SyncEnqueueResponse>("/data-center/sync", payload, token);
      messageApi.success(`${response.message}，请稍后再回来继续配置。`);
    },
    [messageApi],
  );

  const promptSync = useCallback(
    (
      syncHint: "exchange_list" | "stock_list" | "index_list" | "stock_daily_history" | "index_daily_history",
      detailMessage: string,
      nextCountryCode: string,
      nextAsset?: AssetOption,
    ) => {
      if (syncHint === "stock_list") {
        modal.info({
          title: "当前国家/地区还没有股票清单",
          content: `${detailMessage} 请先前往数据中心同步对应交易所的股票清单。`,
          okText: "知道了",
        });
        return;
      }

      modal.confirm({
        title:
          syncHint === "exchange_list"
            ? "当前国家/地区还没有交易所数据"
            : syncHint === "index_list"
              ? "当前国家/地区还没有指数清单"
              : syncHint === "stock_daily_history"
                ? "该股票尚未同步历史日线"
                : "该指数尚未同步历史日线",
        content:
          syncHint === "exchange_list"
            ? "是否现在同步交易所清单？同步完成后再回来选择股票即可。"
            : syncHint === "index_list"
              ? "是否现在同步指数清单？同步完成后再回来选择指数即可。"
              : detailMessage,
        okText: "同步",
        cancelText: "取消",
        onOk: async () => {
          setSyncing(true);
          try {
            if (syncHint === "exchange_list") {
              await enqueueSync({ syncItem: "exchange_list" });
            } else if (syncHint === "index_list") {
              await enqueueSync({ syncItem: "index_list", countryCode: nextCountryCode });
            } else if (syncHint === "stock_daily_history" && nextAsset?.exchangeCode) {
              await enqueueSync({
                syncItem: "stock_daily_history",
                exchangeCode: nextAsset.exchangeCode,
                ticker: nextAsset.ticker,
                dateMode: "auto_fill",
              });
            } else if (syncHint === "index_daily_history") {
              await enqueueSync({
                syncItem: "index_daily_history",
                countryCode: nextCountryCode,
                ticker: nextAsset?.ticker || "",
                dateMode: "auto_fill",
              });
            }
          } finally {
            setSyncing(false);
          }
        },
      });
    },
    [enqueueSync, modal],
  );

  const loadAssetOptions = useCallback(
    async (nextCountryCode?: string, nextAssetType?: AssetType) => {
      if (!nextCountryCode || !nextAssetType) {
        setAssetOptions([]);
        return;
      }

      setLoadingAssets(true);
      try {
        const token = getAccessToken();
        const response = await apiGet<{
          items: AssetOption[];
          syncHint: "exchange_list" | "stock_list" | "index_list" | null;
          message: string | null;
        }>(
          `/strategies/asset-options?countryCode=${encodeURIComponent(nextCountryCode)}&assetType=${encodeURIComponent(nextAssetType)}`,
          token,
        );
        setAssetOptions(response.items);
        if (response.items.length === 0 && response.syncHint && response.message) {
          promptSync(response.syncHint, response.message, nextCountryCode);
        }
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载股票/指数选项失败");
      } finally {
        setLoadingAssets(false);
      }
    },
    [messageApi, promptSync],
  );

  const checkAssetCoverage = useCallback(
    async (nextCountryCode: string, nextAssetType: AssetType, nextAssetValue: string) => {
      const selected = assetOptions.find((item) => item.value === nextAssetValue);
      if (!selected) {
        return;
      }

      try {
        const token = getAccessToken();
        if (nextAssetType === "stock") {
          const response = await apiGet<{ coverage: StockDailyCoverage }>(
            `/data-center/stock-daily-coverage?exchangeCode=${encodeURIComponent(selected.exchangeCode || "")}&ticker=${encodeURIComponent(selected.ticker)}`,
            token,
          );
          if (!response.coverage.latestDate) {
            promptSync(
              "stock_daily_history",
              "该股票还没有历史日线数据，是否现在同步？同步完成后再回来继续配置即可。",
              nextCountryCode,
              selected,
            );
          }
          return;
        }

        const response = await apiGet<{ coverage: IndexDailyCoverage }>(
          `/data-center/index-daily-coverage?countryCode=${encodeURIComponent(nextCountryCode)}&ticker=${encodeURIComponent(selected.ticker)}`,
          token,
        );
        if (!response.coverage.latestDate) {
          promptSync(
            "index_daily_history",
            "该指数还没有历史日线数据，是否现在同步？同步完成后再回来继续配置即可。",
            nextCountryCode,
            selected,
          );
        }
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "检查历史日线覆盖情况失败");
      }
    },
    [assetOptions, messageApi, promptSync],
  );

  useEffect(() => {
    form.setFieldValue("assetIdentifier", undefined);
    setAssetOptions([]);
    if (countryCode && assetType) {
      void loadAssetOptions(countryCode, assetType);
    }
  }, [assetType, countryCode, form, loadAssetOptions]);

  useEffect(() => {
    if (!pendingPrefillAssetIdentifier || !assetOptions.some((item) => item.value === pendingPrefillAssetIdentifier)) {
      return;
    }
    form.setFieldValue("assetIdentifier", pendingPrefillAssetIdentifier);
    setPendingPrefillAssetIdentifier(null);
  }, [assetOptions, form, pendingPrefillAssetIdentifier]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const selected = assetOptions.find((item) => item.value === values.assetIdentifier);
      setSaving(true);
      const token = getAccessToken();
      const response = await apiPost<{ message: string; strategy: { id: number }; evaluationError?: string | null }>(
        "/strategies",
        {
          name: values.name,
          type: values.type,
          source: "人工创建",
          countryRegion: values.countryCode,
          assetType: values.assetType,
          assetIdentifier: values.assetIdentifier,
          assetName: selected?.name,
          strategyConfig: strategyDsl,
          annualReturn: previewResult?.annualReturn,
          maxDrawdown: previewResult?.maxDrawdown,
        },
        token,
      );
      if (response.evaluationError) {
        messageApi.warning(`策略已保存，但自动评估提交失败：${response.evaluationError}`);
      } else {
        messageApi.success(response.message || "策略已保存，已自动提交全面评估任务。");
      }
      router.push("/strategy-builder");
    } catch (error) {
      if (error instanceof Error) {
        messageApi.error(error.message);
      }
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = async () => {
    try {
      const values = await form.validateFields();
      setPreviewLoading(true);
      const token = getAccessToken();
      const response = await apiPost<{ message: string; preview: StrategyPreviewResult }>(
        "/strategies/preview",
        {
          countryCode: values.countryCode,
          assetType: values.assetType,
          assetIdentifier: values.assetIdentifier,
          strategyConfig: strategyDsl,
        },
        token,
      );
      setPreviewResult(response.preview);
      messageApi.success("收益预览已更新。");
    } catch (error) {
      if ((error as { errorFields?: unknown[] })?.errorFields) {
        return;
      }
      messageApi.error(error instanceof Error ? error.message : "收益预览失败");
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <AppShell>
      {contextHolder}
      {modalHolder}
      <section className="dashboard-heading">
        <div>
          <Title level={1}>新建策略</Title>
          <Text className="page-description">先把策略基础信息和标的范围定下来，规则引擎我们下一步单独细化。</Text>
        </div>
        <Space>
          <Button icon={<ArrowLeftOutlined />} href="/strategy-builder">
            返回列表
          </Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => void handleSubmit()}>
            保存基础信息
          </Button>
        </Space>
      </section>

      <Card className="dashboard-card strategy-form-card" bordered>
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            assetType: "stock",
          }}
        >
          <div className="strategy-form-grid">
            <Form.Item label="策略名称" name="name" rules={[{ required: true, message: "请输入策略名称" }]}>
              <Input placeholder="例如：纳指趋势跟随策略" />
            </Form.Item>

            <Form.Item label="类型" name="type" rules={[{ required: true, message: "请选择策略类型" }]}>
              <Select options={strategyTypeOptions} placeholder="请选择策略类型" />
            </Form.Item>

            <Form.Item label="来源">
              <Input value="人工创建" disabled />
            </Form.Item>

            <Form.Item label="国家/地区" name="countryCode" rules={[{ required: true, message: "请选择国家/地区" }]}>
              <Select
                showSearch
                loading={loadingCountries}
                options={countryOptions}
                optionFilterProp="label"
                placeholder="请选择国家/地区"
              />
            </Form.Item>

            <Form.Item label="股票/指数" name="assetType" rules={[{ required: true, message: "请选择股票或指数" }]}>
              <Radio.Group
                options={[
                  { label: "股票", value: "stock" },
                  { label: "指数", value: "index" },
                ]}
                optionType="button"
                buttonStyle="solid"
              />
            </Form.Item>

            <Form.Item
              label={assetType === "index" ? "指数" : "股票"}
              name="assetIdentifier"
              rules={[{ required: true, message: assetType === "index" ? "请选择指数" : "请选择股票" }]}
            >
              <Select
                showSearch
                loading={loadingAssets}
                options={assetOptions}
                optionFilterProp="label"
                placeholder={
                  !countryCode
                    ? "请先选择国家/地区"
                    : !assetType
                      ? "请先选择股票或指数"
                      : assetType === "index"
                        ? "请选择指数"
                        : "请选择股票"
                }
                onChange={(value: string) => {
                  if (countryCode && assetType) {
                    void checkAssetCoverage(countryCode, assetType, value);
                  }
                }}
              />
            </Form.Item>
          </div>
        </Form>
      </Card>

      <Card className="dashboard-card strategy-rule-placeholder-card" title="规则引擎" bordered>
        <RuleEngine
          value={strategyDsl}
          onChange={setStrategyDsl}
          onPreview={() => void handlePreview()}
          previewLoading={previewLoading}
          previewResult={previewResult}
          previewDisabled={saving || syncing}
        />
      </Card>
    </AppShell>
  );
}
