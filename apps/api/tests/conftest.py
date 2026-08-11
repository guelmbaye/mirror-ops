"""Fixtures de test : base SQLite isolee, stockage temporaire, providers mock."""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import pytest

TMP_ROOT = Path(tempfile.mkdtemp(prefix="mirror-ops-tests-"))

os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite+aiosqlite:///{TMP_ROOT / 'test.db'}",
        "STORAGE_DIR": str(TMP_ROOT / "storage"),
        "STORAGE_BACKEND": "local",
        "YOUCAM_MODE": "mock",
        "MEDIA_SIGNING_SECRET": "test-secret",
        "RATE_LIMIT_ENABLED": "false",
        "LOG_LEVEL": "WARNING",
        "LOG_JSON": "false",
        "PUBLIC_BASE_URL": "http://testserver",
    }
)

import httpx  # noqa: E402
from PIL import Image  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, engine, init_models  # noqa: E402
from app.integrations.youcam import reset_providers  # noqa: E402
from app.main import app  # noqa: E402
from app.services.appearance_service import clear_skin_cache  # noqa: E402
from app.services.storage import reset_storage  # noqa: E402

get_settings.cache_clear()


def make_image(
    width: int = 720,
    height: int = 1280,
    color: tuple[int, int, int] = (168, 140, 128),
    fmt: str = "JPEG",
    noisy: bool = True,
) -> bytes:
    """Image synthetique realiste : assez nette et lumineuse pour passer le gate."""
    image = Image.new("RGB", (width, height), color)
    if noisy:
        import random

        random.seed(7)
        pixels = image.load()
        for y in range(0, height, 3):
            for x in range(0, width, 3):
                shift = random.randint(-38, 38)
                r, g, b = pixels[x, y]
                pixels[x, y] = (
                    max(0, min(255, r + shift)),
                    max(0, min(255, g + shift)),
                    max(0, min(255, b + shift)),
                )
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, quality=95 if fmt == "JPEG" else None)
    return buffer.getvalue()


@pytest.fixture(scope="session", autouse=True)
async def _prepare_database():
    await init_models()
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_state():
    reset_providers()
    reset_storage()
    clear_skin_cache()
    yield


@pytest.fixture
async def db():
    async with SessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest.fixture
def photo() -> bytes:
    return make_image()


class FlowHelper:
    """Petit utilitaire pour derouler le parcours complet dans les tests."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def session(self) -> str:
        response = await self.client.post("/api/v1/sessions")
        assert response.status_code == 201, response.text
        return response.json()["id"]

    async def moment(
        self,
        session_id: str,
        occasion: str = "presentation",
        goal: str = "professional",
        time_available: str = "<5m",
    ) -> str:
        response = await self.client.post(
            "/api/v1/moments",
            json={
                "session_id": session_id,
                "occasion": occasion,
                "goal": goal,
                "time_available": time_available,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    async def analyze(
        self, session_id: str, image: bytes | None = None, outfit: str | None = None
    ) -> dict:
        files = {"image": ("look.jpg", image or make_image(), "image/jpeg")}
        data: dict[str, str] = {"session_id": session_id}
        if outfit:
            data["outfit"] = outfit
        response = await self.client.post("/api/v1/appearance/analyze", data=data, files=files)
        assert response.status_code == 201, response.text
        return response.json()

    async def one_change(self, session_id: str) -> dict:
        response = await self.client.post(
            "/api/v1/one-change/evaluate", json={"session_id": session_id}
        )
        assert response.status_code == 201, response.text
        return response.json()["recommendation"]

    async def vto(self, session_id: str, **kwargs) -> httpx.Response:
        payload = {"session_id": session_id, **kwargs}
        return await self.client.post("/api/v1/vto/generate", json=payload)


@pytest.fixture
def flow(client) -> FlowHelper:
    return FlowHelper(client)
