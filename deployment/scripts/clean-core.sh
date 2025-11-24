#!/bin/bash
# LinkedIn Gateway - Complete Core Cleanup Script
# WARNING: This will delete ALL data including database!

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$DEPLOYMENT_DIR"

echo -e "${RED}======================================${NC}"
echo -e "${RED}LinkedIn Gateway Core - COMPLETE CLEANUP${NC}"
echo -e "${RED}======================================${NC}"
echo ""
echo -e "${YELLOW}WARNING: This will:${NC}"
echo "  • Stop all Core containers"
echo "  • Remove all Core containers"
echo "  • Delete all Core volumes (DATABASE WILL BE LOST!)"
echo "  • Remove Core network"
echo "  • Clean up dangling images"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${GREEN}Cleanup cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${YELLOW}Stopping and removing containers...${NC}"
docker compose -f docker-compose.yml down -v --remove-orphans

echo ""
echo -e "${YELLOW}Removing specific Core volumes...${NC}"
docker volume rm linkedin-gateway-core-postgres-data 2>/dev/null || echo "  (postgres-data volume not found)"
docker volume rm linkedin-gateway-core-backend-logs 2>/dev/null || echo "  (backend-logs volume not found)"

echo ""
echo -e "${YELLOW}Removing Core network...${NC}"
docker network rm linkedin-gateway-core-network 2>/dev/null || echo "  (network not found)"

echo ""
echo -e "${YELLOW}Cleaning up dangling images...${NC}"
docker image prune -f

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}✓ Cleanup Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "To reinstall, run:"
echo "  ./install-core.sh"
echo ""

