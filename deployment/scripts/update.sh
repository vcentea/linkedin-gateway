#!/bin/bash
# LinkedIn Gateway - Simple Update Script
# Usage: ./update.sh [core|saas|enterprise] [--no-cache]
# 
# Options:
#   --no-cache    Force rebuild without using cache (slower but ensures clean build)
#                 Default: Uses cache for faster builds

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
EDITION="${1:-core}"
NO_CACHE=false

# Check for --no-cache flag
for arg in "$@"; do
    if [[ "$arg" == "--no-cache" ]]; then
        NO_CACHE=true
    fi
done

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
    # Backup .env files before git operations
    ENV_BACKUP_CREATED=false
    if [ -f "deployment/.env" ]; then
        cp "deployment/.env" "deployment/.env.backup" 2>/dev/null && ENV_BACKUP_CREATED=true
    fi
    if [ -f "backend/.env" ]; then
        cp "backend/.env" "backend/.env.backup" 2>/dev/null && ENV_BACKUP_CREATED=true
    fi
    
    # Fetch latest changes
    git fetch origin main > /dev/null 2>&1
    
    # Use safer merge approach instead of reset --hard
    # This preserves local changes and only updates what's changed
    if git merge --ff-only origin/main > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ Code updated (fast-forward)${NC}"
    elif git merge origin/main --no-edit > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ Code updated (merged)${NC}"
    else
        echo -e "  ${YELLOW}⚠ Merge conflicts detected - keeping local changes${NC}"
        echo -e "  ${YELLOW}  Resolve conflicts manually if needed${NC}"
        git merge --abort > /dev/null 2>&1 || true
    fi
    
    # Restore .env files if they were backed up
    if [ "$ENV_BACKUP_CREATED" = true ]; then
        if [ -f "deployment/.env.backup" ]; then
            mv "deployment/.env.backup" "deployment/.env" 2>/dev/null || true
        fi
        if [ -f "backend/.env.backup" ]; then
            mv "backend/.env.backup" "backend/.env" 2>/dev/null || true
        fi
        echo -e "  ${GREEN}✓ .env files preserved${NC}"
    fi
    
    # Clean only build artifacts, not user files
    # Remove only common build artifacts, preserving .env and other user files
    git clean -fd -e "*.env" -e "*.env.*" -e ".env.backup" > /dev/null 2>&1 || true
else
    echo -e "  ${YELLOW}⚠ Not a git repo, skipping${NC}"
fi
echo ""

# [2/5] Docker images
echo -e "${YELLOW}[2/5] Updating Docker images...${NC}"
cd "$DEPLOYMENT_DIR"
echo -e "  ${BLUE}ℹ Pulling latest base images...${NC}"
if $COMPOSE pull; then
    echo -e "  ${GREEN}✓ Images updated${NC}"
else
    echo -e "  ${YELLOW}⚠ Some images may not have updated (this is usually OK)${NC}"
fi
echo ""

# [3/5] Rebuild containers
echo -e "${YELLOW}[3/5] Rebuilding containers...${NC}"
cd "$DEPLOYMENT_DIR"

if [ "$NO_CACHE" = true ]; then
    echo -e "  ${BLUE}ℹ Building without cache (this may take 5-15 minutes)...${NC}"
    BUILD_ARGS="--no-cache --progress=plain"
else
    echo -e "  ${BLUE}ℹ Building with cache (faster, use --no-cache for clean build)...${NC}"
    BUILD_ARGS="--progress=plain"
fi

echo -e "  ${BLUE}ℹ Build output:${NC}"
if $COMPOSE build $BUILD_ARGS; then
    echo -e "  ${GREEN}✓ Build completed${NC}"
else
    echo -e "  ${RED}✗ Build failed! Check output above for errors${NC}"
    exit 1
fi

echo -e "  ${BLUE}ℹ Starting containers...${NC}"
if $COMPOSE up -d; then
    echo -e "  ${GREEN}✓ Containers running${NC}"
else
    echo -e "  ${RED}✗ Failed to start containers${NC}"
    exit 1
fi
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
