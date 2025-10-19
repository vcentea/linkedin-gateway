# LinkedIn Gateway Chrome Extension

A Chrome extension that connects your LinkedIn profile with matching opportunities and enhances your LinkedIn experience with advanced tooling.

## Features

- Secure backend authentication
- LinkedIn session integration
- Dashboard for quick access to tools
- Status monitoring for LinkedIn connection
- Profile data management

## Project Structure

The extension follows a modular architecture:

```
chrome-extension/
├── src/                  # Source code root
│   ├── background/       # Background Service Worker scripts
│   │   ├── index.js      # Entry point, message router
│   │   ├── auth.js       # Token handling, backend auth API calls
│   │   └── linkedin.js   # LinkedIn session checks, opening LinkedIn tab
│   ├── content/          # Scripts injected into web pages
│   │   └── content.js    # LinkedIn page interactions
│   ├── pages/            # UI Pages for the extension
│   │   ├── app/          # Main dashboard application UI
│   │   │   ├── index.html    # Dashboard HTML
│   │   │   ├── main.js       # Dashboard JS
│   │   │   └── components/   # Reusable UI components
│   │   └── auth/         # Login UI page
│   │       ├── login.html
│   │       └── login.js
│   ├── shared/           # Modules shared across scripts
│   │   ├── api.js        # Backend HTTP requests
│   │   ├── config.js     # Configuration constants
│   │   ├── constants.js  # Shared constants
│   │   ├── utils.js      # General utilities
│   │   └── storage.js    # Chrome storage wrapper
│   └── assets/           # Static assets
│       ├── icons/        # Extension icons
│       └── images/       # Other images for UI
├── manifest.json         # Chrome Extension Manifest V3
└── package.json          # Dependencies & build scripts
```

## Development

1. Clone the repository
2. Install dependencies: `npm install`
3. Load the extension in Chrome:
   - Go to `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked"
   - Select the `chrome-extension` directory

## Environment

The extension connects to the LinkedIn Gateway backend API for authentication and data processing.

- Backend API: https://lgdev.ainnovate.tech
- LinkedIn integration: Uses the user's active LinkedIn session via cookies 