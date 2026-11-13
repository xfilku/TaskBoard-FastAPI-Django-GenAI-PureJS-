"""Generate task previews for owned boards without persisting model proposals."""

import httpx
from ai.dependencies import get_text_model
from ai.model import InvalidModelResponseError, TextModel
from ai.planner import InvalidPlanError, build_plan_prompt, generate_plan
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models.board import Board
from models.task import Task
from schemas.planning import PlanRequest, PlanResponse
from security import get_own_board
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/boards/{board_id}/plan-preview", response_model=PlanResponse)
def plan_preview(
    data: PlanRequest,
    board: Board = Depends(get_own_board),
    db: Session = Depends(get_db),
    model: TextModel = Depends(get_text_model),
) -> PlanResponse:
    """Preview validated proposals after checking ownership; saving is a separate action."""
    titles = db.scalars(select(Task.title).where(Task.board_id == board.id).order_by(Task.id)).all()
    prompt = build_plan_prompt(data.goal, data.min_elements, data.max_elements, titles)
    try:
        return generate_plan(prompt, model, data.min_elements, data.max_elements, titles)
    except (InvalidPlanError, InvalidModelResponseError) as exc:
        raise HTTPException(502, "AI zwróciło niepoprawny plan. Spróbuj ponownie.") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, "Serwer modelu zwrócił błąd.") from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "Model nie odpowiedział na czas.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(503, "Model jest niedostępny.") from exc
