#!/bin/bash
# LinkedIn Gateway - Enterprise Edition Update Script
# Convenience wrapper for: update_v2.sh enterprise

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Call update_v2.sh with 'enterprise' parameter
exec "$SCRIPT_DIR/update_v2.sh" enterprise "$@"
