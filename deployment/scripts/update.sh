#!/bin/bash
# LinkedIn Gateway - Unified Update Script
# This script updates an existing LinkedIn Gateway installation with latest code and migrations
# Usage: ./update.sh [core|saas|enterprise]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get edition from parameter (default to core)
EDITION="${1:-core}"

# Validate edition
if [[ "$EDITION" != "core" && "$EDITION" != "saas" && "$EDITION" != "enterprise" ]]; then
    echo -e "${RED}Error: Invalid edition '$EDITION'. Must be 'core', 'saas', or 'enterprise'.${NC}"
    echo "Usage: $0 [core|saas|enterprise]"
    exit 1
fi

# Script directory and deployment root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$DEPLOYMENT_DIR/.." && pwd)"

# Set edition-specific variables
if [ "$EDITION" = "saas" ]; then
    EDITION_TITLE="SaaS Edition"
    DOCKER_COMPOSE_CMD="docker compose -f docker-compose.yml -f docker-compose.saas.yml"
elif [ "$EDITION" = "enterprise" ]; then
    EDITION_TITLE="Enterprise Edition"
    DOCKER_COMPOSE_CMD="docker compose -f docker-compose.yml -f docker-compose.enterprise.yml"
else
    EDITION_TITLE="Open Core Edition"
    DOCKER_COMPOSE_CMD="docker compose -f docker-compose.yml"
fi

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}LinkedIn Gateway - Update${NC}"
echo -e "${BLUE}Edition: $EDITION_TITLE${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Step 0: Check prerequisites
echo -e "${YELLOW}[0/6] Checking prerequisites...${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ Docker is running${NC}"

# Check if docker compose is available
if ! docker compose version > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker Compose is not available. Please install Docker Compose and try again.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ Docker Compose is available${NC}"

# Check if installation exists
if ! docker ps -a --filter "name=linkedin.*gateway" --format "{{.Names}}" | grep -q "gateway"; then
    echo -e "${YELLOW}No existing installation found.${NC}"
    echo -e "Please run ${GREEN}./install.sh $EDITION${NC} first for a fresh installation."
    exit 1
fi
echo -e "  ${GREEN}✓ Existing installation found${NC}"
echo ""

# Step 1: Pull latest code
echo -e "${YELLOW}[1/6] Pulling latest code from Git...${NC}"
cd "$PROJECT_ROOT"

if [ -d ".git" ]; then
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        echo -e "  ${YELLOW}⚠ Uncommitted changes detected${NC}"
        echo -e "  ${YELLOW}→ Stashing changes...${NC}"
        git stash push -m "Auto-stash before update $(date +%Y-%m-%d_%H-%M-%S)"
        echo -e "  ${GREEN}✓ Changes stashed (recover with: git stash pop)${NC}"
    fi

    # Pull latest changes - try multiple strategies to ensure success
    echo -e "  ${GREEN}→ Pulling latest code...${NC}"

    # Strategy 1: Normal pull
    if git pull origin main 2>/dev/null; then
        echo -e "  ${GREEN}✓ Code updated successfully${NC}"
    # Strategy 2: Pull with --allow-unrelated-histories
    elif git pull origin main --allow-unrelated-histories --no-edit 2>/dev/null; then
        echo -e "  ${GREEN}✓ Code updated (merged unrelated histories)${NC}"
    # Strategy 3: Fetch and hard reset (force update to match remote exactly)
    else
        echo -e "  ${YELLOW}→ Normal pull failed, fetching and resetting to remote...${NC}"
        if git fetch origin main 2>/dev/null && git reset --hard origin/main 2>/dev/null; then
            echo -e "  ${GREEN}✓ Code updated (force reset to remote)${NC}"
            echo -e "  ${YELLOW}  Note: Local code now matches remote exactly${NC}"
        else
            echo -e "  ${RED}✗ Failed to update code from Git${NC}"
            echo -e "  ${RED}  Cannot continue with outdated code${NC}"
            echo ""
            echo "Please manually update the code:"
            echo "  cd $PROJECT_ROOT"
            echo "  git fetch origin"
            echo "  git reset --hard origin/main"
            echo ""
            exit 1
        fi
    fi
