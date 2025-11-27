#!/bin/bash
# LinkedIn Gateway - Database Verification Script
# Checks if database tables exist and shows schema status

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
echo -e "${YELLOW}Database Schema Verification${NC}"
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

# Check if database exists
echo -e "${YELLOW}Checking database existence...${NC}"
DB_EXISTS=$(docker exec $DB_CONTAINER psql -U ${DB_USER:-linkedin_gateway_user} -lqt | cut -d \| -f 1 | grep -w ${DB_NAME:-LinkedinGateway} | wc -l)

if [ "$DB_EXISTS" -eq "0" ]; then
    echo -e "${RED}✗ Database '${DB_NAME:-LinkedinGateway}' does not exist!${NC}"
    exit 1
else
    echo -e "${GREEN}✓ Database exists${NC}"
fi

echo ""
echo -e "${YELLOW}Checking tables...${NC}"

# List all tables
TABLES=$(docker exec $DB_CONTAINER psql -U ${DB_USER:-linkedin_gateway_user} -d ${DB_NAME:-LinkedinGateway} -t -c "
    SELECT tablename 
    FROM pg_tables 
    WHERE schemaname = 'public' 
    ORDER BY tablename;
")

if [ -z "$(echo $TABLES | tr -d '[:space:]')" ]; then
    echo -e "${RED}✗ No tables found in database!${NC}"
    echo ""
    echo "The database exists but is empty. Tables were not created."
    echo ""
    echo "To fix this, run:"
    echo "  cd $DEPLOYMENT_DIR"
    echo "  ./scripts/init-db.sh"
    exit 1
fi

echo -e "${GREEN}Found tables:${NC}"
echo "$TABLES" | while read -r table; do
    if [ ! -z "$table" ]; then
        # Get row count for each table
        COUNT=$(docker exec $DB_CONTAINER psql -U ${DB_USER:-linkedin_gateway_user} -d ${DB_NAME:-LinkedinGateway} -t -c "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "0")
        echo -e "  ${GREEN}✓${NC} $table (rows: $(echo $COUNT | tr -d '[:space:]'))"
    fi
done

echo ""
echo -e "${YELLOW}Checking required tables...${NC}"

REQUIRED_TABLES=("users" "user_sessions" "api_keys" "profiles" "posts" "billing_tiers")

ALL_GOOD=true
for table in "${REQUIRED_TABLES[@]}"; do
    if echo "$TABLES" | grep -q "^ $table$"; then
        echo -e "  ${GREEN}✓${NC} $table"
    else
        echo -e "  ${RED}✗${NC} $table - MISSING!"
        ALL_GOOD=false
    fi
done

echo ""

if [ "$ALL_GOOD" = true ]; then
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}✓ Database schema is complete!${NC}"
    echo -e "${GREEN}======================================${NC}"
else
    echo -e "${RED}======================================${NC}"
    echo -e "${RED}✗ Database schema is incomplete!${NC}"
    echo -e "${RED}======================================${NC}"
    echo ""
    echo "To recreate the schema, run:"
    echo "  cd $DEPLOYMENT_DIR"
    echo "  ./scripts/init-db.sh"
    exit 1
fi

echo ""

