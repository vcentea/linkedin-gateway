# LinkedIn Gateway - Backend Editions

LinkedIn Gateway comes in three editions: **Core** (open-source), **SaaS** (commercial cloud service), and **Enterprise** (self-hosted premium). This document explains the differences and how to choose the right edition for your needs.

## Editions Overview

### Core Edition (Open Source)
The **Core Edition** is the open-source version of LinkedIn Gateway, perfect for:
- Self-hosting on your own infrastructure
- Full control over data and deployment
- No licensing fees
- Community support
- Local development and testing

**License:** MIT (or your chosen open-source license)

### SaaS Edition (Commercial Cloud)
The **SaaS Edition** is a cloud-hosted service operated by AInnovate:
- Single managed cloud instance
- Browser extension proxy mode only
- No server-side execution (security)
- Subscription-based access
- Contains the central licensing server for other editions

**License:** Commercial subscription (users don't need a license key)

### Enterprise Edition (Self-Hosted Premium)
The **Enterprise Edition** is a self-hosted premium version with more features than Core:
- Self-hosting on your infrastructure
- Server-side execution enabled
- Premium enterprise features
- Professional support
- License validation required

**License:** Commercial (requires valid license key validated against SaaS licensing server)

## Feature Matrix

| Feature | Core Edition | SaaS Edition | Enterprise Edition |
|---------|--------------|--------------|-------------------|
| **LinkedIn Integration** | ✅ Full | ✅ Full | ✅ Full |
| **Chrome Extension** | ✅ Full | ✅ Full | ✅ Full |
| **Server Execution** | ✅ Yes | ❌ **No** | ✅ Yes |
| **Local Account Management** | ✅ Yes | ❌ No (OAuth only) | ✅ Yes |
| **REST API** | ✅ Full | ✅ Full | ✅ Full |
| **WebSocket Support** | ✅ Yes | ✅ Yes | ✅ Yes |
| **PostgreSQL Database** | ✅ Yes | ✅ Yes | ✅ Yes |
| **OAuth Authentication** | ✅ Yes | ✅ Yes | ✅ Yes |
| | | |
| **Organizations & Teams** | ❌ No | 🔜 Planned | 🔜 Coming Soon |
| **Advanced Analytics** | ❌ No | 🔜 Planned | 🔜 Coming Soon |
| **Usage Quotas** | ❌ No | 🔜 Planned | 🔜 Coming Soon |
| **Audit Logs** | ❌ No | 🔜 Planned | 🔜 Coming Soon |
| **Billing Integration** | ❌ No | 🔜 Planned | ❌ No |
| **Licensing Server** | ❌ No | ✅ Yes | ❌ No (uses SaaS) |
| **Priority Support** | ❌ Community | ✅ Yes | ✅ Yes (when licensed) |
| **SLA Guarantees** | ❌ No | ✅ Yes | ✅ Yes (when licensed) |

## Channels

A **channel** defines where and how LinkedIn Gateway is deployed:

### `default` Channel
- Standard self-hosted deployment
- Full control over infrastructure
- Manual updates and maintenance
- Available for Core, SaaS, and Enterprise editions

### `railway_private` Channel (Core Edition Only)
- One-click deployment on Railway
- Automatic infrastructure provisioning
- PostgreSQL included
- Requires valid license key
- Automatic updates

## Configuration

### Setting the Edition

The edition is configured via environment variables:

```bash
# Core Edition (default)
LG_BACKEND_EDITION=core
LG_CHANNEL=default

# SaaS Edition (cloud service)
LG_BACKEND_EDITION=saas
LG_CHANNEL=default

# Enterprise Edition (self-hosted premium)
LG_BACKEND_EDITION=enterprise
LG_CHANNEL=default

# Railway Deployment (Core only)
LG_BACKEND_EDITION=core
LG_CHANNEL=railway_private
```

### Checking Your Edition

You can verify your edition via the API:

```bash
curl http://localhost:7778/api/v1/server/info
```

Response examples:

**Core Edition:**
```json
{
  "edition": "core",
  "channel": "default",
  "features": {
    "allows_server_execution": true,
    "has_local_accounts": true,
    "requires_license": false,
    "has_licensing_server": false
  },
  "version": "1.0.0"
}
```

**Enterprise Edition:**
```json
{
  "edition": "enterprise",
  "channel": "default",
  "features": {
    "allows_server_execution": true,
    "has_local_accounts": true,
    "requires_license": true,
    "has_licensing_server": false
  },
  "version": "1.0.0"
}
```

## Choosing Your Edition

### Use Core Edition If You:
- ✅ Want full control over your data
- ✅ Prefer self-hosting
- ✅ Don't need premium features
- ✅ Have technical expertise for deployment
- ✅ Want to contribute to open source
- ✅ Need a cost-effective solution

### Use SaaS Edition If You:
- ✅ Prefer cloud-hosted solution
- ✅ Don't want to manage infrastructure
- ✅ Need subscription-based access
- ✅ Want managed service with SLA
- ✅ Accept proxy-mode only (no server-side execution)

### Use Enterprise Edition If You:
- ✅ Need server-side execution (server_call=true)
- ✅ Want more features than Core
- ✅ Prefer self-hosting over cloud
- ✅ Need professional support
- ✅ Require compliance/security control
- ✅ Want premium features with self-hosting

## Deployment Options

### Core Edition Deployment

#### Self-Hosted (Docker)
```bash
cd deployment/scripts
./install-core.sh
```

#### Railway (One-Click)
1. Get license key (required for Railway)
2. Click "Deploy to Railway" button
3. Enter license key
4. Your instance is ready!

**Why license for Railway?** The Railway template provides a premium managed experience with automatic infrastructure, backups, and support.

### SaaS Edition Deployment

#### Cloud Service
SaaS is hosted and managed by AInnovate. Users connect via browser extension.

Contact us for access to the SaaS service.

### Enterprise Edition Deployment

#### Self-Hosted (Docker)
```bash
cd deployment/scripts
./install-enterprise.sh
```

See [deployment/docs/ENTERPRISE_QUICK_START.md](../deployment/docs/ENTERPRISE_QUICK_START.md) for complete setup instructions.

## Upgrading Between Editions

### Core → Enterprise
1. Update environment: `LG_BACKEND_EDITION=enterprise`
2. Add license key configuration (when licensing is implemented)
3. Restart services
4. Enable optional features via `ENT_FEATURE_*` flags

### Enterprise → Core
1. Update environment: `LG_BACKEND_EDITION=core`
2. Remove Enterprise-specific configuration
3. Restart services

**Note:** Downgrading from Enterprise to Core will lose access to premium features.

### Switching to/from SaaS
**Not recommended.** SaaS is a cloud service, not self-hosted. Migration between self-hosted (Core/Enterprise) and cloud (SaaS) requires manual data migration.

## License Keys

### Core Edition
- ❌ No license required for default channel
- ✅ License required for `railway_private` channel
- License validates deployment method only
- All features remain free and open-source

### SaaS Edition
- ❌ No license key required (subscription-based cloud service)
- Users authenticate via OAuth
- Service operated by AInnovate

### Enterprise Edition
- ✅ Valid license key required (not enforced yet)
- License validates against SaaS licensing server
- Enables premium features
- Professional support included
- Contact sales for licensing options

## Support Options

### Core Edition
- 📖 Documentation: Full documentation available
- 💬 Community: GitHub Discussions, Issues
- 📧 Community Support: Best-effort basis
- 🤝 Contributions: PRs welcome!

### SaaS Edition
- 📞 Priority Support: Email support
- 🎯 SLA Guarantees: Service uptime
- 📊 Managed Infrastructure: No self-hosting required

### Enterprise Edition
- ✅ All Core Edition support options
- 📞 Priority Support: Email & phone
- 🎯 SLA Guarantees: 99.9% uptime (when licensed)
- 🚀 Professional Support: Dedicated assistance
- 📊 Professional Services: Custom integrations available

## Migration & Compatibility

### Version Compatibility
- All editions use compatible APIs
- Chrome extension works with all editions
- Database schema compatible (Core + Enterprise + SaaS migrations)
- Can switch between Core/Enterprise without data loss (except edition-specific features)

### Data Portability
- Export your data anytime
- Standard PostgreSQL format
- API access to all your data
- No vendor lock-in for self-hosted editions

## Frequently Asked Questions

### Q: Is Core Edition really free?
**A:** Yes! Core Edition is open-source and free for any use, including commercial.

### Q: Can I self-host SaaS Edition?
**A:** No, SaaS Edition is a cloud service operated by AInnovate. For self-hosting, use Core or Enterprise editions.

### Q: Can I self-host Enterprise Edition?
**A:** Yes! Enterprise is designed for self-hosting with premium features. Requires a valid license key.

### Q: What's included in Railway deployment?
**A:** PostgreSQL database, automatic backups, HTTPS, monitoring, and infrastructure management.

### Q: Can I try Enterprise features?
**A:** Contact us for a trial license to test Enterprise features.

### Q: Do I need technical skills for Enterprise Edition?
**A:** Yes, similar to Core Edition. Basic Docker and Linux/Windows server knowledge recommended.

### Q: What's the difference between Core and Enterprise?
**A:** Enterprise includes premium features (Organizations, Quotas, Audit Logs - coming soon), professional support, and license validation. Core is fully open-source.

### Q: Can I contribute to Enterprise/SaaS Edition?
**A:** No, Enterprise and SaaS editions are proprietary. Contribute to Core Edition instead!

### Q: What happens if my license expires?
**A:** Enterprise-specific features stop working. Core features continue to work. You'll receive renewal reminders.

### Q: Why is server execution disabled in SaaS?
**A:** Security and control. Since SaaS is our cloud service, we don't allow users to execute arbitrary code on our servers. Use Core or Enterprise for server-side execution.

## Getting Started

### Try Core Edition
```bash
git clone https://github.com/youruser/linkedin-gateway.git
cd linkedin-gateway/deployment/scripts
./install-core.sh
```

### Deploy on Railway
[Get Railway Template](https://railway.app/template/...) (Requires license key)

### Get Enterprise Edition
Enterprise Edition is available in a private repository. Contact us for access.

```bash
git clone <private-enterprise-repo>
cd LinkedinGateway-SaaS/deployment/scripts
./install-enterprise.sh
```

See [deployment/docs/ENTERPRISE_QUICK_START.md](../deployment/docs/ENTERPRISE_QUICK_START.md) for complete setup.

### Access SaaS Service
Contact us for access to the cloud-hosted SaaS service.

### Contact Sales
- Core Edition: Free and open-source
- Enterprise Edition: Contact for licensing
- SaaS Service: Contact for access

---

**Need Help?** 
- Core Edition: [GitHub Issues](https://github.com/youruser/linkedin-gateway/issues)
- Enterprise Edition: Professional support (when licensed)
- SaaS Service: Managed support

