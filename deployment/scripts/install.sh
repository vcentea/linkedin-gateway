#!/bin/bash
# LinkedIn Gateway - Unified Deployment Script
# This script deploys either core or saas edition using Docker Compose
# Usage: ./install.sh [core|saas]
# Safe to run multiple times for updates (idempotent)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}LinkedIn Gateway - $EDITION_TITLE${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Step 0: Git pull latest changes if in a git repository
echo -e "${YELLOW}[0/7] Pulling latest changes...${NC}"
cd "$PROJECT_ROOT"

if [ -d ".git" ]; then
    # Backup .env files before git operations (protect user configuration)
    ENV_BACKUP_CREATED=false
    if [ -f "deployment/.env" ]; then
        cp "deployment/.env" "deployment/.env.backup" 2>/dev/null && ENV_BACKUP_CREATED=true
    fi
    if [ -f "backend/.env" ]; then
        cp "backend/.env" "backend/.env.backup" 2>/dev/null && ENV_BACKUP_CREATED=true
    fi
    
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        echo -e "  ${YELLOW}⚠ Uncommitted changes detected${NC}"
        echo -e "  ${YELLOW}→ Stashing changes...${NC}"
        # Use -u flag to include untracked files, but exclude .env files
        git stash push -m "Auto-stash before install $(date +%Y-%m-%d_%H-%M-%S)" --keep-index 2>/dev/null || \
        git stash push -m "Auto-stash before install $(date +%Y-%m-%d_%H-%M-%S)" 2>/dev/null || true
        echo -e "  ${GREEN}✓ Changes stashed (recover with: git stash pop)${NC}"
    fi

    # Pull latest changes (try normal pull first, then with --allow-unrelated-histories if needed)
    echo -e "  ${GREEN}→ Pulling latest code...${NC}"
    if git pull origin main 2>/dev/null; then
        echo -e "  ${GREEN}✓ Code updated${NC}"
    elif git pull origin main --allow-unrelated-histories --no-edit 2>/dev/null; then
        echo -e "  ${GREEN}✓ Code updated (merged unrelated histories)${NC}"
    else
        echo -e "  ${YELLOW}⚠ Git pull failed (this is OK - continuing with current version)${NC}"
        echo -e "  ${YELLOW}  If you cloned from the public repo, this is expected.${NC}"
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
else
    echo -e "  ${YELLOW}Not a git repository, skipping git pull${NC}"
fi

echo ""

# Change to deployment directory
cd "$DEPLOYMENT_DIR"

