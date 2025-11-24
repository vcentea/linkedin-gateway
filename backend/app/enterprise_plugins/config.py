"""Configuration for Enterprise edition optional features.

These feature flags control which enterprise modules are enabled.
All features are disabled by default until implemented.
"""

import os
from typing import Optional


def get_bool_env(key: str, default: bool = False) -> bool:
    """Get boolean environment variable.
    
    Args:
        key: Environment variable name
        default: Default value if not set
        
    Returns:
        Boolean value from environment or default
    """
    value = os.getenv(key, "").lower()
    if value in ("true", "1", "yes", "on"):
        return True
    elif value in ("false", "0", "no", "off"):
        return False
    return default


class EnterpriseConfig:
    """Enterprise edition feature configuration."""
    
    # Organizations & Teams
    FEATURE_ORGANIZATIONS: bool = get_bool_env("ENT_FEATURE_ORGANIZATIONS", False)
    
    # Usage & Quotas
    FEATURE_QUOTAS: bool = get_bool_env("ENT_FEATURE_QUOTAS", False)
    
    # Audit Logs
    FEATURE_AUDIT_LOGS: bool = get_bool_env("ENT_FEATURE_AUDIT_LOGS", False)
    
    @classmethod
    def to_dict(cls) -> dict:
        """Convert config to dictionary.
        
        Returns:
            Dictionary of all feature flags
        """
        return {
            "organizations": cls.FEATURE_ORGANIZATIONS,
            "quotas": cls.FEATURE_QUOTAS,
            "audit_logs": cls.FEATURE_AUDIT_LOGS,
        }


enterprise_config = EnterpriseConfig()



