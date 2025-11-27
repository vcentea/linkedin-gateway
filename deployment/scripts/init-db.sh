#!/bin/bash
# LinkedIn Gateway - Manual Database Initialization Script
# Manually runs the init SQL scripts to create database schema

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$DEPLOYMENT_DIR"

# Load .env for DB credentials
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    exit 1
fi

source .env

echo -e "${YELLOW}======================================${NC}"
echo -e "${YELLOW}Database Manual Initialization${NC}"
echo -e "${YELLOW}======================================${NC}"
echo ""

# Detect edition from container name
if docker ps | grep -q "linkedin-gateway-saas-db"; then
    DB_CONTAINER="linkedin-gateway-saas-db"
    echo "Edition: SaaS"
elif docker ps | grep -q "linkedin-gateway-enterprise-db"; then
    DB_CONTAINER="linkedin-gateway-enterprise-db"
    echo "Edition: Enterprise"
elif docker ps | grep -q "linkedin-gateway-core-db"; then
    DB_CONTAINER="linkedin-gateway-core-db"
    echo "Edition: Core"
else
    echo -e "${RED}Error: No database container found!${NC}"
    echo "Make sure containers are running with docker compose up"
    exit 1
fi

echo "Database Container: $DB_CONTAINER"
echo "Database Name: ${DB_NAME:-LinkedinGateway}"
echo "Database User: ${DB_USER:-linkedin_gateway_user}"
echo ""

# Check if init scripts exist
if [ ! -d "init-scripts" ]; then
    echo -e "${RED}Error: init-scripts directory not found!${NC}"
    exit 1
fi

SQL_FILES=$(ls init-scripts/*.sql 2>/dev/null | sort)

if [ -z "$SQL_FILES" ]; then
    echo -e "${RED}Error: No .sql files found in init-scripts/!${NC}"
    exit 1
fi

echo -e "${YELLOW}Found SQL initialization files:${NC}"
echo "$SQL_FILES" | while read -r file; do
    echo "  - $(basename $file)"
done

echo ""
read -p "Run these SQL scripts to initialize the database? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Database initialization cancelled.${NC}"
    exit 0
fi

echo ""
echo -e "${YELLOW}Running SQL scripts...${NC}"

# Run each SQL file in order
echo "$SQL_FILES" | while read -r SQL_FILE; do
    FILENAME=$(basename "$SQL_FILE")
    echo ""
    echo -e "${YELLOW}Executing: $FILENAME${NC}"
    
    # Copy SQL file into container and execute it
    docker cp "$SQL_FILE" "$DB_CONTAINER:/tmp/$FILENAME"
    
    if docker exec $DB_CONTAINER psql -U ${DB_USER:-linkedin_gateway_user} -d ${DB_NAME:-LinkedinGateway} -f "/tmp/$FILENAME"; then
        echo -e "${GREEN}✓ $FILENAME executed successfully${NC}"
        docker exec $DB_CONTAINER rm "/tmp/$FILENAME"
    else
        echo -e "${RED}✗ $FILENAME failed!${NC}"
        docker exec $DB_CONTAINER rm "/tmp/$FILENAME" 2>/dev/null || true
        exit 1
    fi
done

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}✓ Database initialization complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "Verifying schema..."
echo ""

# Run verification
"$SCRIPT_DIR/verify-db.sh"

