"""Read-only SQLAlchemy metadata versus PostgreSQL foundation schema verifier."""

# mypy: ignore-errors

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from app.core.config.settings import settings
from app.core.database.sanitization import sanitize_database_error
from app.core.database.session import dispose_engine, get_engine
from app.model_registry import FOUNDATION_TABLE_NAMES, foundation_metadata_tables


@dataclass
class SchemaIssues:
    missing_tables: list[str] = field(default_factory=list)
    unexpected_tables: list[str] = field(default_factory=list)
    column_mismatches: list[str] = field(default_factory=list)
    primary_key_mismatches: list[str] = field(default_factory=list)
    foreign_key_mismatches: list[str] = field(default_factory=list)
    unique_constraint_issues: list[str] = field(default_factory=list)
    check_constraint_issues: list[str] = field(default_factory=list)
    index_mismatches: list[str] = field(default_factory=list)
    default_mismatches: list[str] = field(default_factory=list)
    not_automatically_verified: list[str] = field(default_factory=list)

    def has_errors(self) -> bool:
        return any(
            [
                self.missing_tables,
                self.unexpected_tables,
                self.column_mismatches,
                self.primary_key_mismatches,
                self.foreign_key_mismatches,
                self.unique_constraint_issues,
                self.check_constraint_issues,
                self.index_mismatches,
                self.default_mismatches,
            ]
        )


