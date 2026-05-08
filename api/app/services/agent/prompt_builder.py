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
- 优先考虑把基础趋势因子与归一化波动、区间位置、跳空幅度、RSI、MACD、KDJ、BIAS、highest/lowest、std、pct_change、ema、pct_slope、zscore、percentile_rank、drawdown_from_high 等组合起来，寻找更不容易过拟合的结构。
- 每次 analysis 必须说明本轮是否使用了非基础因子；如果仍然主要使用 close/MA，必须解释为什么这样比使用其他因子更合理。

返回 JSON 顶层字段协议：
- mode：必须是 continue_best、refine_recent、explore_new、mutate 之一。
- intent：必须是上方交易风格枚举之一。
- analysis：字符串，必须分析历史表现、tradeCount、timeRobustness、买入持有基准、本轮选择原因、是否使用非基础因子。
- plan：字符串，必须说明本轮 intent 如何落到 DSL，以及预计会怎样改变真实交易行为。
- strategy：对象，只能包含 entryRules、exitRules、risk。
- 不要输出 markdown、注释、自然语言前后缀或 JSON 以外的内容。

规则列表说明：
- entryRules 和 exitRules 都是按顺序判断的优先级列表，不要在规则之间设置 and/or。
- entryRules 可以包含多条买入规则，exitRules 也可以包含多条卖出规则；不要默认只生成一条买入规则。
- 每天先判断 exitRules，再判断 entryRules；同一侧从上到下命中第一条就执行，后续规则不再执行。
- 如果存在不同买入场景，例如趋势突破、趋势回踩、低吸反转、动能加速、波动收敛后突破，应优先拆成 2 到 4 条 entryRules，并按优先级排序，而不是全部塞进一条巨大的 or 条件。
- 多条买入规则可以使用不同 action.size；例如强确认买入 0.6，回踩试仓买入 0.3，突破加仓买入 0.4。
- 只有当本轮确实只存在一个清晰买入场景时，才返回单条 entryRules；否则应主动使用多条买入规则探索更多入场路径。
- 每条规则内部仍然使用 conditions 里的 and/or/嵌套条件组表达复杂逻辑。
- 每一条规则的 conditions 必须永远是 {{"type": "group", "logic": "and 或 or", "children": [...]}}。
- 禁止把单个 condition 直接放到规则的 conditions 上；即使只有一个条件，也必须包在 group.children 里。
- action.size 表示本次仓位变化比例，0.33 表示买入或卖出 33% 总资金仓位，1 表示 100%；卖出 1 等同于清仓。
- action.type 只能是 buy 或 sell；entryRules 中只能是 buy，exitRules 中只能是 sell。
- action.size 必须是大于 0 且小于等于 1 的 JSON 数字，不能写成字符串、百分号、70、100 或中文。
- 买入实际执行数量为 min(规则要求买入仓位, 剩余可用仓位)，因此不会超过满仓。
- 卖出实际执行数量为 min(规则要求卖出仓位, 当前持仓仓位)，因此不会卖空。
- 买入和卖出的仓位比例必须写在每条规则自己的 action.size 里，不存在全局买入仓位。
- 止损、止盈、最长持仓等退出逻辑也必须表达成高优先级卖出规则，不能放在 risk 或额外字段里。
- 不要描述或依赖 DSL 无法表达的隐藏状态，例如“持仓以来最高价”“真实追踪止损”“移动止盈水位”；如果要近似，只能使用可用字段、函数和表达式规则表达。

