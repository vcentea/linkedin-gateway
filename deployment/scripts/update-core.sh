#!/bin/bash
# LinkedIn Gateway - Open Core Edition Update Script
# This is a convenience wrapper for: update.sh core

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Call the main update script with 'core' parameter
exec "$SCRIPT_DIR/update.sh" core
