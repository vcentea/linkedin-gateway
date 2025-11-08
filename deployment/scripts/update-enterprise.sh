#!/bin/bash
# LinkedIn Gateway - Enterprise Edition Update Script
# This is a convenience wrapper for: update.sh enterprise

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Call the main update script with 'enterprise' parameter
exec "$SCRIPT_DIR/update.sh" enterprise
