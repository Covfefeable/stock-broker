"use client";

import { ArrowLeftOutlined, RobotOutlined } from "@ant-design/icons";
import { Button, Card, DatePicker, Form, Input, InputNumber, Modal, Radio, Select, Space, Typography, message } from "antd";
import dayjs from "dayjs";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/app-shell";
import type { AgentTaskDetailResponse } from "@/components/agent-tasks/types";
import type { CountryOption, IndexDailyCoverage, StockDailyCoverage, SyncEnqueueResponse } from "@/components/data-center/types";
import { getAccessToken } from "@/lib/auth";
import { apiGet, apiPost } from "@/lib/api";

const { Title, Text } = Typography;

type AssetType = "stock" | "index";

type AssetOption = {
  label: string;
  value: string;
  ticker: string;
  exchangeCode?: string;
  name: string;
  latestDate?: string | null;
};

type AiModelOption = {
  label: string;
  value: string;
  name: string;
  model: string;
  baseUrl: string;
  apiKey: string;
};

type CreateAgentTaskFormValues = {
  name: string;
  countryCode?: string;
  assetType?: AssetType;
  assetIdentifier?: string;
  aiModelKey?: string;
  note?: string;
  targetAnnualReturn: number;
  maxDrawdownLimit: number;
  minSharpe: number;
  maxIterations: number;
  backtestStartDate: { format: (template: string) => string };
  backtestEndDate: { format: (template: string) => string };
};

