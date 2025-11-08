# LinkedIn Gateway Product Editions

## Edition Architecture

LinkedIn Gateway uses an **open-core model** with three distinct editions designed for different use cases and deployment scenarios.

---

## 1. Core Edition (Open Source)

**Status:** ✅ Available Now

### Overview
The open-source, self-hosted edition available to everyone. Public repository with full source code.

### Key Characteristics
- **Deployment:** Self-hosted (Docker, Railway, any cloud platform)
- **Code:** Public (open-source)
- **License:** No license required (default channel)
- **Server Execution:** ✅ **Allowed** (users own the server)
- **Local Accounts:** ✅ Enabled
- **Target Audience:** Individual developers, small teams, open-source community

### Feature Matrix
```python
allows_server_execution: True   # Can use server_call=true
has_local_accounts: True        # Local user authentication
requires_license: False         # No license validation (default)
has_licensing_server: False     # Uses SaaS licensing server if needed
```

### Use Cases
- Self-hosted LinkedIn automation
- Development and testing
- Custom integrations
- Privacy-focused deployments

---

## 2. SaaS Edition (Cloud Service)

**Status:** ✅ Available Now (Internal)

### Overview
Single cloud instance hosted and managed exclusively by AInnovate. This is YOUR production service at `lg.ainnovate.tech`.

### Key Characteristics
- **Deployment:** Cloud-hosted by AInnovate (ONLY ONE INSTANCE)
- **Code:** Private (not publicly released)
- **License:** Not required (is the licensing authority itself)
- **Server Execution:** ❌ **DISABLED** (security and control)
- **Access Mode:** Browser extension only (proxy mode)
- **Licensing Server:** ✅ **Contains the central licensing/validation endpoint for all other editions**
- **Target Audience:** End users, businesses (subscription model)

### Feature Matrix
```python
allows_server_execution: False  # Users CANNOT use server_call=true
has_local_accounts: False       # No local accounts (OAuth/SSO only)
requires_license: False         # SaaS itself doesn't need license
has_licensing_server: True      # ⭐ Provides licensing for other editions
```

### Architecture Notes
- Users connect via browser extension
- All operations are proxy-mode only
- Server-side execution is disabled for users
- **Contains the licensing server used by Enterprise and Railway editions**
- Not self-hostable by customers

### Use Cases
- Cloud-based LinkedIn automation service
- Subscription-based SaaS offering
- Central licensing authority for all other editions

---

## 3. Enterprise Edition

**Status:** ✅ Implemented (Not Yet Released)

### Overview
Self-hosted premium edition with more features than Core. Requires license validation against the SaaS licensing server.

### Key Characteristics
- **Deployment:** Self-hosted (Railway, Docker, enterprise infrastructure)
- **Code:** Private/Licensed
- **License:** ✅ **Required** (validated against SaaS licensing server)
- **Server Execution:** ✅ **Allowed** (enterprise owns the server)
- **Target Audience:** Large organizations, enterprises, premium customers

### Feature Matrix
```python
allows_server_execution: True   # Enterprise can use server_call=true
has_local_accounts: True        # Local account management
requires_license: True          # Must validate license with SaaS
has_licensing_server: False     # Uses SaaS licensing server
```

### Use Cases
- Enterprise self-hosted with premium features
- Advanced LinkedIn automation with server-side execution
- Team/organization management
- Custom enterprise integrations
- Licensed premium version with more features than Core

---

## Edition Comparison

| Feature | Core | SaaS | Enterprise |
|---------|------|------|------------|
| **Deployment** | Self-hosted | Cloud (by us) | Self-hosted |
| **Code Access** | Public | Private | Private |
| **License Required** | ❌ No* | ❌ No | ✅ Yes |
| **Server Execution** | ✅ Allowed | ❌ Disabled | ✅ Allowed |
| **Local Accounts** | ✅ Yes | ❌ No (OAuth/SSO) | ✅ Yes |
| **Licensing Server** | ❌ No | ✅ **Yes** | ❌ No (uses SaaS) |
| **Target Audience** | Developers, OSS | End users | Enterprises |

