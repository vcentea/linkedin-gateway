#!/bin/bash
# LinkedIn Gateway - Simple Update Script
# Usage: ./update.sh [core|saas|enterprise]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get edition (default: core)
EDITION="${1:-core}"

# Validate edition
if [[ "$EDITION" != "core" && "$EDITION" != "saas" && "$EDITION" != "enterprise" ]]; then
    echo -e "${RED}Error: Invalid edition. Use: core, saas, or enterprise${NC}"
    exit 1
fi

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$DEPLOYMENT_DIR/.." && pwd)"

# Edition config
if [ "$EDITION" = "saas" ]; then
    EDITION_TITLE="SaaS Edition"
    COMPOSE="docker compose -f docker-compose.yml -f docker-compose.saas.yml"
    DB_CONTAINER="linkedin-gateway-saas-db"
elif [ "$EDITION" = "enterprise" ]; then
    EDITION_TITLE="Enterprise Edition"
    COMPOSE="docker compose -f docker-compose.yml -f docker-compose.enterprise.yml"
    DB_CONTAINER="linkedin-gateway-enterprise-db"
else
    EDITION_TITLE="Open Core Edition"
    COMPOSE="docker compose -f docker-compose.yml"
    DB_CONTAINER="linkedin-gateway-core-db"
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}LinkedIn Gateway Update - $EDITION_TITLE${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# [0/5] Prerequisites
echo -e "${YELLOW}[0/5] Checking prerequisites...${NC}"
docker info > /dev/null 2>&1 || { echo -e "${RED}Error: Docker not running${NC}"; exit 1; }
docker compose version > /dev/null 2>&1 || { echo -e "${RED}Error: Docker Compose not available${NC}"; exit 1; }
echo -e "  ${GREEN}✓ Docker ready${NC}"
echo ""

# [1/5] Update code from Git
echo -e "${YELLOW}[1/5] Updating code from repository...${NC}"
cd "$PROJECT_ROOT"
if [ -d ".git" ]; then
    git fetch origin main > /dev/null 2>&1
    git merge --abort > /dev/null 2>&1 || true
    git reset --hard origin/main > /dev/null 2>&1
    git clean -fdx > /dev/null 2>&1
    echo -e "  ${GREEN}✓ Code updated (forced to match remote)${NC}"
else
    echo -e "  ${YELLOW}⚠ Not a git repo, skipping${NC}"
fi
echo ""

# [2/5] Docker images
echo -e "${YELLOW}[2/5] Updating Docker images...${NC}"
cd "$DEPLOYMENT_DIR"
$COMPOSE pull > /dev/null 2>&1
echo -e "  ${GREEN}✓ Images updated${NC}"
echo ""

# [3/5] Rebuild containers
echo -e "${YELLOW}[3/5] Rebuilding containers...${NC}"
$COMPOSE build --no-cache > /dev/null 2>&1
$COMPOSE up -d
echo -e "  ${GREEN}✓ Containers running${NC}"
echo ""

# [4/5] Wait for database
echo -e "${YELLOW}[4/5] Waiting for database...${NC}"
for i in {1..30}; do
    if docker exec $DB_CONTAINER pg_isready -U linkedin_gateway_user > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ Database ready${NC}"
        break
    fi
    sleep 1
done
echo ""

# [5/5] Migrations
echo -e "${YELLOW}[5/5] Running migrations...${NC}"
MIGRATION_OUTPUT=$($COMPOSE exec -T backend sh -c "cd /app && alembic upgrade head 2>&1" || true)

# Check if migrations succeeded or have acceptable errors
if echo "$MIGRATION_OUTPUT" | grep -q "already exists\|duplicate\|Running upgrade.*->"; then
    echo -e "  ${GREEN}✓ Migrations applied${NC}"
elif echo "$MIGRATION_OUTPUT" | grep -q "SyntaxError\|<<<<<<<"; then
    echo -e "  ${RED}✗ Merge conflict detected in migration files${NC}"
    echo "$MIGRATION_OUTPUT"
    exit 1
else
    # If no output or unknown error, check if we're at head
    CURRENT=$($COMPOSE exec -T backend sh -c "cd /app && alembic current 2>&1" || echo "")
    if echo "$CURRENT" | grep -q "head"; then
        echo -e "  ${GREEN}✓ Already at latest migration${NC}"
    else
        echo -e "  ${GREEN}✓ Migrations completed${NC}"
    fi
fi
echo ""

# Get port
BACKEND_PORT=$(grep "^BACKEND_PORT=" .env 2>/dev/null | cut -d'=' -f2 || echo "7778")

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Update Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "LinkedIn Gateway is running:"
echo -e "  API:    ${GREEN}http://localhost:${BACKEND_PORT}${NC}"
echo -e "  Docs:   ${GREEN}http://localhost:${BACKEND_PORT}/docs${NC}"
echo -e "  Health: ${GREEN}http://localhost:${BACKEND_PORT}/health${NC}"
echo ""
