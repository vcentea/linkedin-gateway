# Private Repository Setup for Enterprise/SaaS Editions

## Overview

LinkedIn Gateway has three editions:

- **Core Edition** (Open Source) - Available in the public repository
- **SaaS Edition** (Private) - Available in the private repository only
- **Enterprise Edition** (Private) - Available in the private repository only

If you're installing **Enterprise** or **SaaS** editions, you need access to the **private repository**.

## Problem

If you initially cloned from the public repository (`linkedin-gateway`), your installation will only have the Core edition and won't receive Enterprise/SaaS updates.

## Solution

Use the `setup-private-repo` script to switch to the private repository and configure authentication.

## Quick Start

### Windows

```batch
cd deployment\scripts
setup-private-repo.bat
```

### Linux/Mac

```bash
cd deployment/scripts
chmod +x setup-private-repo.sh
./setup-private-repo.sh
```

## What the Script Does

1. **Checks your current repository** - Detects if you're using public or private repo
2. **Offers to switch** - If using public repo, prompts to switch to private
3. **Sets up authentication** - Guides you through:
   - GitHub Personal Access Token (PAT) setup - **Recommended**
   - SSH Key setup (if you prefer)
4. **Tests access** - Verifies you can access the private repository
5. **Pulls latest code** - Downloads the latest Enterprise/SaaS code

## Authentication Methods

### Method 1: GitHub Personal Access Token (PAT) - Recommended

**Why**: Works on all platforms, no SSH setup needed

**Steps**:
1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a name: `LinkedIn Gateway`
4. Select scopes: **`repo`** (full control of private repositories)
5. Click "Generate token"
6. **Copy the token** (you won't see it again!)
7. Run the setup script and paste the token when prompted

### Method 2: SSH Key

**Why**: More secure, no password in URL

**Steps**:
1. Generate SSH key:
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   ```
2. Add to GitHub: https://github.com/settings/keys
3. Test it:
   ```bash
   ssh -T git@github.com
   ```
4. Run the setup script

## After Setup

Once the script completes, you can:

**Install Enterprise Edition**:
```bash
cd deployment/scripts
./install-enterprise.sh    # Linux/Mac
install-enterprise.bat     # Windows
```

**Update Enterprise Edition**:
```bash
cd deployment/scripts
./update-enterprise.sh     # Linux/Mac
update-enterprise.bat      # Windows
```

**Install SaaS Edition**:
```bash
cd deployment/scripts
./install-saas.sh          # Linux/Mac
install-saas.bat           # Windows
```

## Verifying Your Setup

Check which repository you're using:

```bash
git remote -v
```

**Public repo** (Core only):
```
origin  https://github.com/vcentea/linkedin-gateway.git (fetch)
origin  https://github.com/vcentea/linkedin-gateway.git (push)
```

**Private repo** (Enterprise/SaaS) - HTTPS with PAT:
```
origin  https://username:token@github.com/vcentea/linkedin-gateway-saas.git (fetch)
origin  https://username:token@github.com/vcentea/linkedin-gateway-saas.git (push)
```

**Private repo** (Enterprise/SaaS) - SSH:
```
origin  git@github.com:vcentea/linkedin-gateway-saas.git (fetch)
origin  git@github.com:vcentea/linkedin-gateway-saas.git (push)
```

## Troubleshooting

### "Authentication failed"

- **PAT**: Check your token has `repo` scope and hasn't expired
- **SSH**: Ensure your SSH key is added to GitHub and working (`ssh -T git@github.com`)

### "Enterprise files not found after setup"

Run:
```bash
git pull origin main
```

If you get conflicts:
```bash
git stash
git pull origin main
git stash pop
```

### "Permission denied (publickey)"

If using SSH and getting this error:
1. Generate a new SSH key (see Method 2 above)
2. Add it to GitHub
3. Re-run the setup script

### "remote: Repository not found"

- Check you have been granted access to the private repository
- Contact the repository owner to be added as a collaborator

### Still having issues?

1. Check your git configuration:
   ```bash
   git config --list
   ```

2. Try cloning fresh from private repo:
   ```bash
   cd ..
   git clone https://github.com/vcentea/linkedin-gateway-saas.git LinkedinGateway-Enterprise
   cd LinkedinGateway-Enterprise
   ```

## Security Notes

### Personal Access Token (PAT)

- **Never commit** your PAT to git
- The PAT is stored in `.git/config` (which is git-ignored)
- You can rotate the token anytime from GitHub settings
- If compromised, revoke it immediately on GitHub

### SSH Key

- Keep your private key (`~/.ssh/id_ed25519`) secure
- Never share it or commit it to git
- Use a passphrase for extra security

## For Repository Administrators

To grant someone access to the private repository:

1. Go to: https://github.com/vcentea/linkedin-gateway-saas/settings/access
2. Click "Add people"
3. Enter their GitHub username
4. Select role: **Write** (for updates) or **Read** (view only)
5. Send them this documentation

## What's the Difference?

| Feature | Core (Public) | Enterprise/SaaS (Private) |
|---------|--------------|---------------------------|
| Basic API endpoints | ✅ | ✅ |
| Chrome extension | ✅ | ✅ |
| Server-side execution | ❌ | ✅ |
| Latest features | After release | Immediately |
| Updates from | Public repo | Private repo |
| New endpoints (like `/connections/list`) | Not yet | ✅ Available now |

## Summary

1. **Core edition** → Clone from `linkedin-gateway` (public)
2. **Enterprise/SaaS** → Clone from `linkedin-gateway-saas` (private)
3. **Switching** → Run `setup-private-repo.sh` or `.bat`
4. **Authentication** → Use PAT (easiest) or SSH key

---

**Need help?** Open an issue or contact the repository administrator.

