"""Synchronisation additive du schema.

`create_all` cree les tables manquantes, mais n'ajoute JAMAIS une colonne a une
table qui existe deja. Sur une base jetable (SQLite recreee a chaque lancement)
cela ne se voit pas ; sur un PostgreSQL persistant, l'ajout d'un champ au modele
casse toutes les requetes — y compris celles qui ne s'en servent pas, puisque
SQLAlchemy selectionne toutes les colonnes declarees.

Ce module comble exactement cet ecart, et rien de plus : il ajoute les colonnes
manquantes, il ne renomme rien, ne supprime rien, ne change aucun type. Les
evolutions non additives resteront du ressort d'une vraie migration — mais elles
sont rares, et ce n'est pas une raison pour laisser une demonstration tomber sur
un `UndefinedColumnError`.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.schema import Column

from app.db.base import Base

logger = logging.getLogger("mirror_ops.db.schema")


def _default_literal(column: Column) -> str | None:
    """Valeur par defaut a appliquer aux lignes existantes.

    Une colonne NOT NULL ajoutee a une table peuplee doit en avoir une, sinon la
    base refuse l'operation.
    """
    if column.server_default is not None:
        argument = getattr(column.server_default, "arg", None)
        return str(argument) if argument is not None else None

    default = column.default
    if default is None or default.is_callable or default.is_sequence:
        return None

    value = default.arg
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    return None


def plan_additive_changes(connection: Connection) -> list[tuple[str, Column]]:
    """Colonnes declarees dans les modeles mais absentes de la base."""
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    missing: list[tuple[str, Column]] = []

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue  # create_all s'en occupe
        present = {col["name"] for col in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name not in present:
                missing.append((table_name, column))
    return missing


def sync_additive_columns(connection: Connection) -> list[str]:
    """Ajoute les colonnes manquantes. Retourne leurs noms qualifies."""
    added: list[str] = []

    for table_name, column in plan_additive_changes(connection):
        column_type = column.type.compile(dialect=connection.dialect)
        statement = f'ALTER TABLE {table_name} ADD COLUMN {column.name} {column_type}'

        if not column.nullable:
            literal = _default_literal(column)
            if literal is not None:
                statement += f" NOT NULL DEFAULT {literal}"
            else:
                # Sans valeur par defaut, imposer NOT NULL echouerait sur les
                # lignes deja presentes. On ajoute la colonne en nullable et on
                # le signale plutot que de faire echouer le demarrage.
                logger.warning(
                    "schema_column_added_as_nullable",
                    extra={"table": table_name, "column": column.name},
                )

        connection.execute(text(statement))
        added.append(f"{table_name}.{column.name}")
        logger.info(
            "schema_column_added", extra={"table": table_name, "column": column.name}
        )

    return added
