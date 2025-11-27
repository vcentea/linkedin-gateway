#!/bin/bash
# LinkedIn Gateway Enterprise - SSH Key Setup Script
# Generates SSH keys for accessing the private Enterprise repository
# Run this BEFORE running install-enterprise.sh or update-enterprise.sh
#
# Can also be sourced by other scripts to use verify_enterprise_ssh_access()

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SSH_DIR="$HOME/.ssh"
KEY_NAME="linkedin_gateway_enterprise"
KEY_PATH="$SSH_DIR/$KEY_NAME"
SSH_CONFIG="$SSH_DIR/config"

# Private repository details (same repo for SaaS and Enterprise)
ENTERPRISE_REPO_HOST="github.com"
ENTERPRISE_REPO="vcentea/linkedin-gateway-saas"
ENTERPRISE_REPO_SSH="git@github.com:vcentea/linkedin-gateway-saas.git"

# Function to verify SSH access to enterprise repo
# Returns 0 if access is granted, 1 otherwise
# Can be called from other scripts after sourcing this file
verify_enterprise_ssh_access() {
    local SILENT=${1:-false}
    
    # Check if key exists
    if [ ! -f "$KEY_PATH" ]; then
        if [ "$SILENT" != "true" ]; then
            echo -e "${RED}✗ SSH key not found: $KEY_PATH${NC}"
            echo "  Run ./scripts/setup-enterprise-keys.sh first"
        fi
        return 1
    fi
    
    # Test SSH connection
    local SSH_TEST=$(ssh -T -o StrictHostKeyChecking=accept-new -o BatchMode=yes -i "$KEY_PATH" git@$ENTERPRISE_REPO_HOST 2>&1) || true
    
    if echo "$SSH_TEST" | grep -q "successfully authenticated"; then
        if [ "$SILENT" != "true" ]; then
            echo -e "${GREEN}✓ SSH access to Enterprise repository verified${NC}"
        fi
        return 0
    else
        if [ "$SILENT" != "true" ]; then
            echo -e "${RED}✗ SSH access denied to Enterprise repository${NC}"
            echo "  Make sure your SSH key is added to GitHub"
            echo "  Run ./scripts/setup-enterprise-keys.sh to see your public key"
        fi
        return 1
    fi
}

# Function to get the SSH URL for enterprise repo
get_enterprise_repo_url() {
    echo "$ENTERPRISE_REPO_SSH"
}

# If this script is being sourced, don't run the main logic
# Check if script is being sourced or executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Script is being executed directly, run main logic
    RUN_MAIN=true
else
    # Script is being sourced, skip main logic
    RUN_MAIN=false
fi

# Only run main logic if executed directly
if [ "$RUN_MAIN" = true ]; then

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}LinkedIn Gateway Enterprise${NC}"
echo -e "${BLUE}SSH Key Setup${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Ensure .ssh directory exists with correct permissions
echo -e "${YELLOW}[1/5] Checking SSH directory...${NC}"
if [ ! -d "$SSH_DIR" ]; then
    echo "  Creating $SSH_DIR..."
    mkdir -p "$SSH_DIR"
    chmod 700 "$SSH_DIR"
    echo -e "  ${GREEN}✓ Created SSH directory${NC}"
else
    echo -e "  ${GREEN}✓ SSH directory exists${NC}"
fi
echo ""

# Check if key already exists
echo -e "${YELLOW}[2/5] Checking for existing SSH key...${NC}"
if [ -f "$KEY_PATH" ]; then
    echo -e "  ${GREEN}✓ SSH key already exists: $KEY_PATH${NC}"
    KEY_EXISTS=true
else
    echo -e "  ${YELLOW}→ No existing key found${NC}"
    KEY_EXISTS=false
fi
echo ""

# Generate key if it doesn't exist
if [ "$KEY_EXISTS" = false ]; then
    echo -e "${YELLOW}[3/5] Generating new SSH key...${NC}"
    
    # Get email for key comment (optional)
    read -p "  Enter your email (for key comment, press Enter to skip): " USER_EMAIL
    
    if [ -z "$USER_EMAIL" ]; then
        USER_EMAIL="enterprise-user@linkedin-gateway"
    fi
    
    # Generate ED25519 key (more secure and shorter than RSA)
    ssh-keygen -t ed25519 -C "$USER_EMAIL" -f "$KEY_PATH" -N ""
    
    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}✓ SSH key generated successfully${NC}"
        chmod 600 "$KEY_PATH"
        chmod 644 "$KEY_PATH.pub"
    else
        echo -e "  ${RED}✗ Failed to generate SSH key${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}[3/5] Skipping key generation (key exists)${NC}"
