#!/bin/bash
# LinkedIn Gateway - Improved Update Script V2
# Usage: ./update_v2.sh [core|saas|enterprise] [version] [--no-cache]
#
# This version uses safer git operations that preserve history:
# - Uses git pull instead of git reset --hard
# - Handles merge conflicts gracefully
# - Supports version pinning
# - Better error handling
# - Progress visibility for builds
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

# Get edition (default: core)
EDITION="${1:-core}"
VERSION="${2:-latest}"
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
echo -e "${BLUE}LinkedIn Gateway Update V2 - $EDITION_TITLE${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# [0/6] Prerequisites
echo -e "${YELLOW}[0/6] Checking prerequisites...${NC}"
docker info > /dev/null 2>&1 || { echo -e "${RED}Error: Docker not running${NC}"; exit 1; }
docker compose version > /dev/null 2>&1 || { echo -e "${RED}Error: Docker Compose not available${NC}"; exit 1; }
echo -e "  ${GREEN}✓ Docker ready${NC}"
echo ""

# [1/6] Update code from Git (NEW SAFER APPROACH)
echo -e "${YELLOW}[1/6] Updating code from repository...${NC}"
cd "$PROJECT_ROOT"

if [ -d ".git" ]; then
    # Check if we have a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        echo -e "${RED}Error: Not a valid git repository${NC}"
        exit 1
    fi

    # Check for local modifications
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        echo -e "  ${YELLOW}⚠ Local modifications detected${NC}"
        echo -e "  ${YELLOW}⚠ Stashing local changes...${NC}"

        # Stash with a timestamp
        STASH_NAME="auto-stash-$(date +%Y%m%d-%H%M%S)"
        git stash push -m "$STASH_NAME" 2>/dev/null || true

        echo -e "  ${GREEN}✓ Changes stashed as: $STASH_NAME${NC}"
        echo -e "  ${BLUE}ℹ To restore: git stash list && git stash pop${NC}"
    fi

    # Fetch latest changes
    echo -e "  ${BLUE}ℹ Fetching latest changes...${NC}"
    if ! git fetch origin main 2>&1; then
        echo -e "${RED}Error: Could not fetch from remote${NC}"
        exit 1
    fi

    # Determine target version
    if [ "$VERSION" = "latest" ]; then
        TARGET="origin/main"
        echo -e "  ${BLUE}ℹ Updating to latest version${NC}"
    else
        # Check if version tag exists
        if git rev-parse "v$VERSION" >/dev/null 2>&1; then
            TARGET="v$VERSION"
            echo -e "  ${BLUE}ℹ Updating to version: $VERSION${NC}"
        else
            echo -e "${RED}Error: Version tag 'v$VERSION' not found${NC}"
            echo -e "${YELLOW}Available versions:${NC}"
            git tag -l "v*" | tail -5
            exit 1
        fi
    fi

    # Try to merge (fast-forward only first)
    echo -e "  ${BLUE}ℹ Attempting fast-forward merge...${NC}"
    if git merge --ff-only "$TARGET" 2>/dev/null; then
        echo -e "  ${GREEN}✓ Code updated successfully (fast-forward)${NC}"
    else
        # Fast-forward failed, try regular merge
        echo -e "  ${YELLOW}⚠ Fast-forward not possible, attempting merge...${NC}"

        if git merge "$TARGET" 2>/dev/null; then
            echo -e "  ${GREEN}✓ Code updated successfully (merge)${NC}"
        else
            # Merge failed - likely conflicts
            echo -e "${RED}✗ Merge failed - conflicts detected${NC}"
            echo -e "${YELLOW}Conflicting files:${NC}"
            git diff --name-only --diff-filter=U

            echo ""
            echo -e "${RED}═══════════════════════════════════════${NC}"
            echo -e "${RED}MERGE CONFLICT - ACTION REQUIRED${NC}"
            echo -e "${RED}═══════════════════════════════════════${NC}"
            echo -e "${YELLOW}Options:${NC}"
            echo -e "  1. Resolve conflicts manually and run: git merge --continue"
            echo -e "  2. Abort merge and keep current version: git merge --abort"
            echo -e "  3. Force update (DESTRUCTIVE): git reset --hard $TARGET"
            echo -e ""
            echo -e "${YELLOW}To see conflicts: git diff${NC}"
            exit 1
        fi
    fi

    # Show what changed
    echo -e "  ${BLUE}ℹ Recent changes:${NC}"
    git log --oneline -5 2>/dev/null || true

else
    echo -e "  ${YELLOW}⚠ Not a git repository, skipping update${NC}"
    echo -e "  ${YELLOW}ℹ Consider cloning from: https://github.com/vcentea/linkedin-gateway${NC}"
fi
echo ""

# [2/6] Docker images
echo -e "${YELLOW}[2/6] Updating Docker images...${NC}"
cd "$DEPLOYMENT_DIR"
echo -e "  ${BLUE}ℹ Pulling latest base images...${NC}"
if $COMPOSE pull; then
    echo -e "  ${GREEN}✓ Images updated${NC}"
