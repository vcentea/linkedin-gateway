#!/bin/bash
# LinkedIn Gateway - Private Repository Setup Script
# 
# This script helps you set up access to the private repository for Enterprise/SaaS editions.
# It will:
# 1. Check if you're using the public or private repository
# 2. Switch to the private repository if needed
# 3. Test authentication
#
# Authentication methods supported:
# - GitHub Personal Access Token (PAT)
# - SSH Key (if already configured)
# - HTTPS with credentials

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Repository URLs
PUBLIC_REPO="https://github.com/vcentea/linkedin-gateway.git"
PRIVATE_REPO_HTTPS="https://github.com/vcentea/linkedin-gateway-saas.git"
PRIVATE_REPO_SSH="git@github.com:vcentea/linkedin-gateway-saas.git"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}LinkedIn Gateway - Private Repo Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${CYAN}ℹ Project location: $PROJECT_ROOT${NC}"
echo ""

# Check if we're in a git repository
cd "$PROJECT_ROOT"
if [ ! -d ".git" ]; then
    echo -e "${RED}✗ Not a git repository!${NC}"
    echo ""
    echo "This directory was not cloned from git."
    echo "Please clone the private repository instead:"
    echo ""
    echo -e "${CYAN}  git clone $PRIVATE_REPO_HTTPS${NC}"
    echo ""
    exit 1
fi

# Check current remote
CURRENT_ORIGIN=$(git remote get-url origin 2>/dev/null || echo "")

echo -e "${YELLOW}[1/4] Checking current repository...${NC}"
echo -e "  Current origin: ${CYAN}$CURRENT_ORIGIN${NC}"
echo ""

