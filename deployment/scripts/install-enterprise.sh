#!/bin/bash
# LinkedIn Gateway - Enterprise Edition Installer
# This is a convenience wrapper for: install.sh enterprise

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Call the main install script with 'enterprise' parameter
exec "$SCRIPT_DIR/install.sh" enterprise



