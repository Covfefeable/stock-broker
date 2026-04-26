from __future__ import annotations

import json
from typing import Any

from app.models.agent_task import AgentTask
from app.services.agent.prompt_builder import _build_generation_prompt
from app.services.agent.rule_definitions import AGENT_STRATEGY_INTENTS
from app.services.ai_client import AIClientError, call_chat_completion_content
from app.services.strategy_service import StrategyError
from app.services.strategy_service import _validate_strategy_config as _validate_token_strategy_config


AI_DSL_GENERATION_RETRY_COUNT = 3


class AgentGenerationError(ValueError):
    pass


def _generate_strategy_with_ai(
    task: AgentTask,
    recent_memories: dict[str, list[str]],
    benchmark_metrics: dict[str, float],
    research_state: dict,
) -> dict:
    model_config = task.ai_model_config or {}
    if not model_config.get("baseUrl") or not model_config.get("apiKey") or not model_config.get("model"):
        raise AgentGenerationError("Agent 任务缺少有效的 AI 模型配置。")

    prompt = _build_generation_prompt(task, recent_memories, benchmark_metrics, research_state)
    print(
        f"[agent-context] task_id={task.id} iteration={research_state.get('iteration')} chars={len(prompt)}",
        flush=True,
    )
    last_error: AgentGenerationError | None = None

    for attempt in range(1, AI_DSL_GENERATION_RETRY_COUNT + 1):
        try:
            content = call_chat_completion_content(
                model_config,
                [
                    {
                        "role": "system",
                        "content": (
                            "你是一名量化研究员，负责为单一股票或指数生成可执行的 JSON 策略 DSL。"
                            "只能返回 JSON，不要包含 markdown，不要输出解释。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                timeout=180,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            generation_payload = _parse_strategy_generation_payload(content)
            strategy_config = generation_payload["strategyConfig"]
            strategy_config["risk"] = _build_fixed_risk_config(task)
            _validate_strategy_config(strategy_config)
            generation_payload["strategyConfig"] = strategy_config
            return generation_payload
        except AIClientError as exc:
            last_error = AgentGenerationError(str(exc))
        except AgentGenerationError as exc:
            last_error = exc

    raise AgentGenerationError(
        f"AI 连续 {AI_DSL_GENERATION_RETRY_COUNT} 次生成 DSL 失败，最后一次原因：{last_error}"
    )


def _parse_strategy_generation_payload(content: str) -> dict:
    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = normalized.strip("`")
        normalized = normalized.replace("json", "", 1).strip()
    try:
        data = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise AgentGenerationError("AI 返回的策略 DSL 不是合法 JSON。") from exc
    if not isinstance(data, dict):
        raise AgentGenerationError("AI 返回的策略 DSL 结构无效。")
    strategy = data.get("strategy", data)
    if not isinstance(strategy, dict):
        raise AgentGenerationError("AI 返回的策略 DSL 结构无效。")
    plan = str(data.get("plan", data.get("actionPlan", ""))).strip()
    return {
        "mode": _normalize_agent_mode(data.get("mode")),
        "intent": _normalize_agent_intent(data.get("intent")),
        "analysis": str(data.get("analysis", "")).strip(),
        "actionPlan": plan,
        "strategyConfig": strategy,
    }


def _normalize_agent_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    legacy_map = {
        "exploration": "explore_new",
        "exploitation": "continue_best",
        "mutation": "mutate",
    }
    mode = legacy_map.get(mode, mode)
    if mode in {"continue_best", "refine_recent", "explore_new", "mutate"}:
        return mode
    return "explore_new"


def _normalize_agent_intent(value: Any) -> str:
    intent = str(value or "").strip().lower()
    return intent if intent in AGENT_STRATEGY_INTENTS else "trend_following"


def _build_fixed_risk_config(task: AgentTask) -> dict:
    return {
        "initialCapital": float(task.initial_capital),
        "positionSize": float(task.position_size),
        "stopLoss": float(task.stop_loss),
        "takeProfit": float(task.take_profit),
        "minAddPositionInterval": task.min_add_position_interval,
        "maxHoldingDays": task.max_holding_days,
        "forceCloseOnEnd": True,
        "backtestStartDate": task.backtest_start_date.isoformat(),
        "backtestEndDate": task.backtest_end_date.isoformat(),
    }


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result[:4]


def _validate_strategy_config(strategy_config: dict) -> None:
    try:
        _validate_token_strategy_config(strategy_config)
    except StrategyError as exc:
        raise AgentGenerationError(f"AI 返回的策略 DSL 无效：{exc}") from exc


