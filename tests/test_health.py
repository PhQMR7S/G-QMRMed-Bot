from typing import Any

import httpx
import pytest

import gqmrmed.main as main
from gqmrmed.main import app


@pytest.mark.asyncio
async def test_health() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "GQMRMed"


@pytest.mark.asyncio
async def test_health_live() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


class FakeSession:
    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def execute(self, statement: Any) -> None:
        return None


class FakeSessionFactory:
    def __call__(self) -> FakeSession:
        return FakeSession()


class FakeRedis:
    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None


class FakeRedisFactory:
    @staticmethod
    def from_url(url: str) -> FakeRedis:
        assert url
        return FakeRedis()


@pytest.mark.asyncio
async def test_health_ready_reports_dependencies_as_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "SessionFactory", FakeSessionFactory())
    monkeypatch.setattr(main, "Redis", FakeRedisFactory)

    response = await main.health_ready()

    assert response.status_code == 200
    assert response.body == b'{"status":"ready","database":"ok","redis":"ok"}'


class FailingRedis:
    async def ping(self) -> bool:
        raise RuntimeError("redis unavailable")

    async def aclose(self) -> None:
        return None


class FailingRedisFactory:
    @staticmethod
    def from_url(url: str) -> FailingRedis:
        assert url
        return FailingRedis()


@pytest.mark.asyncio
async def test_health_ready_returns_503_when_redis_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "SessionFactory", FakeSessionFactory())
    monkeypatch.setattr(main, "Redis", FailingRedisFactory)

    response = await main.health_ready()

    assert response.status_code == 503
    assert response.body == b'{"status":"not_ready","database":"ok","redis":"error"}'
