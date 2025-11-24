# LinkedIn Gateway - Windows Installation Guide

LinkedIn Gateway includes **native Windows BAT scripts** - no WSL or Git Bash required!

## Prerequisites

**Required:**
- **Docker Desktop for Windows** - https://docs.docker.com/desktop/install/windows-install/

**Optional:**
- Git for Windows (for git pull functionality)

## Quick Start

### Fresh Installation

```cmd
cd deployment\scripts
install-core.bat
```

### Update

```cmd
cd deployment\scripts
update-core.bat
```

## Native Windows Implementation

The BAT scripts are **fully native Windows** - they work out of the box!

**Uses only Windows commands:**
- `docker` - Docker commands
- `powershell` - Text manipulation
- `findstr` - Reading .env files
- `timeout` - Waiting
- `curl` - Health checks

**All existing functionality preserved:**
- ✅ Docker initialization
- ✅ Password generation
- ✅ Environment variable handling
- ✅ Database superuser setup
- ✅ Schema creation
- ✅ Alembic migrations

## Available Scripts

**Installation:**
- `install.bat [core|saas|enterprise]` - Main installer
- `install-core.bat` - Core edition
- `install-saas.bat` - SaaS edition
- `install-enterprise.bat` - Enterprise edition

**Updates:**
- `update.bat [core|saas|enterprise]` - Main updater
- `update-core.bat` - Update Core
- `update-saas.bat` - Update SaaS
- `update-enterprise.bat` - Update Enterprise

## Troubleshooting

### Docker not running

Start Docker Desktop from Start Menu, wait for green icon in system tray.

### Port already in use

During installation, enter a different port or edit `.env`:
```
PORT=8080
BACKEND_PORT=8080
```

### PowerShell not found

PowerShell is included in Windows 10/11. Try running as Administrator.

## Manual Installation

If needed:

1. Copy `.env.example` to `.env` and edit
2. Run: `docker compose up -d --build`
3. Run: `docker compose exec backend alembic stamp head`

## More Info

- See [DEPLOYMENT.md](DEPLOYMENT.md) for complete documentation
- See [scripts/README.md](scripts/README.md) for all scripts

---

**No WSL or Git Bash required!**
