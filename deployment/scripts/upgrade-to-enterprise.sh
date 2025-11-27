#!/bin/bash
# LinkedIn Gateway - Upgrade from Core to Enterprise
# This script switches your installation from the public Core repository
# to the private Enterprise repository and updates all files.
#
# Prerequisites:
# 1. Run setup-enterprise-keys.sh first
# 2. Add the SSH key to your GitHub account
# 3. Have repository access granted
#
# Usage: ./upgrade-to-enterprise.sh

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Repository URLs
# Note: Core uses public HTTPS, Enterprise/SaaS use private SSH (same repo)
CORE_REPO_HTTPS="https://github.com/vcentea/linkedin-gateway-saas.git"
PRIVATE_REPO_SSH="git@github.com:vcentea/linkedin-gateway-saas.git"

# SSH Key path - check both current user and sudo user's home
SSH_KEY="$HOME/.ssh/linkedin_gateway_enterprise"

# If running with sudo, try to find the key in the original user's home
if [ -n "$SUDO_USER" ] && [ ! -f "$SSH_KEY" ]; then
    ORIGINAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    if [ -f "$ORIGINAL_HOME/.ssh/linkedin_gateway_enterprise" ]; then
        SSH_KEY="$ORIGINAL_HOME/.ssh/linkedin_gateway_enterprise"
        echo -e "${YELLOW}Note: Running with sudo, using SSH key from $SUDO_USER's home${NC}"
    fi
fi

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$DEPLOYMENT_DIR/.." && pwd)"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}LinkedIn Gateway${NC}"
echo -e "${BLUE}Upgrade: Core → Enterprise${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Warn about sudo usage
if [ -n "$SUDO_USER" ]; then
    echo -e "${YELLOW}⚠ Running with sudo (as root)${NC}"
    echo -e "${YELLOW}  Original user: $SUDO_USER${NC}"
    echo -e "${YELLOW}  SSH keys will be searched in $SUDO_USER's home directory${NC}"
    echo ""
fi

# Step 1: Verify SSH key exists
echo -e "${YELLOW}[1/8] Verifying SSH key...${NC}"
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}✗ SSH key not found: $SSH_KEY${NC}"
    echo ""
    echo "Please run first:"
    echo "  ./scripts/setup-enterprise-keys.sh"
    exit 1
fi
echo -e "  ${GREEN}✓ SSH key found${NC}"
echo ""

# Step 2: Test SSH access to Enterprise repository
echo -e "${YELLOW}[2/8] Testing SSH access to Enterprise repository...${NC}"
SSH_TEST=$(ssh -T -o StrictHostKeyChecking=accept-new -o BatchMode=yes -i "$SSH_KEY" git@github.com 2>&1) || true

if echo "$SSH_TEST" | grep -q "successfully authenticated"; then
    echo -e "  ${GREEN}✓ SSH authentication successful${NC}"
else
    echo -e "${RED}✗ SSH authentication failed${NC}"
    echo ""
    echo "Response: $SSH_TEST"
    echo ""
    echo "Please ensure:"
    echo "  1. Your SSH key is added to GitHub (https://github.com/settings/keys)"
    echo "  2. You have been granted access to the Enterprise repository"
    echo ""
    echo "To see your public key, run:"
    echo "  cat $SSH_KEY.pub"
    exit 1
fi
echo ""

# Step 3: Test access to Enterprise repository specifically
echo -e "${YELLOW}[3/8] Verifying Enterprise repository access...${NC}"

# Use GIT_SSH_COMMAND to specify the key with all necessary options
export GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=10"

echo -e "  ${CYAN}Using SSH key: $SSH_KEY${NC}"
echo -e "  ${CYAN}Testing repository access (timeout: 10s)...${NC}"

# Try ls-remote with timeout to prevent hanging
LSREMOTE_OUTPUT=$(timeout 15 git ls-remote "$PRIVATE_REPO_SSH" HEAD 2>&1) || true
LSREMOTE_EXIT=$?

if [ $LSREMOTE_EXIT -eq 0 ] && [ -n "$LSREMOTE_OUTPUT" ]; then
    echo -e "  ${GREEN}✓ Enterprise repository accessible${NC}"
elif [ $LSREMOTE_EXIT -eq 124 ]; then
    echo -e "  ${YELLOW}⚠ Connection timed out${NC}"
    echo ""
    echo -e "  ${CYAN}Since you confirmed clone works manually, continuing anyway...${NC}"
else
    echo -e "  ${YELLOW}⚠ git ls-remote returned: exit=$LSREMOTE_EXIT${NC}"
    if [ -n "$LSREMOTE_OUTPUT" ]; then
        echo -e "  ${CYAN}Output: $LSREMOTE_OUTPUT${NC}"
    fi
    echo ""
    echo -e "  ${CYAN}Since you confirmed clone works manually, continuing anyway...${NC}"
fi
echo ""

