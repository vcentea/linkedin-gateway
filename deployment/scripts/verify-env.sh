#!/bin/bash
# LinkedIn Gateway - Environment Verification Script
# Checks if .env file exists and has required variables

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$DEPLOYMENT_DIR"

echo -e "${YELLOW}======================================${NC}"
echo -e "${YELLOW}Environment Configuration Check${NC}"
echo -e "${YELLOW}======================================${NC}"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ .env file not found!${NC}"
    echo ""
    echo "Expected location: $(pwd)/.env"
    echo ""
    echo "Please run the install script first:"
    echo "  cd /opt/linkedin_gateway/app/deployment/scripts"
    echo "  ./install-saas.sh"
    exit 1
fi

echo -e "${GREEN}✓ .env file exists${NC}"
echo "  Location: $(pwd)/.env"
echo ""

# Check required variables
echo -e "${YELLOW}Checking required variables:${NC}"
echo ""

REQUIRED_VARS=(
    "DB_USER"
    "DB_PASSWORD"
    "DB_NAME"
    "SECRET_KEY"
    "JWT_SECRET_KEY"
    "LG_BACKEND_EDITION"
    "PORT"
)

OPTIONAL_VARS=(
    "LINKEDIN_CLIENT_ID"
    "LINKEDIN_CLIENT_SECRET"
    "PUBLIC_URL"
)

ALL_GOOD=true

for var in "${REQUIRED_VARS[@]}"; do
    if grep -q "^${var}=.\+" .env && ! grep -q "^${var}=CHANGE" .env; then
        VALUE=$(grep "^${var}=" .env | cut -d'=' -f2-)
        # Mask sensitive values
        if [[ "$var" == *"PASSWORD"* ]] || [[ "$var" == *"SECRET"* ]] || [[ "$var" == *"KEY"* ]]; then
            DISPLAY_VALUE="${VALUE:0:10}****"
        else
            DISPLAY_VALUE="$VALUE"
        fi
        echo -e "  ${GREEN}✓${NC} $var = $DISPLAY_VALUE"
    else
        echo -e "  ${RED}✗${NC} $var - NOT SET or placeholder"
        ALL_GOOD=false
    fi
done

echo ""
echo -e "${YELLOW}Optional variables (needed for OAuth):${NC}"
echo ""

for var in "${OPTIONAL_VARS[@]}"; do
    if grep -q "^${var}=.\+" .env && ! grep -q "^${var}=$" .env; then
        VALUE=$(grep "^${var}=" .env | cut -d'=' -f2-)
        if [[ "$var" == *"SECRET"* ]]; then
            DISPLAY_VALUE="${VALUE:0:10}****"
        else
            DISPLAY_VALUE="$VALUE"
        fi
        echo -e "  ${GREEN}✓${NC} $var = $DISPLAY_VALUE"
    else
        echo -e "  ${YELLOW}⚠${NC} $var - not set (required for LinkedIn OAuth)"
    fi
done

echo ""

if [ "$ALL_GOOD" = true ]; then
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}✓ Configuration looks good!${NC}"
    echo -e "${GREEN}======================================${NC}"
    
    # Check if LinkedIn OAuth is configured
    if ! grep -q "^LINKEDIN_CLIENT_ID=.\+" .env || grep -q "^LINKEDIN_CLIENT_ID=$" .env; then
        echo ""
        echo -e "${YELLOW}Note: LinkedIn OAuth not configured yet.${NC}"
        echo "To enable OAuth:"
        echo "  1. Get credentials from: https://www.linkedin.com/developers/apps"
        echo "  2. Edit .env and set LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, PUBLIC_URL"
        echo "  3. Restart: docker compose -f docker-compose.yml -f docker-compose.saas.yml restart"
    fi
else
    echo -e "${RED}======================================${NC}"
    echo -e "${RED}✗ Configuration has issues!${NC}"
    echo -e "${RED}======================================${NC}"
    echo ""
    echo "Please run the install script to regenerate .env:"
    echo "  cd /opt/linkedin_gateway/app/deployment/scripts"
    echo "  ./install-saas.sh"
fi

echo ""

