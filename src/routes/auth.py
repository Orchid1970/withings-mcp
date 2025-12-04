import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
import httpx
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database import get_db
from src.models import TokenRecord
from src.encryption import encrypt_token, decrypt_token
from src.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
WITHINGS_AUTH = "https://account.withings.com/oauth2_user/authorize2"
WITHINGS_TOKEN = os.getenv("WITHINGS_TOKEN_URL", "https://wbsapi.withings.net/v2/oauth2")

@router.get("/")
async def initiate_oauth():
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.WITHINGS_CLIENT_ID,
        "redirect_uri": f"{settings.BASE_URL}/auth/callback",
        "scope": "user.metrics,user.activity,user.sleepevents",
        "state": "withings_oauth"
    }
    url = f"{WITHINGS_AUTH}?" + "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url)

@router.get("/callback")
async def oauth_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(WITHINGS_TOKEN, data={
            "action": "requesttoken",
            "grant_type": "authorization_code",
            "client_id": settings.WITHINGS_CLIENT_ID,
            "client_secret": settings.WITHINGS_CLIENT_SECRET,
            "code": code,
            "redirect_uri": f"{settings.BASE_URL}/auth/callback"
        })
        
        data = resp.json()
        if data.get("status") != 0:
            logger.error(f"OAuth error: {data}")
            raise HTTPException(status_code=400, detail="OAuth failed")
        
        body = data["body"]
        user_id = str(body["userid"])
        access_token = body["access_token"]
        refresh_token = body["refresh_token"]
        expires_in = body["expires_in"]

        logger.info(f"OAuth complete for user {user_id}. Expires In: {expires_in} seconds.")
        
        # Check if token record already exists
        result = await db.execute(select(TokenRecord).where(TokenRecord.user_id == user_id))
        token = result.scalar_one_or_none()
        
        if token:
            # Update existing token
            token.access_token_encrypted = encrypt_token(access_token)
            token.refresh_token_encrypted = encrypt_token(refresh_token)
            token.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        else:
            # Create new token record
            token = TokenRecord(
                user_id=user_id,
                access_token_encrypted=encrypt_token(access_token),
                refresh_token_encrypted=encrypt_token(refresh_token),
                expires_at=datetime.utcnow() + timedelta(seconds=expires_in)
            )
            db.add(token)
        
        await db.commit()
        return {"status": "connected", "user_id": user_id, "message": "Tokens saved to database"}

async def get_valid_token(user_id: str, db: AsyncSession) -> str:
    """
    Retrieve a valid access token for the given user.
    Automatically refreshes if expired.
    
    Args:
        user_id: The Withings user ID
        db: Database session
        
    Returns:
        Valid access token (decrypted)
        
    Raises:
        HTTPException: If token not found or refresh fails
    """
    # Get token from database
    result = await db.execute(select(TokenRecord).where(TokenRecord.user_id == user_id))
    token = result.scalar_one_or_none()
    
    if not token:
        raise HTTPException(status_code=404, detail=f"No token found for user {user_id}")
    
    # Check if expired
    if datetime.utcnow() >= token.expires_at:
        logger.info(f"Token expired for user {user_id}. Refreshing...")
        
        # Refresh the token
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.post(WITHINGS_TOKEN, data={
                "action": "requesttoken",
                "grant_type": "refresh_token",
                "client_id": settings.WITHINGS_CLIENT_ID,
                "client_secret": settings.WITHINGS_CLIENT_SECRET,
                "refresh_token": decrypt_token(token.refresh_token_encrypted)
            })
            
            data = resp.json()
            if data.get("status") != 0:
                logger.error(f"Token refresh failed for user {user_id}: {data}")
                raise HTTPException(status_code=400, detail="Token refresh failed")
            
            body = data["body"]
            # Update token in database
            token.access_token_encrypted = encrypt_token(body["access_token"])
            token.refresh_token_encrypted = encrypt_token(body["refresh_token"])
            token.expires_at = datetime.utcnow() + timedelta(seconds=body["expires_in"])
            await db.commit()
            
            logger.info(f"Token refreshed successfully for user {user_id}")
    
    # Return decrypted access token
    return decrypt_token(token.access_token_encrypted)
