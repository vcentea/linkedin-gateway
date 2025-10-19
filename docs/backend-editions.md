# LinkedIn Gateway - Backend Editions

LinkedIn Gateway comes in two editions: **Core** (open-source) and **SaaS** (commercial). This document explains the differences and how to choose the right edition for your needs.

## Editions Overview

### Core Edition (Open Source)
The **Core Edition** is the open-source version of LinkedIn Gateway, perfect for:
- Self-hosting on your own infrastructure
- Full control over data and deployment
- No licensing fees
- Community support
- Local development and testing

**License:** MIT (or your chosen open-source license)

### SaaS Edition (Commercial)
The **SaaS Edition** includes additional enterprise features for:
- Multi-tenant organizations
- Advanced analytics and reporting
- Usage quotas and billing
- Premium support
- Managed deployments

**License:** Commercial (requires valid license key)

## Feature Matrix

| Feature | Core Edition | SaaS Edition |
|---------|--------------|--------------|
| **LinkedIn Integration** | ✅ Full | ✅ Full |
| **Chrome Extension** | ✅ Full | ✅ Full |
| **Server Execution** | ✅ Yes | ✅ Yes |
| **Local Account Management** | ✅ Yes | ✅ Yes |
| **REST API** | ✅ Full | ✅ Full |
| **WebSocket Support** | ✅ Yes | ✅ Yes |
| **PostgreSQL Database** | ✅ Yes | ✅ Yes |
| **OAuth Authentication** | ✅ Yes | ✅ Yes |
| | |
| **Organizations & Teams** | ❌ No | ✅ Yes |
| **Advanced Analytics** | ❌ No | ✅ Yes |
| **Usage Quotas** | ❌ No | ✅ Yes |
| **Billing Integration** | ❌ No | ✅ Yes |
| **License Management** | ❌ No | ✅ Yes |
| **Priority Support** | ❌ Community | ✅ Yes |
| **SLA Guarantees** | ❌ No | ✅ Yes |

## Channels

A **channel** defines where and how LinkedIn Gateway is deployed:

### `default` Channel
- Standard self-hosted deployment
- Full control over infrastructure
- Manual updates and maintenance
- Available for both Core and SaaS editions

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

# SaaS Edition
LG_BACKEND_EDITION=saas
LG_CHANNEL=default

# Railway Deployment
LG_BACKEND_EDITION=core
LG_CHANNEL=railway_private
```

### Checking Your Edition

You can verify your edition via the API:

```bash
curl http://localhost:7778/api/v1/server/info
```

Response:
```json
{
  "edition": "core",
  "channel": "default",
  "features": {
    "allows_server_execution": true,
    "has_local_accounts": true,
    "enables_analytics": false,
    "requires_license": false,
    "has_organizations": false,
    "has_billing": false
  },
  "version": "1.0.0"
}
```

## Choosing Your Edition

### Use Core Edition If You:
- ✅ Want full control over your data
- ✅ Prefer self-hosting
- ✅ Don't need multi-tenant features
- ✅ Have technical expertise for deployment
- ✅ Want to contribute to open source
- ✅ Need a cost-effective solution

### Use SaaS Edition If You:
- ✅ Need organization/team management
- ✅ Want advanced analytics
- ✅ Require usage quotas and billing
- ✅ Need enterprise support
- ✅ Prefer managed infrastructure
- ✅ Want SLA guarantees

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

#### Self-Hosted
```bash
cd deployment/scripts
# Requires SaaS configuration
docker compose -f docker-compose.yml -f docker-compose.saas.yml up -d
```

#### Managed Hosting
Contact us for managed SaaS hosting options.

## Upgrading Between Editions

### Core → SaaS
1. Update environment: `LG_BACKEND_EDITION=saas`
2. Add SaaS-specific configuration (Redis, billing, etc.)
3. Run SaaS migrations
4. Configure license key
5. Restart services

### SaaS → Core
1. Export data from SaaS features (organizations, analytics)
2. Update environment: `LG_BACKEND_EDITION=core`
3. Remove SaaS-specific services
4. Restart with core configuration

**Note:** Downgrading from SaaS to Core will lose SaaS-specific features and data.

## License Keys

### Core Edition
- ❌ No license required for default channel
- ✅ License required for `railway_private` channel
- License validates deployment method only
- All features remain free and open-source

### SaaS Edition
- ✅ Valid license key required
- License validates on startup and periodically
- Different tiers available (Starter, Professional, Enterprise)
- Contact sales for licensing options

## Support Options

### Core Edition
- 📖 Documentation: Full documentation available
- 💬 Community: GitHub Discussions, Issues
- 📧 Community Support: Best-effort basis
- 🤝 Contributions: PRs welcome!

### SaaS Edition
- ✅ All Core Edition support options
- 📞 Priority Support: Email & phone
- 🎯 SLA Guarantees: 99.9% uptime
- 🚀 Dedicated Support Engineer (Enterprise tier)
- 📊 Professional Services: Custom integrations

## Migration & Compatibility

### Version Compatibility
- Both editions use the same API
- Chrome extension works with both editions
- Database schema compatible (Core + SaaS migrations)
- Can switch editions without data loss (except SaaS-specific features)

### Data Portability
- Export your data anytime
- Standard PostgreSQL format
- API access to all your data
- No vendor lock-in

## Frequently Asked Questions

### Q: Is Core Edition really free?
**A:** Yes! Core Edition is open-source and free for any use, including commercial.

### Q: Can I host SaaS Edition myself?
**A:** Yes, but you need a valid commercial license.

### Q: What's included in Railway deployment?
**A:** PostgreSQL database, automatic backups, HTTPS, monitoring, and infrastructure management.

### Q: Can I try SaaS Edition features?
**A:** Contact us for a trial license to test SaaS features.

### Q: Do I need technical skills for Core Edition?
**A:** Basic Docker knowledge recommended. Railway template requires minimal technical knowledge.

### Q: Can I contribute to SaaS Edition?
**A:** No, SaaS Edition is proprietary. Contribute to Core Edition instead!

### Q: What happens if my license expires?
**A:** SaaS features stop working. Core features continue to work. You'll receive renewal reminders.

## Getting Started

### Try Core Edition
```bash
git clone https://github.com/youruser/linkedin-gateway.git
cd linkedin-gateway/deployment/scripts
./install-core.sh
```

### Deploy on Railway
[Get Railway Template](https://railway.app/template/...) (Requires license key)

### Contact Sales for SaaS
- Email: sales@linkedin-gateway.com
- Website: https://linkedin-gateway.com/pricing
- Schedule Demo: https://linkedin-gateway.com/demo

---

**Need Help?** 
- Core Edition: [GitHub Issues](https://github.com/youruser/linkedin-gateway/issues)
- SaaS Edition: support@linkedin-gateway.com

