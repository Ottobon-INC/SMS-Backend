"""Central registry for importing all foundation SQLAlchemy models."""

from app.shared.models.base import Base

FOUNDATION_TABLE_NAMES = {
    "sms_subscription_plans",
    "sms_tenants",
    "sms_tenant_subscriptions",
    "sms_branches",
    "sms_configurations",
    "sms_privileged_access_grants",
    "sms_users",
    "sms_roles",
    "sms_permissions",
    "sms_role_permissions",
    "sms_user_access_assignments",
    "sms_academic_years",
    "sms_academic_programmes",
    "sms_batches",
    "sms_sections",
    "sms_subjects",
    "sms_section_subjects",
    "sms_students",
    "sms_student_aliases",
    "sms_enrollments",
    "sms_guardians",
    "sms_student_guardian_links",
    "sms_import_batches",
    "sms_import_rows",
    "sms_workflow_requests",
    "sms_audit_events",
}


def import_foundation_models() -> None:
    """Import all model modules so Base.metadata contains the foundation tables."""

    import app.modules.academic_structure.models  # noqa: F401
    import app.modules.audit.models  # noqa: F401
    import app.modules.branches.models  # noqa: F401
    import app.modules.imports.models  # noqa: F401
    import app.modules.platform_admin.models  # noqa: F401
    import app.modules.students.models  # noqa: F401
    import app.modules.users.models  # noqa: F401
    import app.modules.workflows.models  # noqa: F401


def foundation_metadata_tables() -> dict[str, object]:
    """Return the registered SQLAlchemy foundation tables."""

    import_foundation_models()
    return {
        table_name: Base.metadata.tables[table_name]
        for table_name in sorted(FOUNDATION_TABLE_NAMES)
        if table_name in Base.metadata.tables
    }
