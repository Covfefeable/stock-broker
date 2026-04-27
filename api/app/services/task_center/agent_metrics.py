from app.models.agent_iteration import AgentIteration
from app.models.agent_task import AgentTask
from app.services.scoring import calculate_performance_score
from app.services.settings import get_performance_score_weights


def best_iteration_for_agent(agent_task: AgentTask) -> AgentIteration | None:
    iterations = AgentIteration.query.filter(AgentIteration.task_id == agent_task.id).all()
    if not iterations:
        return None
    return max(
        iterations,
        key=lambda iteration: (
            calculate_agent_iteration_score(iteration),
            iteration.iteration_number,
            iteration.id,
        ),
    )


def calculate_agent_iteration_score(iteration: AgentIteration) -> float:
    return calculate_performance_score(
        iteration.annual_return,
        iteration.sharpe,
        iteration.max_drawdown,
        weights=get_performance_score_weights(iteration.task.user if iteration.task else None),
    )


def metric_to_float(value) -> float | None:
    return round(float(value), 2) if value is not None else None
