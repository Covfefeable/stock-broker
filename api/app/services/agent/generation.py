from __future__ import annotations

import json
from typing import Any

from app.models.agent_task import AgentTask
from app.services.agent.prompt_builder import _build_generation_prompt
from app.services.agent.rule_definitions import AGENT_STRATEGY_INTENTS
from app.services.llm import AIClientError, call_chat_completion_content
from app.services.strategies import StrategyError
from app.services.strategies import _validate_strategy_config as _validate_token_strategy_config


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
    retry_feedback = ""

    for attempt in range(1, AI_DSL_GENERATION_RETRY_COUNT + 1):
        content = ""
        try:
            user_prompt = prompt
            if retry_feedback:
                user_prompt = (
                    f"{prompt}\n\n上一次生成被系统拒绝，请修正后重新输出完整 JSON。\n"
                    f"拒绝原因：{retry_feedback}\n"
                    "请按 DSL 语法协议重新生成：表达式必须符合 Operand (ArithmeticOperator Operand)*，"
                    "字段只能是 variable token，函数只能是 function token，函数参数必须是表达式数组的数组，"
                    "规则 conditions 必须始终是 group。"
                )
            content = call_chat_completion_content(
                model_config,
                [
                    {
                        "role": "system",
                        "content": (
                            "你是一名量化研究员，负责为单一股票、ETF或指数生成可执行的 JSON 策略 DSL。"
                            "只能返回 JSON，不要包含 markdown，不要输出解释。"
                            "生成结果必须严格遵守用户消息中的 DSL 字段协议和表达式语法协议。"
                        ),
                    },
                    {"role": "user", "content": user_prompt},
                ],
                timeout=180,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            generation_payload = _parse_strategy_generation_payload(content)
            strategy_config = generation_payload["strategyConfig"]
            strategy_config["risk"] = _build_fixed_risk_config(task, generation_payload.get("intent"))
            _validate_strategy_config(strategy_config)
            generation_payload["strategyConfig"] = strategy_config
            return generation_payload
        except AIClientError as exc:
            last_error = AgentGenerationError(str(exc))
        except AgentGenerationError as exc:
            _log_invalid_generated_dsl(task, research_state, attempt, content, exc)
            last_error = exc
            retry_feedback = str(exc)

    raise AgentGenerationError(
        f"AI 连续 {AI_DSL_GENERATION_RETRY_COUNT} 次生成 DSL 失败，最后一次原因：{last_error}"
    )


def _log_invalid_generated_dsl(
    task: AgentTask,
    research_state: dict,
    attempt: int,
    content: str,
    error: Exception,
) -> None:
    print(
        (
            "[agent-generated-dsl-invalid] "
            f"task_id={task.id} iteration={research_state.get('iteration')} "
            f"attempt={attempt}/{AI_DSL_GENERATION_RETRY_COUNT} error={error}"
        ),
        flush=True,
    )
    if not content:
        print("[agent-generated-dsl-invalid] empty model response", flush=True)
        return
    try:
        normalized = _strip_json_fence(content)
        parsed = json.loads(normalized)
        print(json.dumps(parsed, ensure_ascii=False, indent=2), flush=True)
    except Exception:
        print(content, flush=True)


def _strip_json_fence(content: str) -> str:
    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = normalized.strip("`")
        normalized = normalized.replace("json", "", 1).strip()
    return normalized


def _parse_strategy_generation_payload(content: str) -> dict:
    normalized = _strip_json_fence(content)
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


def _default_conflict_policy_for_intent(intent: str | None) -> str:
    if intent in {"dip_buying", "mean_reversion", "range_trading"}:
        return "allow_reentry"
    return "exit_first"


def _build_fixed_risk_config(task: AgentTask, intent: str | None = None) -> dict:
    return {
        "forceCloseOnEnd": True,
        "backtestStartDate": task.backtest_start_date.isoformat(),
        "backtestEndDate": task.backtest_end_date.isoformat(),
        "conflictPolicy": _default_conflict_policy_for_intent(intent),
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
