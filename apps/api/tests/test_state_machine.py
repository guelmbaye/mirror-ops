"""Machine a etats de l'API (Doc 08 §21) : les transitions impossibles sont rejetees."""

from __future__ import annotations

from tests.conftest import make_image


async def test_analyze_before_moment_is_rejected(client, flow):
    session_id = await flow.session()
    response = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.jpg", make_image(), "image/jpeg")},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"


async def test_one_change_before_analysis_is_rejected(client, flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    response = await client.post("/api/v1/one-change/evaluate", json={"session_id": session_id})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"


async def test_vto_before_one_change_is_rejected(flow):
    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    response = await flow.vto(session_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"


async def test_state_progresses_monotonically(client, flow):
    session_id = await flow.session()

    async def state() -> str:
        response = await client.get(f"/api/v1/sessions/{session_id}/summary")
        return response.json()["state"]

    assert await state() == "SESSION_CREATED"
    await flow.moment(session_id)
    assert await state() == "MOMENT_CREATED"
    await flow.analyze(session_id)
    assert await state() == "ANALYSIS_COMPLETED"
    await flow.one_change(session_id)
    assert await state() == "DECISION_COMPLETED"
    await flow.vto(session_id)
    assert await state() == "VTO_COMPLETED"


async def test_expired_session_is_rejected(client, flow, db):
    from sqlalchemy import select

    from app.db.base import utcnow
    from app.models.session import UserSession

    session_id = await flow.session()
    session = (
        await db.execute(select(UserSession).where(UserSession.id == session_id))
    ).scalar_one()
    session.expires_at = utcnow().replace(year=utcnow().year - 1)
    await db.commit()

    response = await client.post(
        "/api/v1/moments",
        json={
            "session_id": session_id,
            "occasion": "presentation",
            "goal": "professional",
            "time_available": "<5m",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"


async def test_cross_session_resources_are_rejected(client, flow):
    first = await flow.session()
    second = await flow.session()
    moment_id = await flow.moment(first)
    await flow.moment(second)

    response = await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": second, "moment_id": moment_id},
        files={"image": ("look.jpg", make_image(), "image/jpeg")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
