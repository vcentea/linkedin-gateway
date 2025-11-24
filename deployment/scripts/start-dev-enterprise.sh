#!/bin/bash
# =============================================================================
# LinkedIn Gateway - Start Development Enterprise with Hot Reload
# =============================================================================
# This script starts the Enterprise edition in development mode with hot reload
# enabled, allowing instant code changes without rebuilding.
#
# Usage: ./start-dev-enterprise.sh
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}LinkedIn Gateway - Development Enterprise with Hot Reload${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""

cd "$DEPLOYMENT_DIR"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}No .env file found. Creating from example...${NC}"
    if [ -f ".env.enterprise.example" ]; then
        cp .env.enterprise.example .env
        echo -e "${GREEN}✓ Created .env file${NC}"
    elif [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env file${NC}"
    else
        echo -e "${RED}Error: No .env example file found${NC}"
        exit 1
    fi
    echo ""
fi

# Ensure LG_BACKEND_EDITION is set to enterprise in .env
if ! grep -q "^LG_BACKEND_EDITION=enterprise" .env 2>/dev/null; then
    echo -e "${YELLOW}Setting LG_BACKEND_EDITION=enterprise in .env...${NC}"
    sed -i 's/^LG_BACKEND_EDITION=.*/LG_BACKEND_EDITION=enterprise/' .env 2>/dev/null || \
    sed -i '' 's/^LG_BACKEND_EDITION=.*/LG_BACKEND_EDITION=enterprise/' .env 2>/dev/null || \
    echo "LG_BACKEND_EDITION=enterprise" >> .env
    echo -e "${GREEN}✓ Edition configured${NC}"
    echo ""
fi

# Check if other instances are running
RUNNING=$(docker compose -f docker-compose.yml ps --format json 2>/dev/null | grep linkedin-gateway | wc -l || echo "0")
if [ "$RUNNING" != "0" ]; then
    echo -e "${YELLOW}⚠ Other LinkedIn Gateway instances are running${NC}"
    echo -e "${YELLOW}They may conflict with this dev instance (same ports)${NC}"
    echo ""
    read -p "Stop other instances and continue? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Stopping other instances...${NC}"
        docker compose -f docker-compose.yml down 2>/dev/null || true
        docker compose -f docker-compose.yml -f docker-compose.saas.yml down 2>/dev/null || true
        docker compose -f docker-compose.yml -f docker-compose.enterprise.yml down 2>/dev/null || true
        docker compose -f docker-compose.dev.yml down 2>/dev/null || true
        echo -e "${GREEN}✓ Stopped${NC}"
        echo ""
    else
        echo -e "${RED}Cancelled${NC}"
        exit 1
    fi
fi

echo -e "${CYAN}Starting Development Enterprise with:${NC}"
echo -e "  🔥 Hot reload: ${GREEN}ENABLED${NC}"
echo -e "  📝 Edition: ${GREEN}Enterprise (LG_BACKEND_EDITION=enterprise)${NC}"
echo -e "  🐛 Debug mode: ${GREEN}ON${NC}"
echo -e "  📂 Source: ${GREEN}../backend (mounted)${NC}"
echo ""

# Create a dev override for Enterprise if it doesn't exist
if [ ! -f "docker-compose.dev-enterprise.yml" ]; then
    echo -e "${YELLOW}Creating docker-compose.dev-enterprise.yml...${NC}"
    cat > docker-compose.dev-enterprise.yml <<'EOF'
# Development overlay for Enterprise edition with hot reload
name: linkedin-gateway-enterprise-dev

services:
  backend:
    container_name: linkedin-gateway-enterprise-dev-api
    volumes:
      - ../backend:/app:ro
    environment:
      RELOAD: "true"
EOF
    echo -e "${GREEN}✓ Dev config created${NC}"
    echo ""
fi

# Start services
echo -e "${YELLOW}Starting services...${NC}"
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml -f docker-compose.dev-enterprise.yml up -d

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to start services${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Services started${NC}"
echo ""

# Wait for backend to be ready
echo -e "${YELLOW}Waiting for backend to be ready...${NC}"
PORT=$(grep "^PORT=" .env 2>/dev/null | cut -d'=' -f2 || echo "7778")
MAX_WAIT=60
WAITED=0

while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s -f "http://localhost:${PORT}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend is ready!${NC}"
        break
    fi
    echo -n "."
    sleep 2
    WAITED=$((WAITED + 2))
done

echo ""
echo ""

# Show status
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml -f docker-compose.dev-enterprise.yml ps

echo ""
echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}✓ Development Enterprise with Hot Reload is running!${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""
echo -e "${CYAN}Access:${NC}"
echo -e "  Backend:    ${GREEN}http://localhost:${PORT}${NC}"
echo -e "  API Docs:   ${GREEN}http://localhost:${PORT}/docs${NC}"
echo -e "  Health:     ${GREEN}http://localhost:${PORT}/health${NC}"
echo ""
echo -e "${CYAN}Features:${NC}"
echo -e "  🔥 ${GREEN}Hot Reload: ENABLED${NC} - Edit files in backend/ and see changes instantly"
echo -e "  📝 ${GREEN}Edition: Enterprise${NC} - Running with LG_BACKEND_EDITION=enterprise"
echo -e "  🐛 ${GREEN}Debug: ON${NC} - Detailed logging for development"
echo ""
echo -e "${CYAN}Useful commands:${NC}"
echo -e "  View logs:  ${YELLOW}docker compose -f docker-compose.yml -f docker-compose.enterprise.yml -f docker-compose.dev-enterprise.yml logs -f${NC}"
echo -e "  Stop:       ${YELLOW}docker compose -f docker-compose.yml -f docker-compose.enterprise.yml -f docker-compose.dev-enterprise.yml down${NC}"
echo -e "  Restart:    ${YELLOW}docker compose -f docker-compose.yml -f docker-compose.enterprise.yml -f docker-compose.dev-enterprise.yml restart backend${NC}"
echo ""
echo -e "${YELLOW}💡 Tip: Edit Python files in backend/ and uvicorn will auto-reload!${NC}"
echo ""