def _normalize_default(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip().lower()
    for wrapper in ("::character varying", "::text"):
        text_value = text_value.replace(wrapper, "")
    return " ".join(text_value.split())


def _type_signature(column_type: Any) -> str:
    type_name = str(column_type).lower()
    if type_name in {"datetime", "timestamp without time zone"}:
        return "timestamp"
    return type_name


def _pk_columns(table: Any) -> list[str]:
    return [column.name for column in table.primary_key.columns]


def _fk_signature(fk: dict[str, Any]) -> tuple[tuple[str, ...], str, tuple[str, ...]]:
    referred_table = fk.get("referred_table") or ""
    constrained = tuple(fk.get("constrained_columns") or [])
    referred = tuple(fk.get("referred_columns") or [])
    return constrained, referred_table, referred


def _metadata_fk_signatures(table: Any) -> set[tuple[tuple[str, ...], str, tuple[str, ...]]]:
    signatures: set[tuple[tuple[str, ...], str, tuple[str, ...]]] = set()
    for constraint in table.foreign_key_constraints:
        source = tuple(element.parent.name for element in constraint.elements)
        target_table = constraint.elements[0].column.table.name if constraint.elements else ""
        target_cols = tuple(element.column.name for element in constraint.elements)
        signatures.add((source, target_table, target_cols))
    return signatures


def compare_schema(connection: Connection) -> SchemaIssues:
    inspector = inspect(connection)
    metadata_tables = foundation_metadata_tables()
    live_tables = {
        table_name
        for table_name in inspector.get_table_names(schema="public")
        if table_name in FOUNDATION_TABLE_NAMES
    }

    issues = SchemaIssues()
    expected_names = set(metadata_tables)
    issues.missing_tables = sorted(expected_names - live_tables)
    issues.unexpected_tables = sorted(live_tables - expected_names)

    for table_name in sorted(expected_names & live_tables):
        metadata_table = metadata_tables[table_name]
        live_columns = inspector.get_columns(table_name, schema="public")
        live_by_name = {column["name"]: column for column in live_columns}
        metadata_columns = list(metadata_table.columns)

        live_order = [column["name"] for column in live_columns]
        metadata_order = [column.name for column in metadata_columns]
        if live_order != metadata_order:
            issues.column_mismatches.append(
                f"TABLE: {table_name} column order differs. Database={live_order}; SQLAlchemy={metadata_order}"
            )

        for column in metadata_columns:
            live_column = live_by_name.get(column.name)
            if live_column is None:
                issues.column_mismatches.append(f"TABLE: {table_name} missing live column {column.name}")
                continue
            if bool(live_column["nullable"]) != bool(column.nullable):
                issues.column_mismatches.append(
                    f"TABLE: {table_name} COLUMN: {column.name} nullable differs. "
                    f"Database={live_column['nullable']}; SQLAlchemy={column.nullable}"
                )
            live_default = _normalize_default(live_column.get("default"))
            metadata_default = _normalize_default(column.server_default.arg.text if column.server_default is not None else None)
            if live_default != metadata_default:
                issues.default_mismatches.append(
                    f"TABLE: {table_name} COLUMN: {column.name} default differs. "
                    f"Database={live_default}; SQLAlchemy={metadata_default}"
                )
            live_type = _type_signature(live_column["type"])
            metadata_type = _type_signature(column.type)
            if live_type != metadata_type:
                issues.column_mismatches.append(
                    f"TABLE: {table_name} COLUMN: {column.name} type differs. "
                    f"Database={live_type}; SQLAlchemy={metadata_type}"
                )

        live_pk = inspector.get_pk_constraint(table_name, schema="public").get("constrained_columns") or []
        metadata_pk = _pk_columns(metadata_table)
        if live_pk != metadata_pk:
            issues.primary_key_mismatches.append(
                f"TABLE: {table_name} primary key differs. Database={live_pk}; SQLAlchemy={metadata_pk}"
            )

        live_fks = {_fk_signature(fk) for fk in inspector.get_foreign_keys(table_name, schema="public")}
        metadata_fks = _metadata_fk_signatures(metadata_table)
        if live_fks != metadata_fks:
            issues.foreign_key_mismatches.append(
                f"TABLE: {table_name} foreign keys differ. Database={sorted(live_fks)}; SQLAlchemy={sorted(metadata_fks)}"
            )

        live_uniques = {
            tuple(unique.get("column_names") or [])
            for unique in inspector.get_unique_constraints(table_name, schema="public")
        }
        metadata_uniques = {
            tuple(column.name for column in constraint.columns)
            for constraint in metadata_table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        if not metadata_uniques.issubset(live_uniques):
            issues.unique_constraint_issues.append(
                f"TABLE: {table_name} unique constraints differ. Database={sorted(live_uniques)}; SQLAlchemy={sorted(metadata_uniques)}"
            )

        try:
            live_checks = {check.get("name") for check in inspector.get_check_constraints(table_name, schema="public")}
            metadata_checks = {
                constraint.name
                for constraint in metadata_table.constraints
                if constraint.__class__.__name__ == "CheckConstraint"
            }
            if not metadata_checks.issubset(live_checks):
                issues.check_constraint_issues.append(
                    f"TABLE: {table_name} check constraints differ. Database={sorted(live_checks)}; SQLAlchemy={sorted(metadata_checks)}"
                )
        except NotImplementedError:
            issues.not_automatically_verified.append(f"TABLE: {table_name} check constraint expressions")

        live_indexes = {index.get("name") for index in inspector.get_indexes(table_name, schema="public")}
        metadata_indexes = {index.name for index in metadata_table.indexes}
        if not metadata_indexes.issubset(live_indexes):
            issues.index_mismatches.append(
                f"TABLE: {table_name} indexes differ. Database={sorted(live_indexes)}; SQLAlchemy={sorted(metadata_indexes)}"
            )

    return issues


def _print_summary(issues: SchemaIssues, live_count: int) -> None:
    print("FOUNDATION SCHEMA VALIDATION")
    print()
    print(f"Expected SQLAlchemy tables: {len(FOUNDATION_TABLE_NAMES)}")
    print(f"Live foundation tables:     {live_count}")
    print()
    print(f"Missing tables:             {len(issues.missing_tables)}")
    print(f"Unexpected foundation tables: {len(issues.unexpected_tables)}")
    print(f"Column mismatches:          {len(issues.column_mismatches)}")
    print(f"Primary-key mismatches:     {len(issues.primary_key_mismatches)}")
    print(f"Foreign-key mismatches:     {len(issues.foreign_key_mismatches)}")
    print(f"Unique-constraint issues:   {len(issues.unique_constraint_issues)}")
    print(f"Check-constraint issues:    {len(issues.check_constraint_issues)}")
    print(f"Index mismatches:           {len(issues.index_mismatches)}")
    print(f"Default mismatches:         {len(issues.default_mismatches)}")
    print()
    for label, values in [
        ("Missing tables", issues.missing_tables),
        ("Unexpected foundation tables", issues.unexpected_tables),
        ("Column mismatches", issues.column_mismatches),
        ("Primary-key mismatches", issues.primary_key_mismatches),
        ("Foreign-key mismatches", issues.foreign_key_mismatches),
        ("Unique-constraint issues", issues.unique_constraint_issues),
        ("Check-constraint issues", issues.check_constraint_issues),
        ("Index mismatches", issues.index_mismatches),
        ("Default mismatches", issues.default_mismatches),
        ("Not automatically verified", issues.not_automatically_verified),
    ]:
        if values:
            print(label + ":")
            for value in values:
                print(f"  - {value}")
            print()


def main() -> int:
    try:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not configured. Add it to backend/.env.")
        with get_engine().connect() as connection:
            inspector = inspect(connection)
            live_count = len(
                {
                    table_name
                    for table_name in inspector.get_table_names(schema="public")
                    if table_name in FOUNDATION_TABLE_NAMES
                }
            )
            issues = compare_schema(connection)
        _print_summary(issues, int(live_count))
        if issues.has_errors():
            print("FOUNDATION SCHEMA STATUS: NOT IN SYNC")
            return 1
        print("FOUNDATION SCHEMA STATUS: IN SYNC")
        return 0
    except Exception as exc:
        print("FOUNDATION SCHEMA VALIDATION")
        print(f"Error: {sanitize_database_error(exc)}")
        print("FOUNDATION SCHEMA STATUS: NOT IN SYNC")
        return 1
    finally:
        dispose_engine()


if __name__ == "__main__":
    sys.exit(main())
