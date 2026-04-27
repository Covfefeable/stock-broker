"use client";

import { ArrowLeftOutlined, DownloadOutlined, SaveOutlined, UploadOutlined } from "@ant-design/icons";
import { Button, Card, Form, Input, Modal, Radio, Select, Space, Typography, message } from "antd";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppLoader } from "@/components/app-loader";
import { AppShell } from "@/components/app-shell";
import type { CountryOption, IndexDailyCoverage, StockDailyCoverage, SyncEnqueueResponse } from "@/components/data-center/types";
import { RuleEngine, createDefaultStrategyDslConfig, normalizeStrategyDslConfig } from "@/components/strategy-builder/rule-engine";
import type { StrategyDslConfig, StrategyPreviewResult } from "@/components/strategy-builder/types";
import { getAccessToken } from "@/lib/auth";
import { apiGet, apiPost, apiPut } from "@/lib/api";

const { Text, Title } = Typography;

type AssetType = "stock" | "index";

type AssetOption = {
  label: string;
  value: string;
  ticker: string;
  exchangeCode?: string;
  name: string;
};

type StrategyDetail = {
  id: number;
  name: string;
  type: string;
  source: string;
  countryRegion: string;
  assetType: AssetType;
  assetIdentifier: string;
  assetName?: string | null;
  strategyConfig?: Partial<StrategyDslConfig> | null;
  annualReturn?: string | null;
  drawdown?: string | null;
};

type StrategyDetailResponse = {
  strategy: StrategyDetail;
};

type EditStrategyFormValues = {
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
  { label: "均值回归", value: "均值回归" },
  { label: "套利", value: "套利" },
  { label: "资产配置", value: "资产配置" },
];

function mergeStrategyConfig(input?: Partial<StrategyDslConfig> | null): StrategyDslConfig {
  return normalizeStrategyDslConfig(input);
}

