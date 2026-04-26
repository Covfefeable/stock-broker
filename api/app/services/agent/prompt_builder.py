from __future__ import annotations

import json

from app.models.agent_task import AgentTask
from app.services.agent.rule_definitions import AGENT_STRATEGY_INTENTS, RULE_FIELDS, RULE_FUNCTIONS, RULE_OPERATORS


def _compact_rule_items(items: list[dict], *, include_description: bool = False) -> str:
    lines: list[str] = []
    for item in items:
        value = item.get("value") or item.get("name")
        label = item.get("label") or item.get("name") or value
        description = str(item.get("description") or "").strip()
        suffix = f"：{description}" if include_description and description else ""
        lines.append(f"- {value}: {label}{suffix}")
    return "\n".join(lines)


def _compact_agent_intents() -> str:
    return "\n".join(f"- {value}: {label}" for value, label in AGENT_STRATEGY_INTENTS.items())


def _format_agent_memory_block(items: list[str]) -> str:
    if not items:
        return "- 暂无"
    return "\n".join(f"- {item}" for item in items)


def _build_generation_prompt(
    task: AgentTask,
    recent_memories: dict[str, list[str]],
    benchmark_metrics: dict[str, float],
    research_state: dict,
) -> str:
    current_iteration = research_state.get("iteration")
    best_memory_block = _format_agent_memory_block(recent_memories.get("best") or [])
    recent_memory_block = _format_agent_memory_block(recent_memories.get("recent") or [])
    user_note = str(task.note or "").strip() or "无"
    return f"""
请围绕单一标的生成一套策略 JSON DSL，并采用 ReAct 风格：先分析，再决策，最后输出策略。
本轮由你自主选择研究动作。代码不会限制你的模式选择，但研究方向应以探索为主：在策略综合表现没有明确站上买入持有基准之前，不要沉迷微调已有结构。

任务信息：
- 标的名称：{task.asset_name}
- 标的标识：{task.asset_identifier}
- 国家/地区：{task.country_code}
- 标的类型：{task.asset_type}
- 当前是第 {current_iteration} 轮迭代，共 {task.max_iterations} 轮
- 目标年化收益率：{float(task.target_annual_return):.2f}%
- 最大可接受回撤：{float(task.max_drawdown_limit):.2f}%
- 最低 Sharpe：{float(task.min_sharpe):.2f}

用户备注说明：
{user_note}
- 用户备注说明是人工补充的研究意图、偏好或观察点，生成策略时必须认真参考。
- 如果备注说明与可用字段、固定风险参数、DSL 格式或不得使用未来数据的要求冲突，必须以后者为准。

买入持有基准（Buy-and-Hold Benchmark，仅作为对照基准）：
- 定义：在回测开始日按初始资金一次性全仓买入该标的，并一直持有到回测结束；期间不执行买入、卖出、止损、止盈、加仓、减仓或择时规则。
- 用途：它不是当前策略，不是目标约束，也不是你要模仿的交易规则；它只用于衡量主动策略相比“什么都不做的被动持有”是否创造了额外价值。
- 买入持有基准总收益：{benchmark_metrics["benchmarkReturn"]:.2f}%
- 买入持有基准年化收益：{benchmark_metrics["benchmarkAnnualReturn"]:.2f}%
- 买入持有基准最大回撤：{benchmark_metrics["benchmarkMaxDrawdown"]:.2f}%
- 买入持有基准 Sharpe：{benchmark_metrics["benchmarkSharpe"]:.2f}
- 买入持有基准波动率：{benchmark_metrics["benchmarkVolatility"]:.2f}%

可用字段：
{_compact_rule_items(RULE_FIELDS, include_description=True)}

可用运算符：
{_compact_rule_items(RULE_OPERATORS)}

可用函数：
{_compact_rule_items(RULE_FUNCTIONS, include_description=True)}

交易风格枚举 intent，只能选择以下值之一：
{_compact_agent_intents()}

风险参数必须固定为：
{json.dumps({
    "initialCapital": float(task.initial_capital),
    "positionSize": float(task.position_size),
    "stopLoss": float(task.stop_loss),
    "takeProfit": float(task.take_profit),
    "minAddPositionInterval": task.min_add_position_interval,
    "maxHoldingDays": task.max_holding_days,
    "forceCloseOnEnd": True,
    "backtestStartDate": task.backtest_start_date.isoformat(),
    "backtestEndDate": task.backtest_end_date.isoformat(),
}, ensure_ascii=False)}

开始以来最佳的三次表现：
{best_memory_block}

最近的表现：
{recent_memory_block}

研究动作要求：
- continue_best：延续最佳。
- refine_recent：优化近期。
- explore_new：探索新结构。
- mutate：突变。
- 你可以自由选择任何研究动作，也可以参考、组合或反驳历史记忆里的经验；但必须把“是否已经超过买入持有基准”作为选择优化类动作的重要依据。
- 每轮必须先选择一个 intent。intent 表示本轮交易范式，plan 表示该范式如何落到 DSL，二者不能互相替代。
- 如果连续多轮同一 intent 效果不好，应主动考虑切换 intent；如果某个 intent 在历史最佳中表现好，可以沿用，但必须说明原因。
- 默认优先 explore_new 或 mutate，用不同交易范式、不同因子组合、不同入场/出场结构寻找更高上限。
- 只有当历史记忆里已经出现 scoreDiff > 0 的轮次，也就是策略综合分明确高于买入持有基准综合分时，才适合选择 continue_best 或 refine_recent。
- refine_recent 只能用于近期表现已经站上买入持有基准、且问题主要是回撤、Sharpe、交易频率或跨时间稳定性仍需改善的场景；否则应选择 explore_new 或 mutate。
- continue_best 只能用于当前最佳已经站上买入持有基准、且它的结构值得保留时；如果当前最佳仍弱于买入持有基准，只能把它当成参考或反例，不要围绕它做小修小补。
- 如果历史最佳仍未达到目标年化收益率，或 scoreDiff 仍小于等于 0，必须偏向 explore_new 或 mutate，用新结构寻找更高上限。
- 如果历史最佳已经达到目标年化收益率且 scoreDiff > 0，再考虑 continue_best 或 refine_recent，用于巩固收益、降低回撤、提升 Sharpe。
- 重点判断本轮 DSL 是否可能改变真实交易行为，而不只是字面变化。
- tradeCount 是重要观察指标：交易次数过低通常说明买入或卖出条件过于苛刻，不能只看少数交易带来的偶然高收益。
- 不要把交易次数当成硬性阈值；请结合回测区间、标的波动、收益、回撤和 Sharpe 自行判断触发频率是否健康。
- 分析目标达标情况时，请基于历史迭代里的策略表现；买入持有基准只能作为基准参考，不要写成“买入持有基准未达目标所以策略未达标”。
- 历史记忆中的“曲线诊断”用于描述收益曲线形态、相对买入持有基准强弱、错失上涨、有效避险、入场质量、出场质量、仓位行为和风险行为。请据此判断问题到底来自买入过严、买入偏晚、卖出过早、仓位不足、风控过紧还是行情适配不足。
- 历史记忆中的“timeRobustness”是同一策略在近一年、近三年、近五年的轻量跨时间验证，请重点关注哪些区间失败、是否只适配单一行情阶段，以及失败原因是收益不足、回撤过大还是交易次数异常。
- 每次 analysis 必须总结历史记忆中的 timeRobustness：近一年/近三年/近五年通过率或跑赢买入持有基准比例、最差区间、最差原因、是否存在只适配主回测区间的过拟合迹象。
- 如果 timeRobustness 长期较差或最差区间反复集中在某类行情，不要只做细小阈值微调；应主动判断是否需要探索新结构或突变，避免陷入局部最优。
- 不要总是默认使用 close、MA5、MA20、MA60 这类基础价量条件。除非你能说明它们在历史记忆中确实有效，否则应主动探索更丰富的因子和函数。
- 优先考虑把基础趋势因子与波动率、区间位置、量能变化、收益率变化、RSI、MACD、KDJ、ATR、BIAS、highest/lowest、std、pct_change 等组合起来，寻找更不容易过拟合的结构。
- 每次 analysis 必须说明本轮是否使用了非基础因子；如果仍然主要使用 close/MA，必须解释为什么这样比使用其他因子更合理。

返回 JSON，结构必须为：
{{
  "mode": "continue_best 或 refine_recent 或 explore_new 或 mutate",
  "intent": "trend_following 或 trend_pullback 或 breakout 或 mean_reversion 或 dip_buying 或 momentum_acceleration 或 volatility_breakout 或 defensive_timing 或 range_trading",
  "analysis": "先思考历史表现、买入持有基准、曲线诊断、当前目标和本轮选择原因；必须额外分析历史 tradeCount 是否过低、过密；必须总结 timeRobustness 的通过率、最差区间和失败原因，并判断是否过拟合或陷入局部最优；必须说明本轮是否使用非基础因子，若仍以 close/MA 为主则解释原因",
  "plan": "基于本轮 intent 说明准备怎样设计 DSL，以及它预计会怎样改变交易行为",
  "strategy": {{
    "entry": {{
      "type": "group",
      "logic": "and" 或 "or",
      "children": [ 条件或子组 ]
    }},
    "exit": {{
      "type": "group",
      "logic": "and" 或 "or",
      "children": [ 条件或子组 ]
    }},
    "risk": {{
      "initialCapital": number,
      "positionSize": number,
      "stopLoss": number,
      "takeProfit": number,
      "minAddPositionInterval": number,
      "maxHoldingDays": number,
      "backtestStartDate": "YYYY-MM-DD",
      "backtestEndDate": "YYYY-MM-DD"
    }}
  }}
}}

条件节点格式：
{{
  "type": "condition",
  "leftExpression": [
    {{"type": "variable", "name": "close"}}
  ],
  "operator": ">",
  "rightExpression": [
    {{
      "type": "function",
      "name": "highest",
      "args": [
        [{{"type": "variable", "name": "close"}}],
        [{{"type": "number", "value": 60}}]
      ]
    }}
  ]
}}

表达式 token 只能使用：
- {{"type": "variable", "name": "close", "offset": -1}}，offset 可省略，且必须 <= 0
- {{"type": "number", "value": 20}}
- {{"type": "operator", "value": "+"}}，value 只能是 + - * /
- {{"type": "groupStart"}} 和 {{"type": "groupEnd"}}
- {{"type": "function", "name": "avg", "args": [[表达式 tokens], [{{"type": "number", "value": 20}}]]}}

要求：
- 买入规则里不要使用持仓收益率和持仓天数
- 不允许引用未来数据，任何变量 offset 都必须小于等于 0
- 窗口函数的窗口参数 n 必须是正整数数字 token
- 可以选择简单规则或复杂规则，不要被固定模板束缚
- 可以尝试趋势、突破、反转、动量、震荡过滤等不同思路
- 条件数量建议 1 到 6 个，必要时允许使用嵌套条件组
- 规则需要可读、合理，不要返回空 children
- 必须比较“策略目标”和“买入持有基准”，避免生成明显弱于买入持有基准的平庸策略
- 只输出 JSON 本身
""".strip()


