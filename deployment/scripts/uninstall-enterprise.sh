#!/bin/bash
# LinkedIn Gateway - Enterprise Edition Teardown Script
# This script stops and optionally removes the Enterprise deployment

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
echo -e "${BLUE}LinkedIn Gateway Enterprise - Teardown${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Change to deployment directory
cd "$DEPLOYMENT_DIR"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running.${NC}"
    exit 1
fi

# Check if docker compose is available
if ! docker compose version > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker Compose is not available.${NC}"
    exit 1
fi

# Step 1: Stop and remove containers
echo -e "${YELLOW}[1/3] Stopping containers...${NC}"
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml down

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to stop containers.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ Containers stopped and removed${NC}"

# Step 2: Ask about volumes
echo ""
echo -e "${YELLOW}[2/3] Volume management${NC}"
echo ""
echo -e "Do you want to remove data volumes? ${RED}(This will delete all data!)${NC}"
echo -e "  ${BLUE}1)${NC} Keep volumes (data preserved for next deployment)"
echo -e "  ${RED}2)${NC} Remove volumes (all data will be lost)"
echo -e "  ${YELLOW}3)${NC} Skip (exit now)"
echo ""
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        echo -e "  ${GREEN}✓ Volumes preserved${NC}"
        ;;
    2)
        echo ""
        echo -e "${RED}⚠ WARNING: This will permanently delete:${NC}"
        echo -e "  - Database data (PostgreSQL)"
        echo -e "  - Application logs"
        echo ""
        read -p "Are you absolutely sure? Type 'YES' to confirm: " confirm
        
        if [ "$confirm" = "YES" ]; then
            echo ""
            echo -e "${YELLOW}Removing volumes...${NC}"
            docker compose -f docker-compose.yml -f docker-compose.enterprise.yml down -v
            
            if [ $? -eq 0 ]; then
                echo -e "  ${GREEN}✓ Volumes removed${NC}"
            else
                echo -e "${RED}Error: Failed to remove volumes.${NC}"
                exit 1
            fi
        else
            echo -e "  ${YELLOW}Volume removal cancelled. Volumes preserved.${NC}"
        fi
        ;;
    3)
        echo -e "  ${YELLOW}Teardown cancelled.${NC}"
        exit 0
        ;;
    *)
        echo -e "  ${YELLOW}Invalid choice. Volumes preserved by default.${NC}"
        ;;
esac

# Step 3: Summary
echo ""
echo -e "${YELLOW}[3/3] Cleanup summary${NC}"

# Check what's still running
RUNNING_CONTAINERS=$(docker ps --filter "name=linkedin-gateway-enterprise" --format "{{.Names}}" | wc -l)

if [ "$RUNNING_CONTAINERS" -eq 0 ]; then
    echo -e "  ${GREEN}✓ No LinkedIn Gateway Enterprise containers running${NC}"
else
    echo -e "  ${YELLOW}⚠ Some containers may still be running${NC}"
    docker ps --filter "name=linkedin-gateway-enterprise"
fi

# Check volumes
VOLUMES=$(docker volume ls --filter "name=linkedin-gateway-enterprise" --format "{{.Name}}" | wc -l)
if [ "$VOLUMES" -gt 0 ]; then
    echo -e "  ${GREEN}✓ Data volumes still exist (data preserved)${NC}"
    docker volume ls --filter "name=linkedin-gateway-enterprise"
else
    echo -e "  ${BLUE}ℹ No volumes found (data was removed or never created)${NC}"
fi

# Final message
echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}✓ Teardown Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "Useful commands:"
echo -e "  Redeploy:           cd $DEPLOYMENT_DIR/scripts && ./install-enterprise.sh"
echo -e "  List volumes:       docker volume ls"
echo -e "  Remove old images:  docker image prune"
echo -e "  System cleanup:     docker system prune"
echo ""