export default function NewAgentTaskPage() {
  const searchParams = useSearchParams();
  const [messageApi, contextHolder] = message.useMessage();
  const [modal, modalHolder] = Modal.useModal();
  const [form] = Form.useForm<CreateAgentTaskFormValues>();
  const [countryOptions, setCountryOptions] = useState<CountryOption[]>([]);
  const [assetOptions, setAssetOptions] = useState<AssetOption[]>([]);
  const [aiModelOptions, setAiModelOptions] = useState<AiModelOption[]>([]);
  const [loadingCountries, setLoadingCountries] = useState(true);
  const [loadingAssets, setLoadingAssets] = useState(false);
  const [loadingModels, setLoadingModels] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [loadingCopy, setLoadingCopy] = useState(false);

  const countryCode = Form.useWatch("countryCode", form);
  const assetType = Form.useWatch("assetType", form);

  const loadCountryOptions = useCallback(async () => {
    setLoadingCountries(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ items: CountryOption[] }>("/data-center/country-options", token);
      setCountryOptions(response.items);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载国家/地区失败。");
    } finally {
      setLoadingCountries(false);
    }
  }, [messageApi]);

  const loadAiModelOptions = useCallback(async () => {
    setLoadingModels(true);
    try {
      const token = getAccessToken();
      const response = await apiGet<{ items: AiModelOption[] }>("/agent-tasks/model-options", token);
      setAiModelOptions(response.items);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "加载 AI 模型失败。");
    } finally {
      setLoadingModels(false);
    }
  }, [messageApi]);

  useEffect(() => {
    void loadCountryOptions();
    void loadAiModelOptions();
  }, [loadAiModelOptions, loadCountryOptions]);

  useEffect(() => {
    const copyId = searchParams.get("copyId");
    if (!copyId) {
      return;
    }

    const loadCopySource = async () => {
      setLoadingCopy(true);
      try {
        const token = getAccessToken();
        const response = await apiGet<AgentTaskDetailResponse>(`/agent-tasks/${copyId}`, token);
        const sourceTask = response.task;
        const matchedModel = aiModelOptions.find(
          (item) =>
            item.name === sourceTask.aiModelConfig?.name &&
            item.model === sourceTask.aiModelConfig?.model &&
            item.baseUrl === sourceTask.aiModelConfig?.baseUrl &&
            item.apiKey === sourceTask.aiModelConfig?.apiKey,
        );

        form.setFieldsValue({
          name: `${sourceTask.name}（副本）`,
          countryCode: sourceTask.countryCode,
          assetType: sourceTask.assetType,
          assetIdentifier: sourceTask.assetIdentifier,
          aiModelKey: matchedModel?.value,
          note: sourceTask.note ?? undefined,
          targetAnnualReturn: sourceTask.targetAnnualReturn ?? 20,
          maxDrawdownLimit: sourceTask.maxDrawdownLimit ?? 20,
          minSharpe: sourceTask.minSharpe ?? 0.6,
          maxIterations: sourceTask.maxIterations,
          backtestStartDate: sourceTask.backtestStartDate ? dayjs(sourceTask.backtestStartDate) : dayjs().subtract(5, "year"),
          backtestEndDate: sourceTask.backtestEndDate ? dayjs(sourceTask.backtestEndDate) : dayjs(),
        });
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载复制任务失败。");
      } finally {
        setLoadingCopy(false);
      }
    };

    if (aiModelOptions.length > 0) {
      void loadCopySource();
    }
  }, [aiModelOptions, form, messageApi, searchParams]);

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
      messageApi.success(`${response.message}，请稍后再继续配置。`);
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
            ? "是否现在同步交易所清单？同步完成后再回来选择标的即可。"
            : syncHint === "index_list"
              ? "是否现在同步指数清单？同步完成后再回来选择标的即可。"
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
            } else if (syncHint === "index_daily_history" && nextAsset) {
              await enqueueSync({
                syncItem: "index_daily_history",
                countryCode: nextCountryCode,
                ticker: nextAsset.ticker,
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
          `/agent-tasks/asset-options?countryCode=${encodeURIComponent(nextCountryCode)}&assetType=${encodeURIComponent(nextAssetType)}`,
          token,
        );
        setAssetOptions(response.items);
        if (response.items.length === 0 && response.syncHint && response.message) {
          promptSync(response.syncHint, response.message, nextCountryCode);
        }
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : "加载标的选项失败。");
      } finally {
        setLoadingAssets(false);
      }
    },
    [messageApi, promptSync],
  );

  useEffect(() => {
    form.setFieldValue("assetIdentifier", undefined);
    void loadAssetOptions(countryCode, assetType);
  }, [assetType, countryCode, form, loadAssetOptions]);

  const checkAssetCoverage = useCallback(
    async (nextCountryCode: string, nextAssetType: AssetType, nextAssetValue: string) => {
      const selected = assetOptions.find((item) => item.value === nextAssetValue);
      if (!selected) return;

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
        messageApi.error(error instanceof Error ? error.message : "检查标的数据覆盖情况失败。");
      }
    },
    [assetOptions, messageApi, promptSync],
  );

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const token = getAccessToken();
      setSaving(true);
      const response = await apiPost<{ message: string; task: { id: number } }>(
        "/agent-tasks",
        {
          ...values,
          aiModel: aiModelOptions.find((item) => item.value === values.aiModelKey),
          backtestStartDate: values.backtestStartDate.format("YYYY-MM-DD"),
          backtestEndDate: values.backtestEndDate.format("YYYY-MM-DD"),
        },
        token,
      );
      messageApi.success(response.message);
      window.location.href = `/agent-tasks/${response.task.id}`;
    } catch (error) {
      if ((error as { errorFields?: unknown[] })?.errorFields) return;
      messageApi.error(error instanceof Error ? error.message : "创建 Agent 任务失败。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell>
      {contextHolder}
      {modalHolder}
      <section className="dashboard-heading">
        <div>
          <Title level={1}>新建 Agent 任务</Title>
          <Text className="page-description">设置目标收益和回测约束，让系统围绕单一股票或指数自动迭代策略。</Text>
        </div>
        <Space>
          <Link href="/agent-tasks">
            <Button icon={<ArrowLeftOutlined />}>返回列表</Button>
          </Link>
          <Button
            type="primary"
            icon={<RobotOutlined />}
            loading={saving || syncing}
            onClick={() => void handleSubmit()}
          >
            保存任务
          </Button>
        </Space>
      </section>

      <Form
        form={form}
        layout="vertical"
        initialValues={{
          assetType: "stock",
          maxIterations: 10,
          targetAnnualReturn: 20,
          maxDrawdownLimit: 20,
          minSharpe: 0.6,
          backtestStartDate: dayjs().subtract(5, "year"),
          backtestEndDate: dayjs(),
        }}
      >
        <Card className="dashboard-card strategy-form-card" title="基础信息" bordered>
          <div className="strategy-form-grid">
            <Form.Item label="任务名称" name="name" rules={[{ required: true, message: "请输入任务名称" }]}>
              <Input placeholder="例如：TSLA 趋势 Agent" />
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
            placeholder={!countryCode ? "请先选择国家/地区" : assetType === "index" ? "请选择指数" : "请选择股票"}
            disabled={loadingCopy}
            onChange={(value: string) => {
              if (countryCode && assetType) {
                void checkAssetCoverage(countryCode, assetType, value);
                  }
                }}
              />
            </Form.Item>

            <Form.Item label="AI 模型" name="aiModelKey" rules={[{ required: true, message: "请选择 AI 模型" }]}>
              <Select
                showSearch
                loading={loadingModels}
                options={aiModelOptions}
                optionFilterProp="label"
                placeholder="请选择系统设置中的 AI 模型"
              />
            </Form.Item>
          </div>

          <Form.Item label="备注说明" name="note">
            <Input.TextArea rows={4} placeholder="补充这个 Agent 的目标、约束或观察点（可选）" />
          </Form.Item>
        </Card>

        <Card className="dashboard-card strategy-form-card" title="目标与迭代" bordered>
          <div className="strategy-form-grid">
            <Form.Item label="目标年化收益率" name="targetAnnualReturn" rules={[{ required: true, message: "请输入目标年化收益率" }]}>
              <InputNumber addonAfter="%" min={0} step={0.1} className="strategy-number-input" />
            </Form.Item>

            <Form.Item label="最大可接受回撤" name="maxDrawdownLimit" rules={[{ required: true, message: "请输入最大可接受回撤" }]}>
              <InputNumber addonAfter="%" min={0} step={0.1} className="strategy-number-input" />
            </Form.Item>

            <Form.Item label="最低 Sharpe" name="minSharpe" rules={[{ required: true, message: "请输入最低 Sharpe" }]}>
              <InputNumber min={0} step={0.1} className="strategy-number-input" />
            </Form.Item>

            <Form.Item label="最大迭代次数" name="maxIterations" rules={[{ required: true, message: "请输入最大迭代次数" }]}>
              <InputNumber min={1} step={1} className="strategy-number-input" />
            </Form.Item>
          </div>
        </Card>

        <Card className="dashboard-card strategy-form-card" title="回测参数" bordered>
          <div className="strategy-form-grid">
            <Form.Item label="回测开始日期" name="backtestStartDate" rules={[{ required: true, message: "请选择回测开始日期" }]}>
              <DatePicker className="strategy-number-input" format="YYYY-MM-DD" />
            </Form.Item>

            <Form.Item label="回测结束日期" name="backtestEndDate" rules={[{ required: true, message: "请选择回测结束日期" }]}>
              <DatePicker className="strategy-number-input" format="YYYY-MM-DD" />
            </Form.Item>
          </div>
        </Card>
      </Form>
    </AppShell>
  );
}
