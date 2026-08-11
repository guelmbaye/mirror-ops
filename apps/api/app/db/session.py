"""Moteur asynchrone + fabrique de sessions SQLAlchemy."""

from __future__ import annotations

import logging

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.schema_sync import sync_additive_columns

_settings = get_settings()

_connect_args = {"check_same_thread": False} if _settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_async_engine(
    _settings.DATABASE_URL,
    echo=_settings.DB_ECHO,
    future=True,
    pool_pre_ping=not _settings.DATABASE_URL.startswith("sqlite"),
    connect_args=_connect_args,
)

logger = logging.getLogger("mirror_ops.db")

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def ensure_sqlite_directory(url: str) -> None:
    """Cree le dossier parent d'une base SQLite si besoin.

    `var/` est ignore par git : sans cela, un depot fraichement clone echoue au
    demarrage avec « unable to open database file » — une premiere impression
    desastreuse pour un projet cense se lancer en deux minutes.
    """
    if "sqlite" not in url:
        return
    _, _, path = url.partition(":///")
    path = path.split("?", 1)[0]
    if not path or path == ":memory:":
        return
    parent = Path(path).expanduser().parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)


async def init_models() -> None:
    """Cree les tables si absentes (MVP : pas de migration obligatoire)."""
    import app.models  # noqa: F401  (enregistre les mappings)

    ensure_sqlite_directory(str(engine.url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all n'ajoute pas les colonnes manquantes aux tables existantes.
        # Sur une base persistante, chaque nouveau champ casserait autrement
        # toutes les requetes sur la table concernee.
        added = await conn.run_sync(sync_additive_columns)
    if added:
        logger.info("schema_synced", extra={"columns": added})


async def dispose_engine() -> None:
    await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