else
    echo -e "  ${YELLOW}Not a git repository, skipping git pull${NC}"
fi
echo ""

# Change to deployment directory
cd "$DEPLOYMENT_DIR"

# Step 2: Pull latest Docker images
echo -e "${YELLOW}[2/6] Pulling latest Docker images...${NC}"
$DOCKER_COMPOSE_CMD pull
echo -e "  ${GREEN}✓ Images pulled${NC}"
echo ""

# Step 3: Rebuild and restart containers
echo -e "${YELLOW}[3/6] Rebuilding and restarting containers...${NC}"
echo -e "  → Building images..."
$DOCKER_COMPOSE_CMD build --no-cache

echo -e "  → Restarting services..."
$DOCKER_COMPOSE_CMD up -d

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Docker Compose deployment failed.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ Containers restarted${NC}"
echo ""

# Step 4: Wait for database to be ready
echo -e "${YELLOW}[4/6] Waiting for database to be ready...${NC}"
DB_CONTAINER="${EDITION}-db"
if [ "$EDITION" = "saas" ]; then
    DB_CONTAINER="linkedin-gateway-saas-db"
elif [ "$EDITION" = "enterprise" ]; then
    DB_CONTAINER="linkedin-gateway-enterprise-db"
else
    DB_CONTAINER="linkedin-gateway-core-db"
fi

echo -n "  → Waiting for database"
for i in {1..30}; do
    if docker exec $DB_CONTAINER pg_isready -U ${DB_USER:-linkedin_gateway_user} > /dev/null 2>&1; then
        echo ""
        echo -e "  ${GREEN}✓ Database is ready${NC}"
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

# Step 5: Apply database migrations
echo -e "${YELLOW}[5/6] Applying database migrations...${NC}"
echo -e "  ${BLUE}→ Running: alembic upgrade head${NC}"

if $DOCKER_COMPOSE_CMD exec -T backend sh -c "cd /app && alembic upgrade head"; then
    echo -e "  ${GREEN}✓ Database migrations applied successfully${NC}"
else
    echo -e "  ${RED}✗ Failed to apply database migrations${NC}"
    echo -e "  ${YELLOW}Check backend logs: $DOCKER_COMPOSE_CMD logs backend${NC}"
    exit 1
fi
echo ""

# Step 6: Wait for services and verify health
echo -e "${YELLOW}[6/6] Verifying services are healthy...${NC}"

# Get the backend port from .env or use default
BACKEND_PORT=$(grep "^BACKEND_PORT=" .env 2>/dev/null | cut -d'=' -f2 || echo "7778")
HEALTH_URL="http://localhost:${BACKEND_PORT}/health"

MAX_ATTEMPTS=30
ATTEMPT=0
READY=false

echo -n "  → Checking backend health"
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -s -f "$HEALTH_URL" > /dev/null 2>&1; then
        READY=true
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo -n "."
    sleep 2
done

echo ""

if [ "$READY" = true ]; then
    echo -e "  ${GREEN}✓ Backend is healthy and ready!${NC}"
else
    echo -e "  ${YELLOW}⚠ Backend did not respond within timeout period${NC}"
    echo -e "  ${YELLOW}Check logs: $DOCKER_COMPOSE_CMD logs backend${NC}"
fi
echo ""

# Print success message and service status
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}✓ Update Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "${YELLOW}Service Status:${NC}"
$DOCKER_COMPOSE_CMD ps
echo ""
echo -e "${GREEN}LinkedIn Gateway has been updated and is running:${NC}"
echo -e "  Backend:    ${GREEN}http://localhost:${BACKEND_PORT}${NC}"
echo -e "  Health:     ${GREEN}http://localhost:${BACKEND_PORT}/health${NC}"
echo -e "  API Docs:   ${GREEN}http://localhost:${BACKEND_PORT}/docs${NC}"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "  View logs:      ${GREEN}$DOCKER_COMPOSE_CMD logs -f${NC}"
echo -e "  Stop services:  ${GREEN}$DOCKER_COMPOSE_CMD down${NC}"
echo -e "  Restart:        ${GREEN}$DOCKER_COMPOSE_CMD restart${NC}"
echo ""