# Determine if using public or private repo
if [[ "$CURRENT_ORIGIN" == *"linkedin-gateway.git"* ]] && [[ "$CURRENT_ORIGIN" != *"linkedin-gateway-saas"* ]]; then
    echo -e "${YELLOW}⚠ You are using the PUBLIC repository!${NC}"
    echo ""
    echo "The public repository only contains the Core edition."
    echo "For Enterprise/SaaS editions, you need the PRIVATE repository."
    echo ""
    echo -e "${YELLOW}Do you want to switch to the private repository? (y/n)${NC}"
    read -r SWITCH_REPO
    
    if [[ ! "$SWITCH_REPO" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Setup cancelled.${NC}"
        exit 0
    fi
    
    NEEDS_SWITCH=true
elif [[ "$CURRENT_ORIGIN" == *"linkedin-gateway-saas"* ]]; then
    echo -e "${GREEN}✓ Already using the private repository!${NC}"
    echo ""
    echo "Testing authentication..."
    NEEDS_SWITCH=false
else
    echo -e "${YELLOW}⚠ Unknown repository URL: $CURRENT_ORIGIN${NC}"
    echo ""
    echo "Expected one of:"
    echo "  - $PUBLIC_REPO (public)"
    echo "  - $PRIVATE_REPO_HTTPS (private, HTTPS)"
    echo "  - $PRIVATE_REPO_SSH (private, SSH)"
    echo ""
    exit 1
fi

# Function to test git authentication
test_git_access() {
    local repo_url=$1
    echo -e "${YELLOW}[2/4] Testing access to private repository...${NC}"
    
    # Try to fetch
    if git ls-remote "$repo_url" HEAD >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Authentication successful!${NC}"
        return 0
    else
        echo -e "${RED}✗ Authentication failed!${NC}"
        return 1
    fi
}

# If we need to switch or test access
if [ "$NEEDS_SWITCH" = true ]; then
    echo ""
    echo -e "${YELLOW}[2/4] Choose authentication method:${NC}"
    echo ""
    echo "1) GitHub Personal Access Token (PAT) - Recommended"
    echo "2) SSH Key (if already configured)"
    echo "3) Cancel"
    echo ""
    echo -e "${YELLOW}Enter choice (1-3):${NC} "
    read -r AUTH_METHOD
    
    case $AUTH_METHOD in
        1)
            echo ""
            echo -e "${CYAN}Using Personal Access Token (PAT)${NC}"
            echo ""
            echo "To create a GitHub PAT:"
            echo "1. Go to: https://github.com/settings/tokens"
            echo "2. Click 'Generate new token' → 'Generate new token (classic)'"
            echo "3. Give it a name (e.g., 'LinkedIn Gateway')"
            echo "4. Select scopes: ${YELLOW}repo${NC} (full control)"
            echo "5. Click 'Generate token'"
            echo "6. Copy the token (you won't see it again!)"
            echo ""
            echo -e "${YELLOW}Enter your GitHub username:${NC} "
            read -r GH_USERNAME
            
            echo -e "${YELLOW}Enter your Personal Access Token:${NC} "
            read -rs GH_TOKEN
            echo ""
            
            # Build authenticated URL
            AUTH_URL="https://${GH_USERNAME}:${GH_TOKEN}@github.com/vcentea/linkedin-gateway-saas.git"
            
            # Test access
            if test_git_access "$AUTH_URL"; then
                NEW_REMOTE="$AUTH_URL"
            else
                echo ""
                echo -e "${RED}Failed to authenticate with the provided credentials.${NC}"
                echo "Please check your username and token and try again."
                exit 1
            fi
            ;;
        
        2)
            echo ""
            echo -e "${CYAN}Using SSH Key${NC}"
            echo ""
            echo "Make sure you have:"
            echo "1. Generated an SSH key: ssh-keygen -t ed25519 -C \"your_email@example.com\""
            echo "2. Added it to your GitHub account: https://github.com/settings/keys"
            echo "3. Tested it: ssh -T git@github.com"
            echo ""
            
            # Test SSH access
            if test_git_access "$PRIVATE_REPO_SSH"; then
                NEW_REMOTE="$PRIVATE_REPO_SSH"
            else
                echo ""
                echo -e "${RED}Failed to authenticate via SSH.${NC}"
                echo "Please set up your SSH key first and try again."
                exit 1
            fi
            ;;
        
        3|*)
            echo -e "${YELLOW}Setup cancelled.${NC}"
            exit 0
            ;;
    esac
    
    echo ""
    echo -e "${YELLOW}[3/4] Switching to private repository...${NC}"
    
    # Change the remote URL
    git remote set-url origin "$NEW_REMOTE"
    echo -e "${GREEN}✓ Remote URL updated${NC}"
    
    # Fetch from new remote
    echo "  Fetching from private repository..."
    if git fetch origin main; then
        echo -e "${GREEN}✓ Fetch successful${NC}"
    else
        echo -e "${RED}✗ Fetch failed${NC}"
        echo "Reverting remote URL..."
        git remote set-url origin "$CURRENT_ORIGIN"
        exit 1
    fi
    
    # Pull latest changes
    echo "  Pulling latest changes..."
    if git pull origin main --allow-unrelated-histories --no-edit; then
        echo -e "${GREEN}✓ Successfully pulled from private repository${NC}"
    else
        echo -e "${YELLOW}⚠ Pull had conflicts or issues${NC}"
        echo "You may need to resolve conflicts manually."
    fi
    
else
    # Just test current access
    if test_git_access "$CURRENT_ORIGIN"; then
        echo -e "${GREEN}✓ Access to private repository is working!${NC}"
    else
        echo -e "${RED}✗ Cannot access private repository${NC}"
        echo ""
        echo "Your remote is configured correctly, but authentication is failing."
        echo "Please check your credentials or SSH keys."
        exit 1
    fi
fi

echo ""
echo -e "${YELLOW}[4/4] Verification...${NC}"

# Verify we can see enterprise files
if [ -f "deployment/docker-compose.enterprise.yml" ]; then
    echo -e "${GREEN}✓ Enterprise files present${NC}"
else
    echo -e "${RED}✗ Enterprise files not found${NC}"
    echo "The private repository should contain enterprise edition files."
fi

# Check current branch and commit
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
CURRENT_COMMIT=$(git rev-parse --short HEAD)
echo -e "  Current branch: ${CYAN}$CURRENT_BRANCH${NC}"
echo -e "  Current commit: ${CYAN}$CURRENT_COMMIT${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Private Repository Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "You can now install Enterprise or SaaS editions:"
echo ""
echo -e "${CYAN}  cd deployment/scripts${NC}"
echo -e "${CYAN}  ./install-enterprise.sh${NC}"
echo ""
echo "Or update existing installations:"
echo ""
echo -e "${CYAN}  ./update-enterprise.sh${NC}"
echo ""

