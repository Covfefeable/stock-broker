from __future__ import annotations

from app.services.agent.rule_definitions import AGENT_STRATEGY_INTENTS


def _agent_mode_label(mode: str | None) -> str:
    return {
        "continue_best": "延续最佳",
        "refine_recent": "优化近期",
        "explore_new": "探索新结构",
        "mutate": "突变",
    }.get(str(mode or "").strip().lower(), "探索新结构")


def _agent_intent_label(intent: str | None) -> str:
    return AGENT_STRATEGY_INTENTS.get(str(intent or "").strip().lower(), "趋势跟随")


