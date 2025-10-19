# LinkedIn Gateway - Open Core

> **Unofficial LinkedIn API Gateway** - Access LinkedIn data programmatically through a Chrome extension and REST API.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)

## ⚠️ Important Notice

This is an **unofficial** tool and is not affiliated with, endorsed by, or connected to LinkedIn Corporation. Use at your own risk and in accordance with LinkedIn's Terms of Service.

## 🚀 What is LinkedIn Gateway?

LinkedIn Gateway bridges the gap between LinkedIn's web interface and your applications by providing:

- **Chrome Extension**: Captures LinkedIn session and proxies requests
- **REST API**: Clean, documented endpoints for LinkedIn data
- **Self-Hosted**: Full control over your data and infrastructure
- **Open Core**: Free and open source for self-hosting

## ✨ Features

### Core Features (Open Source)

- 🔐 **Secure Authentication**: Uses your existing LinkedIn session
- 📊 **Profile Data**: Fetch profile information, skills, experience
- 🔗 **Connections**: Manage and view your LinkedIn connections
- 💬 **Messaging**: Send and receive LinkedIn messages
- 📰 **Feed Access**: Read and interact with your LinkedIn feed
- 🔌 **WebSocket Support**: Real-time updates and notifications
- 🐳 **Docker Ready**: One-command deployment with Docker Compose

### Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌────────────┐
│  Chrome         │◄────►│  Backend API     │◄────►│  Your App  │
│  Extension      │      │  (FastAPI)       │      │            │
└─────────────────┘      └──────────────────┘      └────────────┘
        │                         │
        │                         │
        ▼                         ▼
┌─────────────────┐      ┌──────────────────┐
│  LinkedIn       │      │  PostgreSQL      │
│  (via session)  │      │  Database        │
└─────────────────┘      └──────────────────┘
```

## 📋 Prerequisites

- **Docker & Docker Compose** (required - must be installed before running the installer)
- OR **Python 3.11+** and **PostgreSQL** (for manual setup without Docker)
- **Google Chrome** or **Chromium-based browser**
- **LinkedIn Account** (required for functionality)

### Installing Docker

**Linux:**
- Ubuntu/Debian: https://docs.docker.com/engine/install/ubuntu/
- CentOS/RHEL: https://docs.docker.com/engine/install/centos/

**Windows:**
- Download Docker Desktop: https://www.docker.com/products/docker-desktop

**macOS:**
- Download Docker Desktop: https://www.docker.com/products/docker-desktop

## 🛠️ Quick Start

### Option 1: Docker Deployment (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/vcentea/linkedin-gateway.git
   cd linkedin-gateway
   ```

2. **Run the installation script**:
   ```bash
   # Windows
   deployment\scripts\install-core.bat

   # Linux/Mac
   chmod +x deployment/scripts/install-core.sh
   ./deployment/scripts/install-core.sh
   ```

3. **Access the API**:
   - API: `http://localhost:7778`
   - API Docs: `http://localhost:7778/docs`
   - Health Check: `http://localhost:7778/health`

### Option 2: Manual Setup

<details>
<summary>Click to expand manual setup instructions</summary>

#### Backend Setup

1. **Install dependencies**:
   ```bash
   cd backend
   pip install -r requirements/base.txt
   ```

2. **Configure environment**:
   ```bash
   cp deployment/.env.example deployment/.env
   # Edit .env with your database credentials
   ```

3. **Run migrations**:
   ```bash
   alembic upgrade head
   ```

4. **Start the server**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 7778
   ```

#### Chrome Extension Setup

1. **Build the extension**:
   ```bash
   cd chrome-extension
   npm install
   npm run build
   ```

2. **Load in Chrome**:
   - Open `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked"
   - Select `chrome-extension/dist-dev/` directory

</details>

## 📚 Usage

### 1. Install Chrome Extension

Load the extension from `chrome-extension/dist-dev/` in Chrome developer mode.

### 2. Configure Server Connection

Click the extension icon and configure your backend server URL (default: `http://localhost:7778`).

### 3. Login to LinkedIn

Visit LinkedIn and log in normally. The extension will capture your session.

### 4. Use the API

```bash
# Get server info
curl http://localhost:7778/api/v1/server/info

# Get your profile
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:7778/api/v1/profiles/me

# Get connections
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:7778/api/v1/connections

# Send a message
curl -X POST \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"recipient":"linkedin-profile-id","message":"Hello!"}' \
     http://localhost:7778/api/v1/messages
```

## 📖 Documentation

- **[API Documentation](docs/API.md)** - Complete API reference
- **[Product Editions](docs/backend-editions.md)** - Core vs. SaaS features
- **[Troubleshooting](docs/TROUBLESHOOTING_SERVER_CONNECTION.md)** - Common issues

## 🏗️ Project Structure

```
linkedin-gateway/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── api/         # API endpoints
│   │   ├── auth/        # Authentication
│   │   ├── core/        # Core configuration
│   │   ├── db/          # Database models
│   │   ├── linkedin/    # LinkedIn integration
│   │   └── schemas/     # Pydantic schemas
│   ├── alembic/         # Database migrations
│   └── main.py          # Application entry point
├── chrome-extension/    # Browser extension
│   ├── src-v2/          # Extension source code
│   └── manifest.json    # Extension manifest
├── deployment/          # Deployment configs
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── scripts/         # Deployment scripts
└── docs/                # Documentation
```

## 🔧 Configuration

### Environment Variables

Key configuration options in `deployment/.env`:

```bash
# Edition (core or saas)
LG_BACKEND_EDITION=core
LG_CHANNEL=default

# Database
DATABASE_URL=postgresql://user:pass@localhost/dbname
# OR individual components:
DB_HOST=localhost
DB_PORT=5432
DB_NAME=linkedin_gateway
DB_USER=postgres
DB_PASSWORD=your_password

# Security
JWT_SECRET_KEY=your-secret-key-here
CORS_ORIGINS=chrome-extension://*

# API
DEFAULT_RATE_LIMIT=100
```

See `deployment/.env.example` for all options.

## 🔐 Security Considerations

- **Never share your API keys** or LinkedIn session tokens
- **Use HTTPS** in production environments
- **Rotate API keys** regularly
- **Monitor rate limits** to avoid LinkedIn restrictions
- **Review LinkedIn's Terms of Service** before using

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Standards

- Follow PEP 8 for Python code
- Use ESLint for JavaScript code
- Write tests for new features
- Update documentation as needed

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is provided "as is" without warranty of any kind. The developers are not responsible for:

- Any consequences of using this tool
- Violations of LinkedIn's Terms of Service
- Account restrictions or bans
- Data loss or corruption

**Use responsibly and at your own risk.**

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Database with [PostgreSQL](https://www.postgresql.org/)
- Containerization with [Docker](https://www.docker.com/)

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/vcentea/linkedin-gateway/issues)
- **Discussions**: [GitHub Discussions](https://github.com/vcentea/linkedin-gateway/discussions)

---

**Note**: This is the open-core edition. For managed hosting and additional features, contact the maintainers.

Made with ❤️ by the open source community