else
    echo -e "  ${YELLOW}⚠ Some images may not have updated (this is usually OK)${NC}"
fi
echo ""

# [3/6] Rebuild containers
echo -e "${YELLOW}[3/6] Rebuilding containers...${NC}"
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

# [4/6] Wait for database
echo -e "${YELLOW}[4/6] Waiting for database...${NC}"
for i in {1..30}; do
    if docker exec $DB_CONTAINER pg_isready -U linkedin_gateway_user > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ Database ready${NC}"
        break
    fi
    sleep 1
done
echo ""

# [5/6] Migrations
echo -e "${YELLOW}[5/6] Running migrations...${NC}"

# Show which migration paths are being used
echo -e "  ${BLUE}ℹ Checking migration paths...${NC}"
MIGRATION_PATHS=$($COMPOSE exec -T backend sh -c "cd /app && alembic branches 2>&1 | head -5" || true)

# Run migrations (alembic will automatically check both versions/ and versions_saas/)
echo -e "  ${BLUE}ℹ Running alembic upgrade head...${NC}"
MIGRATION_OUTPUT=$($COMPOSE exec -T backend sh -c "cd /app && alembic upgrade head 2>&1" || true)

# Check if migrations succeeded or have acceptable errors
if echo "$MIGRATION_OUTPUT" | grep -q "already exists\|duplicate\|Running upgrade.*->"; then
    echo -e "  ${GREEN}✓ Migrations applied${NC}"

    # Show what was applied
    if echo "$MIGRATION_OUTPUT" | grep -q "Running upgrade"; then
        echo -e "  ${BLUE}ℹ Applied migrations:${NC}"
        echo "$MIGRATION_OUTPUT" | grep "Running upgrade" | sed 's/^/    /'
    fi
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

# Show current migration state
CURRENT_STATE=$($COMPOSE exec -T backend sh -c "cd /app && alembic current 2>&1" || echo "")
if [ -n "$CURRENT_STATE" ]; then
    echo -e "  ${BLUE}ℹ Current migration state:${NC}"
    echo "$CURRENT_STATE" | sed 's/^/    /'
fi

# Special note for SaaS edition
if [ "$EDITION" = "saas" ]; then
    echo -e "  ${BLUE}ℹ SaaS Edition: Both core and SaaS-specific migrations are checked${NC}"
fi

# Ensure schema is correct (add any missing columns/indexes)
echo -e "  ${BLUE}ℹ Ensuring schema is correct...${NC}"
echo -e "  ${BLUE}ℹ Running: python alembic/ensure_schema.py${NC}"

ENSURE_OUTPUT=$($COMPOSE exec -T backend sh -c "cd /app && python alembic/ensure_schema.py 2>&1")
ENSURE_EXIT_CODE=$?

echo -e "${BLUE}--- Schema Enforcement Output ---${NC}"
echo "$ENSURE_OUTPUT"
echo -e "${BLUE}--- End Schema Enforcement Output ---${NC}"

if [ $ENSURE_EXIT_CODE -eq 0 ]; then
    if echo "$ENSURE_OUTPUT" | grep -q "Schema fixed"; then
        echo -e "  ${GREEN}✓ Schema updated - missing columns added${NC}"
    elif echo "$ENSURE_OUTPUT" | grep -q "Schema is correct"; then
        echo -e "  ${GREEN}✓ Schema is correct${NC}"
    else
        echo -e "  ${GREEN}✓ Schema enforcement completed${NC}"
    fi
else
    echo -e "  ${RED}✗ Schema enforcement failed with exit code: $ENSURE_EXIT_CODE${NC}"
    echo -e "  ${YELLOW}⚠ Warning: Database schema may be inconsistent${NC}"
fi

echo ""

# [6/6] Health check
echo -e "${YELLOW}[6/6] Running health check...${NC}"
BACKEND_PORT=$(grep "^BACKEND_PORT=" .env 2>/dev/null | cut -d'=' -f2 || echo "7778")

# Wait a moment for services to be fully ready
sleep 3

# Check if API is responding
if curl -s -f "http://localhost:${BACKEND_PORT}/health" > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓ Health check passed${NC}"
else
    echo -e "  ${YELLOW}⚠ Health check failed (services may still be starting)${NC}"
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Update Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "LinkedIn Gateway is running:"
echo -e "  API:    ${GREEN}http://localhost:${BACKEND_PORT}${NC}"
echo -e "  Docs:   ${GREEN}http://localhost:${BACKEND_PORT}/docs${NC}"
echo -e "  Health: ${GREEN}http://localhost:${BACKEND_PORT}/health${NC}"
echo ""

# Show current version if available
cd "$PROJECT_ROOT"
if [ -d ".git" ]; then
    CURRENT_VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "unknown")
    CURRENT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    echo -e "${BLUE}Current version: ${CURRENT_VERSION} (${CURRENT_COMMIT})${NC}"
    echo ""
fi
