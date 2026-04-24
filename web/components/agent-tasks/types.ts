export type AgentTaskStatus = "queued" | "running" | "success" | "failure";

export type AgentTaskItem = {
  id: number;
  name: string;
  countryCode: string;
  assetType: "stock" | "index";
  assetIdentifier: string;
  assetName: string;
  aiModelName: string;
  aiModelConfig: {
    name?: string;
    model?: string;
    baseUrl?: string;
    apiKey?: string;
  };
  note?: string | null;
  status: AgentTaskStatus;
  maxIterations: number;
  currentIteration: number;
  targetAnnualReturn: number | null;
  maxDrawdownLimit: number | null;
  minSharpe: number | null;
  initialCapital: number | null;
  positionSize: number | null;
  stopLoss: number | null;
  takeProfit: number | null;
  maxHoldingDays: number;
  backtestStartDate: string | null;
  backtestEndDate: string | null;
  bestAnnualReturn: number | null;
  bestSharpe: number | null;
  bestStrategyConfig?: Record<string, unknown> | null;
  bestSummary?: string | null;
  celeryTaskId?: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  createdAt: string | null;
  updatedAt: string | null;
};

export type AgentIterationItem = {
  id: number;
  iterationNumber: number;
  status: string;
  annualReturn: number | null;
  maxDrawdown: number | null;
  sharpe: number | null;
  strategyConfig: Record<string, unknown>;
  memory?: string | null;
  analysis?: string | null;
  actionPlan?: string | null;
  summary: string;
  createdAt: string | null;
};

export type AgentTaskListResponse = {
  items: AgentTaskItem[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
  };
  filters: {
    countryCodes: string[];
    statuses: string[];
  };
};

export type AgentTaskDetailResponse = {
  task: AgentTaskItem;
  iterations: AgentIterationItem[];
};
