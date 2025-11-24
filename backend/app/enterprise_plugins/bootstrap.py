"""Bootstrap module for Enterprise edition plugins.

This module registers optional Enterprise features and routes when
LG_BACKEND_EDITION=enterprise is set.
"""

import logging
from fastapi import FastAPI

from app.enterprise_plugins.config import enterprise_config
from app.enterprise_plugins import organizations, quotas, audit_logs


logger = logging.getLogger(__name__)


def register(app: FastAPI) -> None:
    """Register Enterprise edition plugins and routes.
    
    This function is called during application startup when the edition
    is set to "enterprise". It registers optional feature modules based
    on environment variable configuration.
    
    Args:
        app: The FastAPI application instance
    """
    logger.info("🏢 Initializing Enterprise edition plugins")
    
    features_enabled = []
    
    # Register Organizations & Teams API
    if enterprise_config.FEATURE_ORGANIZATIONS:
        app.include_router(
            organizations.router,
            prefix="/api/v1/enterprise",
            tags=["enterprise"]
        )
        features_enabled.append("Organizations & Teams")
        logger.info("  ✓ Organizations & Teams API enabled")
    else:
        logger.info("  ⊘ Organizations & Teams API disabled")
    
    # Register Usage & Quotas API
    if enterprise_config.FEATURE_QUOTAS:
        app.include_router(
            quotas.router,
            prefix="/api/v1/enterprise",
            tags=["enterprise"]
        )
        features_enabled.append("Usage & Quotas")
        logger.info("  ✓ Usage & Quotas API enabled")
    else:
        logger.info("  ⊘ Usage & Quotas API disabled")
    
    # Register Audit Logs API
    if enterprise_config.FEATURE_AUDIT_LOGS:
        app.include_router(
            audit_logs.router,
            prefix="/api/v1/enterprise",
            tags=["enterprise"]
        )
        features_enabled.append("Audit Logs")
        logger.info("  ✓ Audit Logs API enabled")
    else:
        logger.info("  ⊘ Audit Logs API disabled")
    
    # Add enterprise health/info endpoint (internal - hidden from public API docs)
    @app.get("/api/v1/enterprise/features", include_in_schema=False)
    async def get_enterprise_features():
        """Get information about enabled enterprise features.
        
        Internal endpoint - not included in public API documentation.
        
        Returns:
            Dictionary of feature status
        """
        return {
            "edition": "enterprise",
            "features": enterprise_config.to_dict(),
            "features_enabled": features_enabled,
            "message": "Enterprise edition is active. Enable features via ENT_FEATURE_* environment variables."
        }
    
    if features_enabled:
        logger.info(f"🏢 Enterprise plugins loaded: {', '.join(features_enabled)}")
    else:
        logger.info("🏢 Enterprise edition active (no optional features enabled)")



