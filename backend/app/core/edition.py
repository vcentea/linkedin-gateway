"""Edition and channel detection for LinkedIn Gateway.

This module provides functionality to detect the edition (core vs saas) and
channel (default, railway_private, etc.) of the running backend instance.
It also defines the feature matrix that controls which features are available
in each edition.
"""

import os
from dataclasses import dataclass
from typing import Literal

EditionType = Literal["core", "saas", "enterprise"]
ChannelType = Literal["default", "railway_private"]


def get_edition() -> EditionType:
    """Get the current backend edition.
    
    Returns:
        The edition type: "core", "saas", or "enterprise". Defaults to "core" if
        the LG_BACKEND_EDITION environment variable is not set or invalid.
    """
    edition = os.getenv("LG_BACKEND_EDITION", "core").lower()
    if edition not in ("core", "saas", "enterprise"):
        return "core"
    return edition  # type: ignore


def get_channel() -> ChannelType:
    """Get the current deployment channel.
    
    Returns:
        The channel type. Defaults to "default" if the LG_CHANNEL
        environment variable is not set.
    """
    channel = os.getenv("LG_CHANNEL", "default").lower()
    if channel not in ("default", "railway_private"):
        return "default"
    return channel  # type: ignore


@dataclass
class FeatureMatrix:
    """Feature availability matrix for different editions and channels.
    
    This class determines which features are enabled based on the current
    edition and channel configuration.
    
    Attributes:
        allows_server_execution: Whether server-side execution is allowed
        has_local_accounts: Whether local account management is available
        requires_license: Whether a valid license is required
        has_licensing_server: Whether this instance provides licensing validation for others
    """
    
    allows_server_execution: bool
    has_local_accounts: bool
    requires_license: bool
    has_licensing_server: bool
    
    @classmethod
    def from_edition_and_channel(
        cls,
        edition: EditionType,
        channel: ChannelType
    ) -> "FeatureMatrix":
        """Create a feature matrix based on edition and channel.
        
        Args:
            edition: The backend edition (core, saas, or enterprise)
            channel: The deployment channel (default, railway_private)
            
        Returns:
            A FeatureMatrix instance configured for the given edition and channel.
        """
        if edition == "core":
            return cls._get_core_features(channel)
        elif edition == "saas":
            return cls._get_saas_features(channel)
        else:  # enterprise
            return cls._get_enterprise_features(channel)
    
    @classmethod
    def _get_core_features(cls, channel: ChannelType) -> "FeatureMatrix":
        """Get feature matrix for core edition.
        
        Args:
            channel: The deployment channel
            
        Returns:
            FeatureMatrix configured for core edition.
        """
        if channel == "railway_private":
            # Railway private template requires license
            return cls(
                allows_server_execution=True,
                has_local_accounts=True,
                requires_license=True,
                has_licensing_server=False,
            )
        else:
            # Default core edition: open source, no restrictions
            return cls(
                allows_server_execution=True,
                has_local_accounts=True,
                requires_license=False,
                has_licensing_server=False,
            )
    
    @classmethod
    def _get_saas_features(cls, channel: ChannelType) -> "FeatureMatrix":
        """Get feature matrix for SaaS edition.
        
        SaaS is the single cloud instance hosted by us. Users connect via browser
        extension in proxy mode only. Server-side execution is disabled for security
        and control. This is NOT self-hosted. Contains the licensing server.
        
        Args:
            channel: The deployment channel
            
        Returns:
            FeatureMatrix configured for SaaS edition.
        """
        return cls(
            allows_server_execution=False,  # SaaS users cannot use server_call=true
            has_local_accounts=False,       # No local accounts (OAuth/SSO only)
            requires_license=False,         # SaaS itself doesn't need license
            has_licensing_server=True,      # Contains the licensing server for others
        )
    
    @classmethod
    def _get_enterprise_features(cls, channel: ChannelType) -> "FeatureMatrix":
        """Get feature matrix for Enterprise edition.
        
        Enterprise is a self-hosted premium edition with more features than Core.
        Requires license validation against the SaaS licensing server.
        
        Args:
            channel: The deployment channel
            
        Returns:
            FeatureMatrix configured for Enterprise edition.
        """
        return cls(
            allows_server_execution=True,   # Enterprise can use server_call=true
            has_local_accounts=True,        # Local account management
            requires_license=True,          # Must validate license with SaaS
            has_licensing_server=False,     # Uses SaaS licensing server
        )
    
    def to_dict(self) -> dict:
        """Convert feature matrix to dictionary.
        
        Returns:
            Dictionary representation of the feature matrix.
        """
        return {
            "allows_server_execution": self.allows_server_execution,
            "has_local_accounts": self.has_local_accounts,
            "requires_license": self.requires_license,
            "has_licensing_server": self.has_licensing_server,
        }


def get_feature_matrix() -> FeatureMatrix:
    """Get the feature matrix for the current edition and channel.
    
    Returns:
        FeatureMatrix instance configured for the current runtime environment.
    """
    edition = get_edition()
    channel = get_channel()
    return FeatureMatrix.from_edition_and_channel(edition, channel)

