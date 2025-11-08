#!/bin/bash
# Update Backend - Pull latest code, rebuild and restart backend service
# Usage: ./update-backend.sh [core|saas] [--no-pull] [--branch branch-name]

set -e

EDITION="core"
SKIP_PULL=false
BRANCH="main"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        core|saas)
            EDITION=$1
            shift
            ;;
        --no-pull)
            SKIP_PULL=true
            shift
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: ./update-backend.sh [core|saas] [--no-pull] [--branch branch-name]"
            exit 1
            ;;
    esac
done

echo "========================================"
echo "LinkedIn Gateway Backend Update"
echo "Edition: $EDITION"
echo "Branch: $BRANCH"
echo "========================================"
echo ""

# Navigate to project root
cd "$(dirname "$0")/../.."

# Pull latest code from Git
if [ "$SKIP_PULL" = false ]; then
    echo "Pulling latest code from Git ($BRANCH)..."
    
    if ! git fetch origin; then
        echo "WARNING: Git fetch failed! Continuing with local code..."
    else
        # Check for uncommitted changes
        if ! git diff-index --quiet HEAD --; then
            echo ""
            echo "WARNING: You have uncommitted changes!"
            echo "These changes will be included in the build."
            echo ""
            read -p "Continue with build? (y/N): " -n 1 -r
            echo ""
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
        
        # Pull latest changes
        if ! git pull origin "$BRANCH"; then
            echo "ERROR: Git pull failed! Please resolve conflicts manually."
            exit 1
        fi
        echo "Git pull successful!"
    fi
    echo ""
else
    echo "Skipping git pull (using local code)..."
    echo ""
fi

# Navigate to deployment directory
cd deployment

if [ "$EDITION" = "saas" ]; then
    echo "Rebuilding SAAS backend..."
    docker compose -f docker-compose.yml -f docker-compose.saas.yml build --no-cache backend
    
    echo "Restarting SAAS backend..."
    docker compose -f docker-compose.yml -f docker-compose.saas.yml up -d backend
    COMPOSE_CMD="docker compose -f docker-compose.yml -f docker-compose.saas.yml"
else
    echo "Rebuilding CORE backend..."
    docker compose build --no-cache backend
    
    echo "Restarting CORE backend..."
    docker compose up -d backend
    COMPOSE_CMD="docker compose"
fi

# Apply migrations
echo ""
echo "Applying database migrations..."
if $COMPOSE_CMD exec -T backend alembic upgrade head; then
    echo "Database migrations applied successfully."
else
    echo "ERROR: Failed to run database migrations. Check backend logs."
    exit 1
fi

echo ""
echo "========================================"
echo "Backend updated successfully!"
echo "========================================"
echo ""
echo "Checking backend status..."
docker compose ps backend

echo ""
echo "View logs with:"
if [ "$EDITION" = "saas" ]; then
    echo "  docker compose -f docker-compose.yml -f docker-compose.saas.yml logs -f backend"
else
    echo "  docker compose logs -f backend"
fi
