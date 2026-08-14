"""Local development bootstrap for overriding authentication."""
import logging
from uuid import UUID
from fastapi import Request

from app.main import app
from app.core.security.jwt import AuthenticatedPrincipal
from app.core.security.dependencies import get_request_context

logger = logging.getLogger(__name__)

# --- Local Testing Mock ---
async def mock_request_context(request: Request) -> AuthenticatedPrincipal:
    """Mock context to bypass Auth for local development only."""
    # Tenant: Test Tenant
    tenant_id = str(UUID("b1621609-cee0-4f12-99bc-8bd8560ae02c"))
    # Branch: Test Branch
    branch_id = str(UUID("f12c2100-e828-42ea-ac6b-e70542c684e6"))
    user_id = UUID("18b87bea-cbdd-4274-82c6-8b5e8ec211cb")
    
    return AuthenticatedPrincipal(
        app_user_id=user_id,
        claims={
            "tenant_id": tenant_id,
            "branch_id": branch_id,
            "role": "OFFICE_STAFF",
            "permissions": [
                "import.upload",
                "import.validate",
                "import.submit",
                "import.approve",
                "import.commit"
            ]
        }
    )

logger.info("APPLYING LOCAL DEVELOPMENT AUTHENTICATION BYPASS")
app.dependency_overrides[get_request_context] = mock_request_context
