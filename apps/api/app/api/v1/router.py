"""Assemblage du routeur v1 (Doc 08 §34 : Minimal contract. Maximum clarity)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import appearance, health, media, moments, one_change, sessions, vto

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(sessions.router)
api_router.include_router(moments.router)
api_router.include_router(appearance.router)
api_router.include_router(one_change.router)
api_router.include_router(vto.router)
api_router.include_router(media.router)