export default function StrategyDetailPage() {
  const params = useParams<{ id: string }>();
  const strategyId = Number(params.id);
  const [messageApi, contextHolder] = message.useMessage();
  const [modal, modalHolder] = Modal.useModal();
  const [form] = Form.useForm<EditStrategyFormValues>();
  const router = useRouter();

  const [loadingPage, setLoadingPage] = useState(true);
  const [loadingCountries, setLoadingCountries] = useState(true);
  const [loadingAssets, setLoadingAssets] = useState(false);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [countryOptions, setCountryOptions] = useState<CountryOption[]>([]);
  const [assetOptions, setAssetOptions] = useState<AssetOption[]>([]);
  const [selectedCountryLabel, setSelectedCountryLabel] = useState<string>();
  const [strategyDetail, setStrategyDetail] = useState<StrategyDetail | null>(null);
  const [pendingAssetIdentifier, setPendingAssetIdentifier] = useState<string>();
  const [strategyDsl, setStrategyDsl] = useState<StrategyDslConfig>(() => createDefaultStrategyDslConfig());
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewResult, setPreviewResult] = useState<StrategyPreviewResult | null>(null);
  const importDslInputRef = useRef<HTMLInputElement | null>(null);

  const assetType = Form.useWatch("assetType", form);
  const countryCode = Form.useWatch("countryCode", form);

  const pageTitle = useMemo(() => (strategyDetail?.name ? `编辑策略 - ${strategyDetail.name}` : "编辑策略"), [strategyDetail?.name]);

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

  const loadStrategyDetail = useCallback(async () => {
    if (!Number.isFinite(strategyId)) {
      messageApi.error("策略参数无效。");
      router.replace("/strategy-builder");
      return;
    }

    setLoadingPage(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<StrategyDetailResponse>(`/strategies/${strategyId}`, token);
      setStrategyDetail(response.strategy);
      setStrategyDsl(mergeStrategyConfig(response.strategy.strategyConfig));
      setPreviewResult(null);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载策略详情失败");
      router.replace("/strategy-builder");
    } finally {
      setLoadingPage(false);
    }
  }, [messageApi, router, strategyId]);

  useEffect(() => {
    void loadCountryOptions();
    void loadStrategyDetail();
  }, [loadCountryOptions, loadStrategyDetail]);

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
      content: string,
      nextCountryCode?: string,
      asset?: AssetOption,
    ) => {
      if (syncHint === "stock_list") {
        modal.info({
          title: "需要先同步股票清单",
          content,
          okText: "知道了",
        });
        return;
      }

      modal.confirm({
        title: "需要同步数据",
        content,
        okText: "去同步",
        cancelText: "取消",
        onOk: async () => {
          setSyncing(true);
          try {
            if (syncHint === "exchange_list") {
              await enqueueSync({ syncItem: "exchange_list" });
              return;
            }
            if (syncHint === "index_list" && nextCountryCode) {
              await enqueueSync({ syncItem: "index_list", countryCode: nextCountryCode });
              return;
            }
            if (syncHint === "stock_daily_history" && asset?.exchangeCode) {
              await enqueueSync({
                syncItem: "stock_daily_history",
                exchangeCode: asset.exchangeCode,
                ticker: asset.ticker,
                dateMode: "auto_fill",
              });
              return;
            }
            if (syncHint === "index_daily_history" && nextCountryCode) {
              await enqueueSync({
                syncItem: "index_daily_history",
                countryCode: nextCountryCode,
                ticker: asset?.ticker ?? "",
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
            promptSync("stock_daily_history", `当前股票 ${selected.name} 尚未同步历史日线，是否立即同步？`, nextCountryCode, selected);
          }
          return;
        }

        const response = await apiGet<{ coverage: IndexDailyCoverage }>(
          `/data-center/index-daily-coverage?countryCode=${encodeURIComponent(nextCountryCode)}&ticker=${encodeURIComponent(selected.ticker)}`,
          token,
        );
        if (!response.coverage.latestDate) {
          promptSync("index_daily_history", `当前指数 ${selected.name} 尚未同步历史日线，是否立即同步？`, nextCountryCode, selected);
        }
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "检查历史日线覆盖情况失败");
      }
    },
    [assetOptions, messageApi, promptSync],
  );

  useEffect(() => {
    if (!strategyDetail || countryOptions.length === 0) {
      return;
    }

    const matchedCountry =
      countryOptions.find((item) => item.label === strategyDetail.countryRegion) ??
      countryOptions.find((item) => item.value === strategyDetail.countryRegion);

    form.setFieldsValue({
      name: strategyDetail.name,
      type: strategyDetail.type,
      countryCode: matchedCountry?.value,
      assetType: strategyDetail.assetType,
      assetIdentifier: undefined,
    });
    setSelectedCountryLabel(matchedCountry?.label ?? strategyDetail.countryRegion);
    setPendingAssetIdentifier(strategyDetail.assetIdentifier);
  }, [countryOptions, form, strategyDetail]);

  useEffect(() => {
    form.setFieldValue("assetIdentifier", undefined);
    setAssetOptions([]);
    if (countryCode && assetType) {
      void loadAssetOptions(countryCode, assetType);
    }
  }, [assetType, countryCode, form, loadAssetOptions]);

  useEffect(() => {
    if (!pendingAssetIdentifier || assetOptions.length === 0) {
      return;
    }

    const matched = assetOptions.find((item) => item.value === pendingAssetIdentifier);
    if (matched) {
      form.setFieldValue("assetIdentifier", matched.value);
      setPendingAssetIdentifier(undefined);
    }
  }, [assetOptions, form, pendingAssetIdentifier]);

  const handleCountryChange = (value: string) => {
    const match = countryOptions.find((item) => item.value === value);
    setSelectedCountryLabel(match?.label);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const selected = assetOptions.find((item) => item.value === values.assetIdentifier);
      setSaving(true);
      const token = getAccessToken();
      await apiPut<{ message: string; strategy: { id: number } }>(
        `/strategies/${strategyId}`,
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
      messageApi.success("策略已更新。");
      await loadStrategyDetail();
    } catch (error) {
      if (error instanceof Error && error.message.startsWith("请输入")) {
        messageApi.error(error.message);
        return;
      }
      if ((error as { errorFields?: unknown[] })?.errorFields) {
        return;
      }
      messageApi.error(error instanceof Error ? error.message : "更新策略失败");
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
          strategyId,
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

  const handleExportDsl = () => {
    const fileName = `${sanitizeFileName(strategyDetail?.name || "strategy")}-dsl.json`;
    const content = JSON.stringify(strategyDsl, null, 2);
    const blob = new Blob([content], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleImportDslFile = async (file?: File) => {
    if (!file) return;
    try {
      const content = await file.text();
      const parsed = JSON.parse(content) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("DSL 文件内容必须是 JSON 对象。");
      }
      const payload = parsed as { strategy?: Partial<StrategyDslConfig>; strategyConfig?: Partial<StrategyDslConfig> };
      const importedDsl = normalizeStrategyDslConfig(payload.strategyConfig ?? payload.strategy ?? (parsed as Partial<StrategyDslConfig>));
      setStrategyDsl(importedDsl);
      setPreviewResult(null);
      messageApi.success("DSL 已导入，请预览确认收益后再保存。");
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "导入 DSL 失败，请检查文件格式。");
    } finally {
      if (importDslInputRef.current) {
        importDslInputRef.current.value = "";
      }
    }
  };

  if (loadingPage) {
    return (
      <AppShell>
        {contextHolder}
        {modalHolder}
        <div className="app-loader-fullscreen">
          <AppLoader message="正在加载策略" fullscreen={false} />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      {contextHolder}
      {modalHolder}
      <section className="dashboard-heading">
        <div>
          <Title level={1}>{pageTitle}</Title>
          <Text className="page-description">查看并编辑单一股票/指数策略，保存后可继续回测与迭代。</Text>
        </div>
        <Space>
          <Button icon={<ArrowLeftOutlined />} href="/strategy-builder">
            返回列表
          </Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving || syncing} onClick={() => void handleSubmit()}>
            保存修改
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
                onChange={handleCountryChange}
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
                  !countryCode ? "请先选择国家/地区" : assetType === "index" ? "请选择指数" : "请选择股票"
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

      <Card
        className="dashboard-card strategy-rule-placeholder-card"
        title="规则引擎"
        bordered
        extra={
          <Space>
            <Button icon={<DownloadOutlined />} onClick={handleExportDsl}>
              导出 DSL
            </Button>
            <Button icon={<UploadOutlined />} onClick={() => importDslInputRef.current?.click()}>
              导入 DSL
            </Button>
            <input
              ref={importDslInputRef}
              accept="application/json,.json"
              className="hidden-file-input"
              type="file"
              onChange={(event) => void handleImportDslFile(event.target.files?.[0])}
            />
          </Space>
        }
      >
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

function sanitizeFileName(value: string): string {
  return value.trim().replace(/[\\/:*?"<>|]+/g, "_") || "strategy";
}