fi
echo ""

# Configure SSH to use this key for GitHub
echo -e "${YELLOW}[4/5] Configuring SSH for GitHub...${NC}"

# Check if config entry already exists
if [ -f "$SSH_CONFIG" ] && grep -q "Host github" "$SSH_CONFIG"; then
    echo -e "  ${GREEN}✓ SSH config already configured${NC}"
else
    echo "  Adding SSH config entry..."
    
    # Create config file if it doesn't exist
    touch "$SSH_CONFIG"
    chmod 600 "$SSH_CONFIG"
    
    # Add configuration for enterprise repository
    cat >> "$SSH_CONFIG" << EOF

# LinkedIn Gateway Enterprise Repository
Host github
    HostName $ENTERPRISE_REPO_HOST
    User git
    IdentityFile $KEY_PATH
    IdentitiesOnly yes

EOF
    
    echo -e "  ${GREEN}✓ SSH config updated${NC}"
fi
echo ""

# Display the public key
echo -e "${YELLOW}[5/5] Your SSH Public Key${NC}"
echo ""
echo -e "${CYAN}======================================${NC}"
echo -e "${CYAN}COPY THE KEY BELOW AND ADD IT TO GITHUB${NC}"
echo -e "${CYAN}======================================${NC}"
echo ""
cat "$KEY_PATH.pub"
echo ""
echo -e "${CYAN}======================================${NC}"
echo ""

# Test connection (optional)
echo -e "${YELLOW}Testing SSH connection to GitHub...${NC}"
echo ""

# Use ssh -T to test (will return exit code 1 even on success because GitHub doesn't allow shell access)
SSH_TEST=$(ssh -T -o StrictHostKeyChecking=accept-new -i "$KEY_PATH" git@$ENTERPRISE_REPO_HOST 2>&1) || true

if echo "$SSH_TEST" | grep -q "successfully authenticated"; then
    echo -e "${GREEN}✓ SSH authentication successful!${NC}"
    echo "  $SSH_TEST"
    AUTH_SUCCESS=true
elif echo "$SSH_TEST" | grep -q "Permission denied"; then
    echo -e "${YELLOW}⚠ SSH key not yet authorized on GitHub${NC}"
    AUTH_SUCCESS=false
else
    echo -e "${YELLOW}⚠ Could not verify authentication${NC}"
    echo "  Response: $SSH_TEST"
    AUTH_SUCCESS=false
fi

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Next Steps${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

if [ "$AUTH_SUCCESS" = true ]; then
    echo -e "${GREEN}Your SSH key is already authorized!${NC}"
    echo ""
    echo "You can now run the Enterprise installation:"
    echo "  cd deployment"
    echo "  ./scripts/install-enterprise.sh"
    echo ""
    echo "Or update an existing installation:"
    echo "  cd deployment"
    echo "  ./scripts/update-enterprise.sh"
else
    echo -e "${YELLOW}1. Add the SSH key to GitHub:${NC}"
    echo "   a. Go to: https://github.com/settings/keys"
    echo "   b. Click 'New SSH key'"
    echo "   c. Title: 'LinkedIn Gateway Enterprise - $(hostname)'"
    echo "   d. Key type: 'Authentication Key'"
    echo "   e. Paste the public key shown above"
    echo "   f. Click 'Add SSH key'"
    echo ""
    echo -e "${YELLOW}2. Request repository access:${NC}"
    echo "   Contact the repository owner to grant your GitHub account"
    echo "   access to: $ENTERPRISE_REPO"
    echo ""
    echo -e "${YELLOW}3. Verify access:${NC}"
    echo "   Run this script again to test authentication"
    echo "   Or run: ssh -T git@github.com"
    echo ""
    echo -e "${YELLOW}4. After access is granted, run:${NC}"
    echo "   cd deployment"
    echo "   ./scripts/install-enterprise.sh"
fi

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Key Information${NC}"
echo -e "${BLUE}======================================${NC}"
echo "  Private Key: $KEY_PATH"
echo "  Public Key:  $KEY_PATH.pub"
echo "  SSH Config:  $SSH_CONFIG"
echo ""

fi  # End of RUN_MAIN check

