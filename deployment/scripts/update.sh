#!/bin/bash
# LinkedIn Gateway - Update Script
# This is a wrapper that calls update_v2.sh with your edition

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pass all arguments to update_v2.sh
exec "$SCRIPT_DIR/update_v2.sh" "$@"
