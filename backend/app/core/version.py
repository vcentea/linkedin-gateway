"""
Version management for LinkedIn Gateway API
"""

# API Version
API_VERSION = "1.1.0"
MIN_EXTENSION_VERSION = "1.0.0"  # Minimum compatible extension version

# Feature flags
FEATURES = {
    "multi_key_support": True,
    "instance_tracking": True,
    "self_deletion": True
}

def get_version_info():
    """Get version and feature information"""
    return {
        "version": API_VERSION,
        "features": FEATURES,
        "min_extension_version": MIN_EXTENSION_VERSION
    }

