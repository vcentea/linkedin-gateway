#!/bin/bash
# LinkedIn Gateway - Database Connection Debugger
# Helping diagnose why installation or verification fails

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$DEPLOYMENT_DIR"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Database Connection Debugger${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# 1. Load .env
echo -e "${YELLOW}[1/5] Loading configuration...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    exit 1
fi

# Read .env manually to avoid sourcing issues, but handle quoted values
# Use export so they are available
export $(grep -v '^#' .env | xargs) 2>/dev/null

# Fallback defaults
DB_USER=${DB_USER:-linkedin_gateway_user}
DB_NAME=${DB_NAME:-LinkedinGateway}
# Mask password for logging
DB_PASS_MASKED="${DB_PASSWORD:0:3}********"

echo "  Env DB_USER: $DB_USER"
echo "  Env DB_NAME: $DB_NAME"
echo "  Env DB_PASSWORD: $DB_PASS_MASKED"
echo ""

# 2. Detect Container
echo -e "${YELLOW}[2/5] Detecting database container...${NC}"
if docker ps | grep -q "linkedin-gateway-saas-db"; then
    DB_CONTAINER="linkedin-gateway-saas-db"
    echo "  Found: SaaS ($DB_CONTAINER)"
elif docker ps | grep -q "linkedin-gateway-enterprise-db"; then
    DB_CONTAINER="linkedin-gateway-enterprise-db"
    echo "  Found: Enterprise ($DB_CONTAINER)"
elif docker ps | grep -q "linkedin-gateway-core-db"; then
    DB_CONTAINER="linkedin-gateway-core-db"
    echo "  Found: Core ($DB_CONTAINER)"
else
    echo -e "${RED}Error: No database container running!${NC}"
    echo "  Check: docker ps"
    exit 1
fi
echo ""

# 3. Check Container Logs (Last 20 lines) to see startup errors
echo -e "${YELLOW}[3/5] Checking recent container logs (for auth errors)...${NC}"
docker logs --tail 20 $DB_CONTAINER
echo ""

# 4. Attempt Connection
echo -e "${YELLOW}[4/5] Testing connection via psql...${NC}"

# We use PGPASSWORD env var inside the exec command
# Capture stderr to check for specific errors
OUTPUT=$(docker exec -e PGPASSWORD="$DB_PASSWORD" $DB_CONTAINER psql -U "$DB_USER" -d "$DB_NAME" -c '\conninfo' 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Connection Successful!${NC}"
    echo "$OUTPUT"
else
    echo -e "${RED}✗ Connection Failed!${NC}"
    echo -e "${RED}Output:${NC}"
    echo "$OUTPUT"
    
    echo ""
    echo -e "${YELLOW}Diagnosis:${NC}"
    if echo "$OUTPUT" | grep -q "password authentication failed"; then
        echo -e "${RED}PASSWORD MISMATCH DETECTED${NC}"
        echo "The password in your .env file does NOT match the database container."
        echo ""
        echo "This often happens when:"
        echo "1. The database volume persisted from a previous install with an old password"
        echo "2. The .env file was regenerated with a new random password"
        echo ""
        echo "${BLUE}Solution:${NC}"
        echo "Option A (Reset DB): Run ./scripts/clean-[edition].sh to wipe the database volume"
        echo "Option B (Fix .env): Find the old password (if known) and put it in .env"
        echo "Option C (Force Password): Use ./scripts/fix-db-password.sh to force update the DB user password"
    elif echo "$OUTPUT" | grep -q "role .* does not exist"; then
        echo -e "${RED}USER DOES NOT EXIST${NC}"
        echo "The database user '$DB_USER' does not exist inside the database."
    elif echo "$OUTPUT" | grep -q "database .* does not exist"; then
        echo -e "${RED}DATABASE DOES NOT EXIST${NC}"
        echo "The database '$DB_NAME' has not been created."
    fi
fi
echo ""

# 5. List Tables (if connected)
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${YELLOW}[5/5] Listing tables...${NC}"
    TABLE_COUNT=$(docker exec -e PGPASSWORD="$DB_PASSWORD" $DB_CONTAINER psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT count(*) FROM pg_tables WHERE schemaname = 'public';" | tr -d '[:space:]')
    echo -e "  Table count: ${GREEN}$TABLE_COUNT${NC}"
    
    if [ "$TABLE_COUNT" -eq "0" ]; then
        echo -e "${YELLOW}  Database is empty (no tables). Init scripts may have failed.${NC}"
    fi
fi

echo ""