\* Railway private channel requires license

---

## Deployment Channels

In addition to editions, the system supports deployment channels:

### `default` (Standard)
- Standard deployment for most use cases
- No special restrictions
- Core: No license required
- SaaS: Contains licensing server
- Enterprise: License required

### `railway_private` (Railway Template)
- Core edition deployed via Railway template
- Requires license validation (even for Core)
- Special channel for Railway marketplace customers
- Validates license against SaaS licensing server

---

## Edition Selection

Edition is controlled via environment variable:

```bash
# Core Edition (default)
LG_BACKEND_EDITION=core

# SaaS Edition
LG_BACKEND_EDITION=saas

# Enterprise Edition
LG_BACKEND_EDITION=enterprise
```

---

## Licensing Architecture

### Central Licensing Server (in SaaS Edition)
- **Location:** SaaS edition ONLY (single instance at lg.ainnovate.tech)
- **Feature Flag:** `has_licensing_server=True` (only for SaaS)
- **Purpose:** Provides license validation endpoint for all other editions

### License Validation Flow
```
1. Self-hosted instance (Railway Core/Enterprise) starts
2. If requires_license=True, contact SaaS licensing endpoint
3. SaaS validates license key
4. Instance receives validation response
5. Features enabled/disabled based on validation
```

### Who Requires License?
- **Core (default channel):** ❌ No
- **Core (railway_private channel):** ✅ Yes
- **SaaS:** ❌ No (is the licensing authority)
- **Enterprise:** ✅ Yes

---

## Security Model

### Core Edition
- Users own and control the server
- Full control over data and execution
- Self-managed security

### SaaS Edition
- AInnovate owns and controls the server
- Server-side execution disabled for users (security)
- All user operations via browser extension (proxy mode)
- Controlled environment
- **Hosts the licensing server for ecosystem**

### Enterprise Edition
- Enterprise owns and controls their server
- Licensed features from AInnovate
- Self-managed security
- License validated against central SaaS licensing server

---

## Feature Matrix Details

### `allows_server_execution`
- **True:** Can use `server_call=true` parameter in API calls
- **False:** Must use proxy mode via browser extension
- **Core:** True (they own the server)
- **SaaS:** False (cloud service, users don't own server)
- **Enterprise:** True (they own the server)

### `has_local_accounts`
- **True:** Local username/password authentication available
- **False:** Must use OAuth/SSO
- **Core:** True
- **SaaS:** False (OAuth/SSO only)
- **Enterprise:** True

### `requires_license`
- **True:** Must validate license key with SaaS licensing server
- **False:** No license validation needed
- **Core:** False (default), True (railway_private)
- **SaaS:** False (is the licensing authority)
- **Enterprise:** True

### `has_licensing_server`
- **True:** This instance provides licensing validation for others
- **False:** Uses external licensing server or none
- **Core:** False
- **SaaS:** **True** (provides licensing for all others)
- **Enterprise:** False (uses SaaS licensing server)

---

## Development Strategy

### Current Phase (Phase 5)
- ✅ Edition detection system implemented
- ✅ Feature matrix framework in place
- ✅ Core, SaaS, and Enterprise editions defined
- ✅ Licensing server feature identified (SaaS only)
- 🚧 Infrastructure setup in progress

### Future Phases
- Implement licensing validation in Core (railway_private)
- Implement licensing validation in Enterprise
- Build licensing server endpoints in SaaS
- Create Railway template with licensing
- Public release of Core edition

---

## Notes

- **SaaS is NOT self-hostable** - It's your single cloud instance
- **SaaS contains the licensing server** - Central authority for all editions
- **Core is fully open** - Public code, no restrictions (except Railway template needs license)
- **Enterprise is self-hosted + licensed** - Premium features with license validation
- **Only discussed features are implemented** - No analytics, billing, organizations yet
