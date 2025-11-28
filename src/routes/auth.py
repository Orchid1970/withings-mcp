import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database import get_db
from src.models import TokenRecord
from src.encryption import encrypt_token
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
WITHINGS_AUTH = "https://account.withings.com/oauth2_user/authorize2"
WITHINGS_TOKEN = "https://wbsapi.withings.net/v2/oauth2"

@router.get("/withings")
async def initiate_oauth():
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.WITHINGS_CLIENT_ID,
        "redirect_uri": f"{settings.BASE_URL}/auth/withings/callback",
        "scope": "user.metrics,user.activity,user.sleepevents",
        "state": "withings_oauth"
    }
    url = f"{WITHINGS_AUTH}?" + "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url)

@router.get("/withings/callback")
async def oauth_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(WITHINGS_TOKEN, data={
            "action": "requesttoken",
            "grant_type": "authorization_code",
            "client_id": settings.WITHINGS_CLIENT_ID,
            "client_secret": settings.WITHINGS_CLIENT_SECRET,
            "code": code,
            "redirect_uri": f"{settings.BASE_URL}/auth/withings/callback"
        })
        
        data = resp.json()
        if data.get("status") != 0:
            logger.error(f"OAuth error: {data}")
            raise HTTPException(status_code=400, detail="OAuth failed")
        
        body = data["body"]
        user_id = str(body["userid"])
        
        result = await db.execute(select(TokenRecord).where(TokenRecord.user_id == user_id))
        token = result.scalar_one_or_none()
        
        if token:
            token.access_token_encrypted = encrypt_token(body["access_token"])
            token.refresh_token_encrypted = encrypt_token(body["refresh_token"])
            token.expires_at = datetime.utcnow() + timedelta(seconds=body["expires_in"])
        else:
            token = TokenRecord(
                user_id=user_id,
                access_token_encrypted=encrypt_token(body["access_token"]),
                refresh_token_encrypted=encrypt_token(body["refresh_token"]),
                expires_at=datetime.utcnow() + timedelta(seconds=body["expires_in"])
            )
            db.add(token)
        
        await db.commit()
        logger.info(f"OAuth complete for user {user_id}")
        return {"status": "connected", "user_id": user_id}