DSL 结构硬性要求，违反任何一条都会被系统拒绝：
- strategy 里只能使用 entryRules / exitRules / risk，不要返回旧字段 entry 或 exit。
- entryRules 和 exitRules 都必须是数组，数组内每项必须包含 name、action、conditions。
- mode 只能是 continue_best、refine_recent、explore_new、mutate 之一；intent 只能从上方 intent 枚举中选择英文值，不能写中文。
- conditions 的 type 必须是 group；group.logic 只能是 and 或 or；group.children 里才能放 condition 或子 group，且 children 不能为空。
- condition 必须同时包含 type、leftExpression、operator、rightExpression。
- condition.operator 只能是 >、>=、<、<=、==、!=、cross_over、cross_under 之一，不能写中文、英文描述或符号以外的词。
- leftExpression 和 rightExpression 必须是表达式 token 数组，不能是字符串、对象或数字。
- 表达式 token 的语法是一个小型中缀表达式语法：Expression = Operand (ArithmeticOperator Operand)*。
- Operand 只能是 variable、number、function，或由 groupStart / Expression / groupEnd 包裹的表达式。
- token.type 只能是 variable、number、operator、groupStart、groupEnd、function。
- variable token：type 必须是 variable；name 必须使用“可用字段”中的英文 value；offset 可省略，只能是 <= 0 的整数。
- number token：type 必须是 number；value 必须是 JSON 数字，不能是字符串、百分号或中文。
- operator token：type 必须是 operator；value 只能是 +、-、*、/；它只用于表达式内部算术，不能用于条件比较。
- function token：type 必须是 function；name 必须是可用函数名；args 必须是表达式 token 数组的数组。
- 函数名只能放在 function.name，不能放在 token.type；字段名只能放在 variable.name，不能放在 token.type。
- 可用函数只有 abs、min、max、sum、avg、std、highest、lowest、change、pct_change、ema、pct_slope、zscore、percentile_rank、drawdown_from_high；不要使用 ma、sma、if、and、or、cross、rank 等未列出的函数。
- 函数参数个数必须匹配：abs 1 个；min/max 2 个；sum/avg/std/highest/lowest/change/pct_change/ema/pct_slope/zscore/percentile_rank/drawdown_from_high 2 个。
- sum/avg/std/highest/lowest/change/pct_change/ema/pct_slope/zscore/percentile_rank/drawdown_from_high 的第 2 个参数必须是单个正整数 number token 的表达式数组。
- 如果需要移动平均，请优先使用字段 ma5/ma10/ma20/ma60/ma120；如需自定义窗口，可使用 avg(close, n) 或 ema(close, n) 的 function token。
- 表达式数组不能为空；不能连续出现两个 Operand；二元 operator 前后都必须有 Operand。
- 允许一元 + 或 -，但只允许出现在表达式开头、operator 之后或 groupStart 之后；负数阈值优先直接写成 number.value。
- groupStart 和 groupEnd 必须成对出现，不能用字符串 "(" 或 ")" 代替。
- 条件比较由 condition.operator 表达，表达式 token 内禁止出现 >、>=、<、<=、==、!=、cross_over、cross_under。
- 量纲必须一致：收益率字段和收益率阈值比较，价格字段和价格表达式比较，atr14_pct、range_pct、gap_pct、volatility_20d 等比例字段不能直接和价格字段比较。
- 规则的 conditions 必须永远是 group；即使只有一个条件，也要放在 group.children 中。

要求：
- 买入规则里不要使用持仓收益率和持仓天数
- 不允许引用未来数据，任何变量 offset 都必须小于等于 0
- 窗口函数的窗口参数 n 必须是正整数数字 token
- 可以选择简单规则或复杂规则，不要被固定模板束缚
- 可以尝试趋势、突破、反转、动量、震荡过滤等不同思路
- 条件数量建议 1 到 6 个，必要时允许使用嵌套条件组
- 规则需要可读、合理，不要返回空 children
- 必须比较“策略目标”和“买入持有基准”，避免生成明显弱于买入持有基准的平庸策略

DSL 能力说明：
- entryRules 和 exitRules 支持多条规则，并按列表顺序命中第一条；请把更重要、更紧急的规则放在更靠前的位置。
- 多个买入场景应优先拆成多条 entryRules，例如趋势突破、回踩确认、低波动突破、低位反转分别成为独立规则，而不是全部塞进一个巨大 or 条件。
- 多个卖出场景应优先拆成多条 exitRules，例如风险退出、动能衰退、仓位过高减仓、浮盈保护分别成为独立规则。
- 可以使用 position_ratio 做仓位控制。position_ratio 范围是 0 到 1，例如当前仓位大于 0.7 时卖出 0.3，或当前仓位低于 0.5 时允许继续买入。
- 可以使用 position_return、holding_days、days_since_last_trade 做持仓状态控制。position_return 只适合卖出规则；days_since_last_trade 可用于控制交易冷却期，避免过度连续买卖。
- action.size 是本条规则要执行的仓位比例；买入会自动限制在剩余可用仓位内，卖出会自动限制在当前持仓内，不会超过满仓，也不会卖空。
- leftExpression 和 rightExpression 可以是组合表达式，不限于单个字段；可以用算术 token 与函数组合表达 close / ema(close, 20) - 1、zscore(range_pct, 60)、drawdown_from_high(close, 60)、percentile_rank(volatility_20d, 120) 等结构。
- offset 可用于历史引用，但只能小于等于 0，例如 close[-1]、rsi14[-3]；不得使用未来数据。
- pct_slope(x, n) 用比例口径判断趋势斜率或指标改善，zscore(x, n) 用于判断历史极端程度，percentile_rank(x, n) 用于判断历史分位，drawdown_from_high(x, n) 用于判断相对近期高点的回撤。
- 量纲必须严格匹配：atr14_pct、range_pct、gap_pct、volatility_20d、bias_ma20、position_return 都是比例，阈值应写 0.02 这种小数；rsi14、kdj_k、kdj_d 是 0 到 100；position_ratio 是 0 到 1。
- 价格字段只能和价格类表达式比较，比例字段只能和比例类表达式比较；不要把价格、比例、振荡指标混在同一个比较条件里。
- 只输出 JSON 本身
""".strip()


