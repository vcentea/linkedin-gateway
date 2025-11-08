#!/bin/bash
# =============================================================================
# Fix Database Password Mismatch
# =============================================================================
# This script updates the PostgreSQL password to match your .env file
#
# Use this when you get: "password authentication failed for user"
#
# Usage: ./fix-db-password.sh
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}LinkedIn Gateway - Fix Database Password${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""

cd "$DEPLOYMENT_DIR"

# Check which .env file to use
if [ -f ".env.prod.saas" ]; then
    ENV_FILE=".env.prod.saas"
    COMPOSE_CMD="docker compose -f docker-compose.yml -f docker-compose.saas.yml --env-file .env.prod.saas"
elif [ -f ".env" ]; then
    ENV_FILE=".env"
    COMPOSE_CMD="docker compose -f docker-compose.yml"
else
    echo -e "${RED}Error: No .env file found${NC}"
    exit 1
fi

echo -e "${YELLOW}Using environment file: ${ENV_FILE}${NC}"
echo ""

# Load credentials from .env
DB_USER=$(grep "^DB_USER=" "$ENV_FILE" | cut -d'=' -f2)
DB_PASSWORD=$(grep "^DB_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2)
DB_NAME=$(grep "^DB_NAME=" "$ENV_FILE" | cut -d'=' -f2)

if [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}Error: DB_USER or DB_PASSWORD not found in ${ENV_FILE}${NC}"
    exit 1
fi

echo -e "${YELLOW}Database credentials from ${ENV_FILE}:${NC}"
echo -e "  User: ${GREEN}${DB_USER}${NC}"
echo -e "  Password: ${GREEN}${DB_PASSWORD:0:4}****${NC}"
echo -e "  Database: ${GREEN}${DB_NAME}${NC}"
echo ""

# Check if postgres container is running
if ! $COMPOSE_CMD ps postgres | grep -q "Up"; then
    echo -e "${RED}Error: PostgreSQL container is not running${NC}"
    echo -e "${YELLOW}Starting containers...${NC}"
    $COMPOSE_CMD up -d postgres
    echo "Waiting for PostgreSQL to be ready..."
    sleep 10
fi

echo -e "${YELLOW}Updating PostgreSQL password...${NC}"

# Update the password in PostgreSQL
$COMPOSE_CMD exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" <<EOF
ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
\q
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Password updated successfully!${NC}"
    echo ""
    echo -e "${YELLOW}Restarting backend to apply changes...${NC}"
    $COMPOSE_CMD restart backend
    echo -e "${GREEN}✓ Backend restarted${NC}"
    echo ""
    echo -e "${GREEN}==============================================================================${NC}"
    echo -e "${GREEN}✓ Database password fixed!${NC}"
    echo -e "${GREEN}==============================================================================${NC}"
    echo ""
    echo -e "${BLUE}Test your authentication now.${NC}"
else
    echo -e "${RED}Error: Failed to update password${NC}"
    echo ""
    echo -e "${YELLOW}This usually means the current database password is different.${NC}"
    echo -e "${YELLOW}You may need to recreate the database (see Option 2 below)${NC}"
    echo ""
    echo -e "${BLUE}Option 2: Recreate Database${NC}"
    echo -e "  cd deployment/scripts"
    echo -e "  ./reset-db-saas.sh"
    exit 1
fi

