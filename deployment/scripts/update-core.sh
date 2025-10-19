#!/bin/bash
# LinkedIn Gateway - Open Core Update Script
# This script updates an existing LinkedIn Gateway installation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory and deployment root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$DEPLOYMENT_DIR/.." && pwd)"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}LinkedIn Gateway - Update${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Change to deployment directory
cd "$DEPLOYMENT_DIR"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

# Check if docker compose is available
if ! docker compose version > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker Compose is not available. Please install Docker Compose and try again.${NC}"
    exit 1
fi

# Check if installation exists
if ! docker ps -a --filter "name=linkedin_gateway" --format "{{.Names}}" | grep -q "linkedin_gateway"; then
    echo -e "${YELLOW}No existing installation found.${NC}"
    echo -e "Please run ${GREEN}install-core.sh${NC} first for a fresh installation."
    exit 1
fi

echo -e "${YELLOW}[1/3] Updating LinkedIn Gateway...${NC}"
echo ""

# Pull latest images and rebuild
echo -e "  → Pulling latest changes and rebuilding..."
docker compose -f docker-compose.yml up -d --build

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Update failed.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ Update completed${NC}"

# Wait for services and poll health endpoint
echo ""
echo -e "${YELLOW}[2/3] Waiting for services to be ready...${NC}"

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
    echo -e "${YELLOW}  Check logs: docker compose -f $DEPLOYMENT_DIR/docker-compose.yml logs backend${NC}"
fi

# Print success message
echo ""
echo -e "${YELLOW}[3/3] Update summary${NC}"
docker compose -f docker-compose.yml ps

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}✓ Update Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "LinkedIn Gateway has been updated and is running:"
echo -e "  Backend:    ${GREEN}http://localhost:${BACKEND_PORT}${NC}"
echo -e "  Health:     ${GREEN}http://localhost:${BACKEND_PORT}/health${NC}"
echo -e "  API Docs:   ${GREEN}http://localhost:${BACKEND_PORT}/docs${NC}"
echo ""
echo -e "Useful commands:"
echo -e "  View logs:      docker compose -f $DEPLOYMENT_DIR/docker-compose.yml logs -f"
echo -e "  Restart:        docker compose -f $DEPLOYMENT_DIR/docker-compose.yml restart"
echo -e "  Uninstall:      cd $SCRIPT_DIR && ./uninstall-core.sh"
echo ""

