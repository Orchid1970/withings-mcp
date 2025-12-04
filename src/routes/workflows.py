import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database import get_db
from src.models import Observation
from src.clients.withings_client import sync_user, sync_all_users

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/withings/sync")
async def trigger_sync(user_id: str = Query(None)):
    if user_id:
        await sync_user(user_id)
        return {"status": "synced", "user_id": user_id}
    else:
        await sync_all_users()
        return {"status": "synced_all"}

@router.get("/withings/observations")
async def get_observations(
    user_id: str,
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Observation)
        .where(Observation.user_id == user_id)
        .order_by(Observation.effective_datetime.desc())
        .limit(limit)
    )
    observations = result.scalars().all()
    
    return {
        "count": len(observations),
        "observations": [
            {
                "id": obs.id,
                "code": obs.code_display,
                "value": obs.value_quantity,
                "unit": obs.value_unit,
                "datetime": obs.effective_datetime.isoformat(),
                "loinc": obs.code_value
            }
            for obs in observations
        ]
    }
