from celery import current_task
from celery.exceptions import SoftTimeLimitExceeded

from app.extensions import celery_app, db
from app.models.agent_task import AgentTask
from app.models.user import User
from app.services.agent_tasks import AgentTaskError, mark_agent_task_failed, run_agent_iterations
from app.services.scheduled_plans import complete_scheduled_plan_run_for_agent


def _get_user(user_id: int) -> User:
    user = db.session.get(User, user_id)
    if not user:
        raise AgentTaskError(f"未找到用户 {user_id}，无法执行 Agent 任务。")
    return user


def _get_task(task_id: int) -> AgentTask:
    task = db.session.get(AgentTask, task_id)
    if not task:
        raise AgentTaskError(f"未找到 Agent 任务 {task_id}。")
    return task


@celery_app.task(name="app.tasks.agent.run_agent_task")
def run_agent_task(*, task_id: int, user_id: int) -> dict:
    _get_user(user_id)
    task = _get_task(task_id)
    celery_task_id = current_task.request.id if current_task else None

    try:
        result = run_agent_iterations(task, task_id=celery_task_id)
        complete_scheduled_plan_run_for_agent(
            task,
            success=task.status == "success",
            error_message=None if task.status == "success" else "Agent 任务未完成，未保存计划策略。",
        )
        return result
    except SoftTimeLimitExceeded as exc:
        mark_agent_task_failed(task, "Agent 任务执行超时。", celery_task_id=celery_task_id)
        complete_scheduled_plan_run_for_agent(task, success=False, error_message="Agent 任务执行超时。")
        raise AgentTaskError("Agent 任务执行超时。") from exc
    except AgentTaskError as exc:
        mark_agent_task_failed(task, str(exc), celery_task_id=celery_task_id)
        complete_scheduled_plan_run_for_agent(task, success=False, error_message=str(exc))
        raise
    except Exception as exc:
        mark_agent_task_failed(task, f"Agent 任务执行失败：{exc}", celery_task_id=celery_task_id)
        complete_scheduled_plan_run_for_agent(task, success=False, error_message=f"Agent 任务执行失败：{exc}")
        raise
