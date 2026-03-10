"""Goal and milestone management endpoints."""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException

from app.database import repositories as repo
from app.models.schemas import (
    BulkMilestoneCreate,
    GoalCreate,
    GoalListItem,
    GoalProgressUpdate,
    GoalResponse,
    GoalUpdate,
    GoalWithMilestones,
    MilestoneCreate,
    MilestoneResponse,
    MilestoneUpdate,
)

logger = logging.getLogger("life-master.routers.goals")

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalListItem])
async def list_goals(status: str | None = None, category: str | None = None):
    return await repo.get_goals_with_milestone_counts(status=status, category=category)


@router.post("", response_model=GoalResponse)
async def create_goal(body: GoalCreate):
    result = await repo.create_goal(body.model_dump())
    logger.info("Goal created: %s", body.title)
    return result


@router.get("/{goal_id}", response_model=GoalWithMilestones)
async def get_goal(goal_id: int):
    result = await repo.get_goal(goal_id)
    if not result:
        raise HTTPException(status_code=404, detail="Goal not found")
    milestones = await repo.get_milestones(goal_id)
    days_remaining = None
    if result.get("deadline"):
        try:
            days_remaining = (date.fromisoformat(result["deadline"]) - date.today()).days
        except ValueError:
            pass
    return {
        **result,
        "milestones": milestones,
        "milestone_total": len(milestones),
        "milestone_done": sum(1 for m in milestones if m["is_completed"]),
        "days_remaining": days_remaining,
    }


@router.put("/{goal_id}", response_model=GoalResponse)
async def update_goal(goal_id: int, body: GoalUpdate):
    existing = await repo.get_goal(goal_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Goal not found")
    result = await repo.update_goal(goal_id, body.model_dump(exclude_unset=True))
    return result


@router.patch("/{goal_id}/progress", response_model=GoalResponse)
async def update_progress(goal_id: int, body: GoalProgressUpdate):
    existing = await repo.get_goal(goal_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Goal not found")
    result = await repo.update_goal_progress(goal_id, body.progress)
    logger.info("Goal %d progress: %.0f%%", goal_id, body.progress * 100)
    return result


@router.delete("/{goal_id}")
async def abandon_goal(goal_id: int):
    goal = await repo.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    result = await repo.abandon_goal(goal_id)
    logger.info("Goal %d abandoned", goal_id)
    return result


@router.patch("/{goal_id}/reactivate", response_model=GoalResponse)
async def reactivate_goal(goal_id: int):
    goal = await repo.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    result = await repo.reactivate_goal(goal_id)
    logger.info("Goal %d reactivated", goal_id)
    return result


@router.patch("/{goal_id}/pause", response_model=GoalResponse)
async def pause_goal(goal_id: int):
    goal = await repo.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    result = await repo.pause_goal(goal_id)
    logger.info("Goal %d paused", goal_id)
    return result


# ── Milestones ────────────────────────────────────────────


@router.get("/{goal_id}/milestones", response_model=list[MilestoneResponse])
async def list_milestones(goal_id: int):
    goal = await repo.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return await repo.get_milestones(goal_id)


@router.post("/{goal_id}/milestones", response_model=MilestoneResponse)
async def create_milestone(goal_id: int, body: MilestoneCreate):
    goal = await repo.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    result = await repo.create_milestone(goal_id, body.model_dump())
    logger.info("Milestone created for goal %d: %s", goal_id, body.title)
    return result


@router.post("/{goal_id}/milestones/bulk", response_model=list[MilestoneResponse])
async def create_milestones_bulk(goal_id: int, body: BulkMilestoneCreate):
    goal = await repo.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    items = [m.model_dump() for m in body.milestones]
    results = await repo.create_milestones_bulk(goal_id, items)
    logger.info("Created %d milestones for goal %d", len(results), goal_id)
    return results


@router.put("/{goal_id}/milestones/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(goal_id: int, milestone_id: int, body: MilestoneUpdate):
    goal = await repo.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    result = await repo.update_milestone(milestone_id, body.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return result


@router.patch("/{goal_id}/milestones/{milestone_id}/complete", response_model=MilestoneResponse)
async def complete_milestone(goal_id: int, milestone_id: int):
    goal = await repo.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    result = await repo.complete_milestone(milestone_id, goal_id)
    if not result:
        raise HTTPException(status_code=404, detail="Milestone not found")
    logger.info("Milestone %d completed for goal %d", milestone_id, goal_id)
    return result


@router.patch("/{goal_id}/milestones/{milestone_id}/uncomplete", response_model=MilestoneResponse)
async def uncomplete_milestone(goal_id: int, milestone_id: int):
    goal = await repo.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    result = await repo.uncomplete_milestone(milestone_id, goal_id)
    if not result:
        raise HTTPException(status_code=404, detail="Milestone not found")
    logger.info("Milestone %d uncompleted for goal %d", milestone_id, goal_id)
    return result


@router.delete("/{goal_id}/milestones/{milestone_id}")
async def delete_milestone(goal_id: int, milestone_id: int):
    ok = await repo.delete_milestone(milestone_id, goal_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return {"deleted": milestone_id}
