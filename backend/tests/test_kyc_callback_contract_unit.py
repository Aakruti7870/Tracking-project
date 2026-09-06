"""Deployment regression checks for the public DigiLocker return route."""
from pathlib import Path
import asyncio

import httpx

from server import app


ROOT = Path(__file__).resolve().parents[2]


def test_kyc_return_is_an_expo_public_route_and_nginx_spa_fallback():
    route = ROOT / "frontend/app/kyc/return.tsx"
    nginx = (ROOT / "frontend/nginx.conf").read_text()

    assert route.is_file()
    assert "try_files $uri /index.html" in nginx
    assert "trackmyrmc://kyc" in route.read_text()


def test_kyc_return_query_string_uses_same_public_spa_route():
    nginx = (ROOT / "frontend/nginx.conf").read_text()

    # nginx try_files ignores the query while retaining it on the index fallback;
    # no exact-match/proxy rule may intercept the public callback.
    assert "location = /kyc/return" not in nginx
    assert "location /kyc/return" not in nginx


async def _get(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def test_kyc_return_200():
    response = asyncio.run(_get("/kyc/return"))
    assert response.status_code == 200


def test_kyc_return_query_200():
    response = asyncio.run(_get("/kyc/return?state=test"))
    assert response.status_code == 200