# Step 4: Backup .env files
echo -e "${YELLOW}[4/8] Backing up configuration files...${NC}"
cd "$PROJECT_ROOT"

BACKUP_DIR="$PROJECT_ROOT/.upgrade-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -f "deployment/.env" ]; then
    cp "deployment/.env" "$BACKUP_DIR/deployment.env"
    echo -e "  ${GREEN}✓ Backed up deployment/.env${NC}"
fi

if [ -f "backend/.env" ]; then
    cp "backend/.env" "$BACKUP_DIR/backend.env"
    echo -e "  ${GREEN}✓ Backed up backend/.env${NC}"
fi

echo -e "  ${CYAN}Backup location: $BACKUP_DIR${NC}"
echo ""

# Step 5: Stop running containers
echo -e "${YELLOW}[5/8] Stopping running containers...${NC}"
cd "$DEPLOYMENT_DIR"

# Try to stop any running linkedin-gateway containers
if docker compose -f docker-compose.yml down 2>/dev/null; then
    echo -e "  ${GREEN}✓ Containers stopped${NC}"
else
    echo -e "  ${YELLOW}⚠ No containers to stop (or already stopped)${NC}"
fi
echo ""

# Step 6: Change git remote to Enterprise
echo -e "${YELLOW}[6/8] Switching repository to Enterprise...${NC}"
cd "$PROJECT_ROOT"

# Get current remote
CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "none")
echo -e "  Current remote: ${CYAN}$CURRENT_REMOTE${NC}"

# Configure git to use our SSH key for this repo
git config core.sshCommand "ssh -i $SSH_KEY -o IdentitiesOnly=yes"

# Change remote to Enterprise
git remote set-url origin "$PRIVATE_REPO_SSH"
echo -e "  ${GREEN}✓ Remote changed to: $PRIVATE_REPO_SSH${NC}"

# Verify the change
NEW_REMOTE=$(git remote get-url origin)
echo -e "  New remote: ${GREEN}$NEW_REMOTE${NC}"
echo ""

# Step 7: Fetch and merge Enterprise code
echo -e "${YELLOW}[7/8] Pulling Enterprise code...${NC}"

# Stash any local changes
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo -e "  ${YELLOW}→ Stashing local changes...${NC}"
    git stash push -m "upgrade-to-enterprise-$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
fi

# Fetch from new remote
echo -e "  ${GREEN}→ Fetching from Enterprise repository...${NC}"
git fetch origin

# Get the default branch (usually main)
DEFAULT_BRANCH=$(git remote show origin | grep 'HEAD branch' | cut -d' ' -f5)
if [ -z "$DEFAULT_BRANCH" ]; then
    DEFAULT_BRANCH="main"
fi
echo -e "  ${GREEN}→ Default branch: $DEFAULT_BRANCH${NC}"

# Try to merge/pull
echo -e "  ${GREEN}→ Merging Enterprise code...${NC}"
if git pull origin "$DEFAULT_BRANCH" --allow-unrelated-histories --no-edit 2>&1; then
    echo -e "  ${GREEN}✓ Enterprise code merged successfully${NC}"
else
    # If merge fails, try reset (will overwrite local changes)
    echo -e "  ${YELLOW}⚠ Merge had conflicts, attempting force update...${NC}"
    git fetch origin "$DEFAULT_BRANCH"
    git reset --hard "origin/$DEFAULT_BRANCH"
    echo -e "  ${GREEN}✓ Reset to Enterprise code${NC}"
fi
echo ""

# Step 8: Restore .env files
echo -e "${YELLOW}[8/8] Restoring configuration files...${NC}"

if [ -f "$BACKUP_DIR/deployment.env" ]; then
    cp "$BACKUP_DIR/deployment.env" "$PROJECT_ROOT/deployment/.env"
    echo -e "  ${GREEN}✓ Restored deployment/.env${NC}"
fi

if [ -f "$BACKUP_DIR/backend.env" ]; then
    cp "$BACKUP_DIR/backend.env" "$PROJECT_ROOT/backend/.env"
    echo -e "  ${GREEN}✓ Restored backend/.env${NC}"
fi
echo ""

# Done!
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}✓ Upgrade Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "Your installation has been upgraded to Enterprise."
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo ""
echo "1. Review any new environment variables in the .env files"
echo "   (compare with .env.example if available)"
echo ""
echo "2. Start the Enterprise containers:"
echo -e "   ${YELLOW}cd $DEPLOYMENT_DIR${NC}"
echo -e "   ${YELLOW}./scripts/install-enterprise.sh${NC}"
echo ""
echo "   Or if you prefer to update existing containers:"
echo -e "   ${YELLOW}./scripts/update-enterprise.sh${NC}"
echo ""
echo -e "${CYAN}Backup location:${NC} $BACKUP_DIR"
echo ""
echo -e "${CYAN}To revert to Core (if needed):${NC}"
echo "   git remote set-url origin $CORE_REPO_HTTPS"
echo "   git fetch origin && git reset --hard origin/main"
echo ""

