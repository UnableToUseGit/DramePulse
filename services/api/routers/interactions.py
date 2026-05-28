from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..repositories.interactions import get_interaction_results, list_interaction_plans
from ..schemas import InteractionPlan, InteractionPlansResponse, InteractionResultResponse

router = APIRouter()


@router.get("/videos/{video_id}/interaction-plans", response_model=InteractionPlansResponse)
def retrieve_interaction_plans(video_id: str) -> InteractionPlansResponse:
    plans = [InteractionPlan(**plan) for plan in list_interaction_plans(video_id)]
    return InteractionPlansResponse(video_id=video_id, interaction_plans=plans)


@router.get("/interactions/{interaction_id}/results", response_model=InteractionResultResponse)
def retrieve_interaction_results(interaction_id: str) -> InteractionResultResponse:
    results = get_interaction_results(interaction_id)
    if results is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interaction not found")
    return InteractionResultResponse(**results)
