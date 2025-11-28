import logging
import httpx
from datetime import datetime, timedelta
from sqlalchemy import select
from src.database import async_session
from src.models import TokenRecord, Observation
from src.encryption import decrypt_token, encrypt_token
from src.config import get_settings
from src.fhir_mappings import WITHINGS_TO_FHIR

logger = logging.getLogger(__name__)
WITHINGS_API = "https://wbsapi.withings.net"

async def refresh_token_if_needed(token: TokenRecord) -> TokenRecord:
    if token.expires_at > datetime.utcnow() + timedelta(minutes=5):
        return token
    
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{WITHINGS_API}/v2/oauth2", data={
            "action": "requesttoken",
            "grant_type": "refresh_token",
            "client_id": settings.WITHINGS_CLIENT_ID,
            "client_secret": settings.WITHINGS_CLIENT_SECRET,
            "refresh_token": decrypt_token(token.refresh_token_encrypted)
        })
        data = resp.json()["body"]
        
        token.access_token_encrypted = encrypt_token(data["access_token"])
        token.refresh_token_encrypted = encrypt_token(data["refresh_token"])
        token.expires_at = datetime.utcnow() + timedelta(seconds=data["expires_in"])
        logger.info(f"Refreshed token for user {token.user_id}")
        return token

async def fetch_measurements(token: TokenRecord) -> list[dict]:
    token = await refresh_token_if_needed(token)
    access_token = decrypt_token(token.access_token_encrypted)
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{WITHINGS_API}/measure", data={
            "action": "getmeas",
            "access_token": access_token,
            "startdate": int((datetime.utcnow() - timedelta(days=30)).timestamp()),
            "enddate": int(datetime.utcnow().timestamp())
        })
        return resp.json().get("body", {}).get("measuregrps", [])

def convert_to_fhir(user_id: str, measuregrps: list[dict]) -> list[Observation]:
    observations = []
    for grp in measuregrps:
        grp_date = datetime.fromtimestamp(grp["date"])
        for measure in grp.get("measures", []):
            mtype = measure["type"]
            if mtype not in WITHINGS_TO_FHIR:
                continue
            
            fhir = WITHINGS_TO_FHIR[mtype]
            value = measure["value"] * (10 ** measure["unit"])
            
            obs = Observation(
                user_id=user_id,
                code_system="http://loinc.org",
                code_value=fhir["loinc"],
                code_display=fhir["display"],
                value_quantity=value,
                value_unit=fhir["unit"],
                effective_datetime=grp_date,
                withings_type=mtype
            )
            observations.append(obs)
    return observations

async def sync_user(user_id: str):
    async with async_session() as session:
        result = await session.execute(select(TokenRecord).where(TokenRecord.user_id == user_id))
        token = result.scalar_one_or_none()
        if not token:
            logger.warning(f"No token for user {user_id}")
            return
        
        measuregrps = await fetch_measurements(token)
        observations = convert_to_fhir(user_id, measuregrps)
        
        for obs in observations:
            session.add(obs)
        await session.commit()
        logger.info(f"Synced {len(observations)} observations for user {user_id}")

async def sync_all_users():
    async with async_session() as session:
        result = await session.execute(select(TokenRecord))
        tokens = result.scalars().all()
        for token in tokens:
            await sync_user(token.user_id)