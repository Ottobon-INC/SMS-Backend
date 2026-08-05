"""Foundation model metadata tests."""

import importlib

from app.model_registry import (
    FOUNDATION_TABLE_NAMES,
    foundation_metadata_tables,
    import_foundation_models,
)
from app.shared.models.base import Base

MODEL_MODULES = [
    "app.modules.academic_structure.models",
    "app.modules.audit.models",
    "app.modules.authentication.models",
    "app.modules.branches.models",
    "app.modules.imports.models",
    "app.modules.platform_admin.models",
    "app.modules.students.models",
    "app.modules.users.models",
    "app.modules.workflows.models",
]


def test_model_modules_import_successfully() -> None:
    for module_name in MODEL_MODULES:
        importlib.import_module(module_name)


def test_foundation_metadata_contains_exactly_expected_tables() -> None:
    import_foundation_models()
    foundation_tables = {
        table_name
        for table_name in Base.metadata.tables
        if table_name in FOUNDATION_TABLE_NAMES
    }
    assert foundation_tables == FOUNDATION_TABLE_NAMES
    assert len(foundation_tables) == 26


def test_foundation_metadata_registry_has_no_missing_tables() -> None:
    tables = foundation_metadata_tables()
    assert set(tables) == FOUNDATION_TABLE_NAMES
    assert len(tables) == 26