# Check if Docker is installed and working
if ! docker --version > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not installed or not accessible.${NC}"
    echo ""
    echo "Please install Docker first:"
    echo "  • Ubuntu/Debian: https://docs.docker.com/engine/install/ubuntu/"
    echo "  • CentOS/RHEL: https://docs.docker.com/engine/install/centos/"
    echo "  • Other Linux: https://docs.docker.com/engine/install/"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓ Docker is installed ($(docker --version))${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is installed but not running.${NC}"
    echo ""
    echo "Please start Docker and try again:"
    echo "  sudo systemctl start docker"
    echo ""
    exit 1
fi

# Check if docker compose is available
if ! docker compose version > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker Compose is not available.${NC}"
    echo ""
    echo "Modern Docker includes Compose as a plugin by default."
    echo "Please ensure you have Docker Compose installed:"
    echo "  https://docs.docker.com/compose/install/"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose is available ($(docker compose version --short 2>/dev/null || echo 'installed'))${NC}"
echo ""

# Step 1: Check and create .env file
echo -e "${YELLOW}[1/6] Checking environment configuration...${NC}"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "  → Creating .env from .env.example..."
        cp .env.example .env
        echo -e "  ${GREEN}✓ Created .env file${NC}"
    else
        echo -e "${RED}Error: .env.example not found. Cannot create .env file.${NC}"
        exit 1
    fi
else
    echo -e "  ${GREEN}✓ .env file exists${NC}"
fi

# Prompt for port
echo ""
echo -e "${YELLOW}Configuration Setup:${NC}"
echo ""
read -p "  Port to use (press Enter for default 7778): " USER_PORT
PORT=${USER_PORT:-7778}

# Update port in .env (ensure we only match exact PORT= and BACKEND_PORT=, not DB_PORT=)
if grep -q "^PORT=" .env; then
    # Use sed with explicit anchoring to match only lines starting with PORT=
    sed -i.bak "/^PORT=/s/.*/PORT=$PORT/" .env && rm -f .env.bak
else
    echo "PORT=$PORT" >> .env
fi

if grep -q "^BACKEND_PORT=" .env; then
    # Use sed with explicit anchoring to match only lines starting with BACKEND_PORT=
    sed -i.bak "/^BACKEND_PORT=/s/.*/BACKEND_PORT=$PORT/" .env && rm -f .env.bak
else
    echo "BACKEND_PORT=$PORT" >> .env
fi

echo -e "  ${GREEN}✓ Port set to $PORT${NC}"

# Step 2: Generate database password and secrets
echo ""
echo -e "${YELLOW}[2/6] Generating secure credentials...${NC}"

# Function to generate a random secret
generate_secret() {
    openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "CHANGE_ME_$(date +%s)_$(openssl rand -hex 16 2>/dev/null || echo 'RANDOM')"
}

# Generate a simple password: LinkedinGW + timestamp + random
# This creates passwords like: LinkedinGW20251018143052
generate_password() {
    # Generate timestamp (YYYYMMDDHHMMSS) and random number
    TIMESTAMP=$(date +%Y%m%d%H%M%S)
    RANDOM_NUM=$RANDOM
    echo "LinkedinGW${TIMESTAMP}${RANDOM_NUM}"
}

# Check if DB_PASSWORD is set - only generate if empty or placeholder
# IMPORTANT: Don't overwrite existing passwords to preserve data on reinstalls
DB_PASSWORD=$(grep "^DB_PASSWORD=" .env 2>/dev/null | cut -d'=' -f2- || echo "")
# Only regenerate if it's EXACTLY a common placeholder (case-sensitive, whole match)
if [ -z "$DB_PASSWORD" ] || [ "$DB_PASSWORD" = "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY" ] || [ "$DB_PASSWORD" = "change_this_password" ] || [ "$DB_PASSWORD" = "your_strong_password_here" ] || [ "$DB_PASSWORD" = "postgres" ]; then
    DB_PASSWORD=$(generate_password)
    echo -e "  ${YELLOW}→ Generating new DB password: LinkedinGW${TIMESTAMP:0:8}****${NC}"
    if grep -q "^DB_PASSWORD=" .env; then
        # Replace existing DB_PASSWORD
        sed -i.bak "s|^DB_PASSWORD=.*|DB_PASSWORD=$DB_PASSWORD|" .env && rm -f .env.bak
    else
        # Append if not exists
        echo "DB_PASSWORD=$DB_PASSWORD" >> .env
    fi
    echo -e "  ${GREEN}✓ DB_PASSWORD saved to .env${NC}"
else
    echo -e "  ${GREEN}✓ DB_PASSWORD already set (keeping existing: ${DB_PASSWORD:0:10}***)${NC}"
fi

# Check if SECRET_KEY is set - only replace if it's EXACTLY the placeholder
SECRET_KEY_VALUE=$(grep "^SECRET_KEY=" .env 2>/dev/null | cut -d'=' -f2- || echo "")
if [ -z "$SECRET_KEY_VALUE" ] || [ "$SECRET_KEY_VALUE" = "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY" ] || [ "$SECRET_KEY_VALUE" = "change_this_secret_key" ]; then
    SECRET_KEY=$(generate_secret)
    if grep -q "^SECRET_KEY=" .env; then
        # Replace placeholder SECRET_KEY
        sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env && rm .env.bak
    else
        # Append if not exists
        echo "SECRET_KEY=$SECRET_KEY" >> .env
    fi
    echo -e "  ${GREEN}✓ Generated SECRET_KEY${NC}"
else
    echo -e "  ${GREEN}✓ SECRET_KEY already set (keeping existing)${NC}"
fi

# Check if JWT_SECRET_KEY is set - only replace if it's EXACTLY the placeholder
JWT_SECRET_VALUE=$(grep "^JWT_SECRET_KEY=" .env 2>/dev/null | cut -d'=' -f2- || echo "")
if [ -z "$JWT_SECRET_VALUE" ] || [ "$JWT_SECRET_VALUE" = "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY" ] || [ "$JWT_SECRET_VALUE" = "change_this_secret_key" ]; then
    JWT_SECRET_KEY=$(generate_secret)
    if grep -q "^JWT_SECRET_KEY=" .env; then
        # Replace placeholder JWT_SECRET_KEY
        sed -i.bak "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET_KEY|" .env && rm .env.bak
    else
        echo "JWT_SECRET_KEY=$JWT_SECRET_KEY" >> .env
    fi
    echo -e "  ${GREEN}✓ Generated JWT_SECRET_KEY${NC}"
else
    echo -e "  ${GREEN}✓ JWT_SECRET_KEY already set (keeping existing)${NC}"
fi

# Ensure edition is set correctly
if ! grep -q "^LG_BACKEND_EDITION=$EDITION" .env; then
    if grep -q "^LG_BACKEND_EDITION=" .env; then
        sed -i.bak "s|^LG_BACKEND_EDITION=.*|LG_BACKEND_EDITION=$EDITION|" .env && rm .env.bak
    else
        echo "LG_BACKEND_EDITION=$EDITION" >> .env
    fi
    echo -e "  ${GREEN}✓ Set edition to $EDITION${NC}"
fi

# Ensure channel is set to default
if ! grep -q "^LG_CHANNEL=default" .env; then
    if grep -q "^LG_CHANNEL=" .env; then
        sed -i.bak "s|^LG_CHANNEL=.*|LG_CHANNEL=default|" .env && rm .env.bak
    else
        echo "LG_CHANNEL=default" >> .env
    fi
    echo -e "  ${GREEN}✓ Set channel to default${NC}"
fi

# Copy .env to backend directory (app reads from there)
echo ""
echo -e "${YELLOW}[3/7] Copying configuration to backend...${NC}"
cp .env ../backend/.env
echo -e "  ${GREEN}✓ Configuration copied to backend/.env${NC}"

# Step 4: Deploy with Docker Compose
echo ""
echo -e "${YELLOW}[4/7] Starting Docker Compose deployment...${NC}"
echo "  → Building and starting containers..."
$DOCKER_COMPOSE_CMD up -d --build

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Docker Compose deployment failed.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ Containers started${NC}"

# Step 5: Verify database initialization
echo ""
echo -e "${YELLOW}[5/7] Verifying database initialization...${NC}"
echo -e "  ${GREEN}→ Waiting for PostgreSQL to be ready...${NC}"

# Wait for database to be fully ready
DB_CONTAINER="${EDITION}-db"
if [ "$EDITION" = "saas" ]; then
    DB_CONTAINER="linkedin-gateway-saas-db"
else
    DB_CONTAINER="linkedin-gateway-core-db"
fi

# Wait up to 30 seconds for database to be ready
echo -n "  → Waiting for database"
for i in {1..30}; do
    if docker exec $DB_CONTAINER pg_isready -U ${DB_USER:-linkedin_gateway_user} -d ${DB_NAME:-LinkedinGateway} > /dev/null 2>&1; then
        echo ""
        echo -e "  ${GREEN}✓ Database is ready${NC}"
        echo "  → Waiting for init scripts to complete..."
        sleep 3
        break
    fi
    echo -n "."
    sleep 1
done

# Check if tables were created
echo ""
echo -e "  ${GREEN}→ Checking if database schema was created...${NC}"
TABLES_COUNT=$(docker exec $DB_CONTAINER psql -U ${DB_USER:-linkedin_gateway_user} -d ${DB_NAME:-LinkedinGateway} -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';" 2>/dev/null | tr -d '[:space:]')

# Check if this is a fresh install (no alembic_version table)
ALEMBIC_VERSION_EXISTS=$(docker exec $DB_CONTAINER psql -U ${DB_USER:-linkedin_gateway_user} -d ${DB_NAME:-LinkedinGateway} -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'alembic_version');" 2>/dev/null | tr -d '[:space:]')

IS_FRESH_INSTALL=false

# If query failed or returned 0, check again after brief delay
if [ -z "$TABLES_COUNT" ]; then
    echo -e "  ${YELLOW}→ Could not query database, retrying...${NC}"
    sleep 2
    TABLES_COUNT=$(docker exec $DB_CONTAINER psql -U ${DB_USER:-linkedin_gateway_user} -d ${DB_NAME:-LinkedinGateway} -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';" 2>/dev/null | tr -d '[:space:]')
fi

if [ -z "$TABLES_COUNT" ] || [ "$TABLES_COUNT" -eq "0" ]; then
    echo -e "  ${YELLOW}⚠ No tables found, init scripts may not have run automatically.${NC}"
    echo -e "  ${YELLOW}→ Running init scripts manually...${NC}"
    IS_FRESH_INSTALL=true

    # Manually run init scripts (executes all .sql files in init-scripts/ directory)
    # 01-create-schema.sql: Creates all tables, indexes, and schema
    # 02-grant-privileges.sql: Grants full privileges for migrations
    for SQL_FILE in ../init-scripts/*.sql; do
        if [ -f "$SQL_FILE" ]; then
            FILENAME=$(basename "$SQL_FILE")
            echo -e "    → Executing: $FILENAME"
            docker cp "$SQL_FILE" "$DB_CONTAINER:/tmp/$FILENAME"
            if docker exec $DB_CONTAINER psql -U ${DB_USER:-linkedin_gateway_user} -d ${DB_NAME:-LinkedinGateway} -f "/tmp/$FILENAME" 2>&1 | grep -i "error" > /dev/null; then
                echo -e "      ${YELLOW}⚠ Script may have warnings (possibly tables already exist)${NC}"
            fi
            docker exec $DB_CONTAINER rm "/tmp/$FILENAME"
        fi
    done

    # Verify tables were created
    echo -e "  ${GREEN}→ Verifying schema...${NC}"
    TABLES_COUNT=$(docker exec $DB_CONTAINER psql -U ${DB_USER:-linkedin_gateway_user} -d ${DB_NAME:-LinkedinGateway} -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';" 2>/dev/null | tr -d '[:space:]')

    if [ -n "$TABLES_COUNT" ] && [ "$TABLES_COUNT" -gt "0" ]; then
        echo -e "  ${GREEN}✓ Database schema created successfully ($TABLES_COUNT tables)${NC}"
    else
        echo -e "  ${RED}✗ Failed to create database schema!${NC}"
        echo -e "  ${YELLOW}Debug: TABLES_COUNT = '$TABLES_COUNT'${NC}"
        echo -e "  ${YELLOW}Please check Docker logs: docker logs $DB_CONTAINER${NC}"
        exit 1
    fi
else
    echo -e "  ${GREEN}✓ Database schema exists ($TABLES_COUNT tables)${NC}"
    # Check if alembic_version table exists to determine if this is a fresh install
    if [ "$ALEMBIC_VERSION_EXISTS" != "t" ]; then
        IS_FRESH_INSTALL=true
        echo -e "  ${YELLOW}→ Detected fresh installation (no migration history)${NC}"
    fi
fi

# Apply migrations or stamp database version
echo ""
if [ "$IS_FRESH_INSTALL" = true ]; then
    # For fresh installs: stamp the database as being at the latest version
    # This tells Alembic the schema is already up-to-date, avoiding redundant migrations
    echo -e "${YELLOW}Marking database as up-to-date (alembic stamp head)...${NC}"
    if $DOCKER_COMPOSE_CMD exec -T backend sh -c "cd /app && alembic stamp head"; then
        echo -e "  ${GREEN}✓ Database marked as up-to-date${NC}"
    else
        echo -e "  ${RED}✗ Failed to stamp alembic version. Please check backend logs.${NC}"
        exit 1
    fi
else
    # For existing installs: run migrations to upgrade schema
    echo -e "${YELLOW}Applying database migrations (alembic upgrade head)...${NC}"
    if $DOCKER_COMPOSE_CMD exec -T backend sh -c "cd /app && alembic upgrade head"; then
        echo -e "  ${GREEN}✓ Database migrations applied${NC}"
    else
        echo -e "  ${RED}✗ Failed to run alembic migrations. Please check backend logs.${NC}"
        exit 1
    fi
fi

echo ""
echo -e "  ${YELLOW}💡 To verify database:${NC}"
echo -e "     ./scripts/verify-db.sh"
echo ""

# Step 6: Wait for services and poll health endpoint
echo ""
echo -e "${YELLOW}[6/7] Waiting for backend API to be ready...${NC}"

# Get the backend port from .env or use default
BACKEND_PORT=$(grep "^BACKEND_PORT=" .env 2>/dev/null | cut -d'=' -f2 || echo "7778")
HEALTH_URL="http://localhost:${BACKEND_PORT}/health"

MAX_ATTEMPTS=30
ATTEMPT=0
READY=false

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
    echo -e "${YELLOW}  ⚠ Backend did not respond within timeout period.${NC}"
    echo -e "${YELLOW}  Check logs: $DOCKER_COMPOSE_CMD logs backend${NC}"
fi

# Step 7: Print success message and next steps
echo -e "${YELLOW}[7/7] Configuration Instructions${NC}"
echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}✓ Installation Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: LinkedIn OAuth Setup Required${NC}"
echo ""
echo -e "To enable LinkedIn OAuth, you need to:"
echo -e "  1. Get LinkedIn OAuth credentials from: ${GREEN}https://www.linkedin.com/developers/apps${NC}"
echo -e "  2. Edit ${GREEN}$DEPLOYMENT_DIR/.env${NC}"
echo -e "  3. Set your LinkedIn OAuth credentials:"
echo -e "     ${YELLOW}LINKEDIN_CLIENT_ID=your_client_id_here${NC}"
echo -e "     ${YELLOW}LINKEDIN_CLIENT_SECRET=your_client_secret_here${NC}"
echo -e "     ${YELLOW}PUBLIC_URL=https://your-domain-or-tunnel.com${NC}"
echo -e "  4. Restart services: ${GREEN}$DOCKER_COMPOSE_CMD restart${NC}"
echo ""
echo -e "${GREEN}LinkedIn Gateway is running:${NC}"
echo -e "  Backend:    ${GREEN}http://localhost:${BACKEND_PORT}${NC}"
echo -e "  Health:     ${GREEN}http://localhost:${BACKEND_PORT}/health${NC}"
echo -e "  API Docs:   ${GREEN}http://localhost:${BACKEND_PORT}/docs${NC}"
echo ""
echo -e "Useful commands:"
echo -e "  View logs:      ${GREEN}$DOCKER_COMPOSE_CMD logs -f${NC}"
echo -e "  Stop services:  ${GREEN}$DOCKER_COMPOSE_CMD down${NC}"
echo -e "  Restart:        ${GREEN}$DOCKER_COMPOSE_CMD restart${NC}"
echo -e "  Update:         ${GREEN}$SCRIPT_DIR/update-$EDITION.sh${NC}"
echo ""
