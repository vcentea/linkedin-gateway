#!/bin/bash
# LinkedIn Gateway - Open Core Edition Installer
# This is a convenience wrapper for: install.sh core

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Call the main install script with 'core' parameter
exec "$SCRIPT_DIR/install.sh" core
