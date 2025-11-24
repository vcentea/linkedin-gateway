#!/bin/bash
# LinkedIn Gateway - Core Edition Update Script
# Convenience wrapper for: update_v2.sh core

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Call update_v2.sh with 'core' parameter
exec "$SCRIPT_DIR/update_v2.sh" core "$@"
