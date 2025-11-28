import pytest
from httpx import AsyncClient, ASGITransport
from src.app import api

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=api)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}