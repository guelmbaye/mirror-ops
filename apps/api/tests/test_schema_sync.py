"""Une base persistante doit survivre a l'ajout d'un champ.

Ce module existe a cause d'un incident reel : l'ajout de `is_addition` au modele
a rendu inutilisable une base PostgreSQL existante. `create_all` cree les tables
manquantes mais n'ajoute aucune colonne — et SQLAlchemy selectionnant toutes les
colonnes declarees, TOUTES les requetes sur `recommendations` echouaient, y
compris celles qui ne se servaient pas du nouveau champ.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import create_engine, inspect, text

from app.db.base import Base
from app.db.schema_sync import _default_literal, plan_additive_changes, sync_additive_columns


def _engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")


def test_a_missing_column_is_added_to_a_populated_table(tmp_path):
    """Le scenario exact de l'incident."""
    engine = _engine(tmp_path)

    with engine.begin() as conn:
        # Une base « d'hier » : la table existe, sans la colonne recente.
        Base.metadata.create_all(conn)
        conn.execute(text("ALTER TABLE recommendations DROP COLUMN is_addition"))

    with engine.begin() as conn:
        assert any(t == "recommendations" and c.name == "is_addition"
                   for t, c in plan_additive_changes(conn))
        added = sync_additive_columns(conn)

    assert "recommendations.is_addition" in added
    with engine.connect() as conn:
        columns = {c["name"] for c in inspect(conn).get_columns("recommendations")}
    assert "is_addition" in columns


def test_existing_rows_survive_a_not_null_column(tmp_path):
    """Sans valeur par defaut, ajouter NOT NULL a une table peuplee echouerait."""
    engine = _engine(tmp_path)

    with engine.begin() as conn:
        Base.metadata.create_all(conn)
        conn.execute(text("ALTER TABLE recommendations DROP COLUMN is_addition"))
        conn.execute(
            text(
                "INSERT INTO recommendations (id, session_id, moment_id, analysis_id, "
                "action, label, score, confidence, confidence_value, reason, what, why, "
                "how, keep, impact, candidates, created_at, updated_at) VALUES "
                "('r1','s1','m1','a1','CHANGE_JACKET','Change the jacket', 70.0, 'medium', "
                "0.6, 'r', 'w', 'y', 'h', '[]', '{}', '[]', "
                "'2026-01-01 00:00:00', '2026-01-01 00:00:00')"
            )
        )

    with engine.begin() as conn:
        sync_additive_columns(conn)

    with engine.connect() as conn:
        row = conn.execute(text("SELECT is_addition FROM recommendations WHERE id='r1'")).one()
    assert row[0] in (0, False)  # la ligne existante recoit la valeur par defaut


def test_sync_is_idempotent(tmp_path):
    engine = _engine(tmp_path)
    with engine.begin() as conn:
        Base.metadata.create_all(conn)
    with engine.begin() as conn:
        assert sync_additive_columns(conn) == []
        assert sync_additive_columns(conn) == []


def test_sync_never_touches_an_existing_column(tmp_path):
    """Additif seulement : aucun renommage, aucune suppression, aucun type modifie."""
    engine = _engine(tmp_path)
    with engine.begin() as conn:
        Base.metadata.create_all(conn)
        before = {c["name"]: str(c["type"]) for c in inspect(conn).get_columns("recommendations")}
        sync_additive_columns(conn)
        after = {c["name"]: str(c["type"]) for c in inspect(conn).get_columns("recommendations")}
    assert before == after


def test_default_literals_are_quoted_correctly():
    assert _default_literal(sa.Column("a", sa.Boolean, default=False, nullable=False)) == "false"
    assert _default_literal(sa.Column("b", sa.Integer, default=3, nullable=False)) == "3"
    assert _default_literal(sa.Column("c", sa.String, default="x'y", nullable=False)) == "'x''y'"
    assert _default_literal(sa.Column("d", sa.String, nullable=True)) is None
