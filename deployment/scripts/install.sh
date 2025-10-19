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
if [[ "$EDITION" != "core" && "$EDITION" != "saas" ]]; then
    echo -e "${RED}Error: Invalid edition '$EDITION'. Must be 'core' or 'saas'.${NC}"
    echo "Usage: $0 [core|saas]"
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
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        echo -e "  ${YELLOW}⚠ Uncommitted changes detected${NC}"
        echo -e "  ${YELLOW}→ Stashing changes...${NC}"
        git stash push -m "Auto-stash before install $(date +%Y-%m-%d_%H-%M-%S)"
        echo -e "  ${GREEN}✓ Changes stashed (recover with: git stash pop)${NC}"
    fi
    
    # Pull latest changes
    echo -e "  ${GREEN}→ Pulling latest code...${NC}"
    if git pull origin main; then
        echo -e "  ${GREEN}✓ Code updated${NC}"
    else
        echo -e "  ${YELLOW}⚠ Git pull failed, continuing with current version${NC}"
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
# Don't overwrite existing passwords (even if weak) to preserve data on reinstalls
DB_PASSWORD=$(grep "^DB_PASSWORD=" .env 2>/dev/null | cut -d'=' -f2- || echo "")
if [ -z "$DB_PASSWORD" ] || echo "$DB_PASSWORD" | grep -Eq "CHANGE|change|your_strong_password_here|postgres$"; then
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
    echo -e "  ${GREEN}✓ DB_PASSWORD already set${NC}"
fi

# Check if SECRET_KEY is set and not a placeholder
if ! grep -q "^SECRET_KEY=.\+" .env || grep -q "^SECRET_KEY=CHANGE" .env || grep -q "^SECRET_KEY=+$" .env; then
    SECRET_KEY=$(generate_secret)
    if grep -q "^SECRET_KEY=" .env; then
        # Replace existing SECRET_KEY (even if it's a placeholder)
        sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env && rm .env.bak
    else
        # Append if not exists
        echo "SECRET_KEY=$SECRET_KEY" >> .env
    fi
    echo -e "  ${GREEN}✓ Generated SECRET_KEY${NC}"
else
    echo -e "  ${GREEN}✓ SECRET_KEY already set${NC}"
fi

# Check if JWT_SECRET_KEY is set and not a placeholder
if ! grep -q "^JWT_SECRET_KEY=.\+" .env || grep -q "^JWT_SECRET_KEY=CHANGE" .env || grep -q "^JWT_SECRET_KEY=+$" .env; then
    JWT_SECRET_KEY=$(generate_secret)
    if grep -q "^JWT_SECRET_KEY=" .env; then
        # Replace existing JWT_SECRET_KEY (even if it's a placeholder)
        sed -i.bak "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET_KEY|" .env && rm .env.bak
    else
        echo "JWT_SECRET_KEY=$JWT_SECRET_KEY" >> .env
    fi
    echo -e "  ${GREEN}✓ Generated JWT_SECRET_KEY${NC}"
else
    echo -e "  ${GREEN}✓ JWT_SECRET_KEY already set${NC}"
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
    if docker exec $DB_CONTAINER pg_isready -U ${DB_USER:-linkedin_gateway_user} > /dev/null 2>&1; then
        echo ""
        echo -e "  ${GREEN}✓ Database is ready${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# Check if tables were created
echo ""
echo -e "  ${GREEN}→ Checking if database schema was created...${NC}"
TABLES_COUNT=$(docker exec $DB_CONTAINER psql -U ${DB_USER:-linkedin_gateway_user} -d ${DB_NAME:-LinkedinGateway} -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';" 2>/dev/null | tr -d '[:space:]')

if [ -z "$TABLES_COUNT" ] || [ "$TABLES_COUNT" -eq "0" ]; then
    echo -e "  ${RED}✗ Database tables not found!${NC}"
    echo -e "  ${YELLOW}→ Init scripts didn't run automatically. Running manually...${NC}"
    
    # Manually run init scripts
    for SQL_FILE in ../init-scripts/*.sql; do
        if [ -f "$SQL_FILE" ]; then
            FILENAME=$(basename "$SQL_FILE")
            echo -e "    → Executing: $FILENAME"
            docker cp "$SQL_FILE" "$DB_CONTAINER:/tmp/$FILENAME"
            docker exec $DB_CONTAINER psql -U ${DB_USER:-linkedin_gateway_user} -d ${DB_NAME:-LinkedinGateway} -f "/tmp/$FILENAME" > /dev/null 2>&1
            docker exec $DB_CONTAINER rm "/tmp/$FILENAME"
        fi
    done
    
    # Verify tables were created
    TABLES_COUNT=$(docker exec $DB_CONTAINER psql -U ${DB_USER:-linkedin_gateway_user} -d ${DB_NAME:-LinkedinGateway} -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';" 2>/dev/null | tr -d '[:space:]')
    
    if [ "$TABLES_COUNT" -gt "0" ]; then
        echo -e "  ${GREEN}✓ Database schema created successfully ($TABLES_COUNT tables)${NC}"
    else
        echo -e "  ${RED}✗ Failed to create database schema!${NC}"
        echo -e "  ${YELLOW}You can try manually with: ./scripts/init-db.sh${NC}"
    fi
else
    echo -e "  ${GREEN}✓ Database schema exists ($TABLES_COUNT tables)${NC}"
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

