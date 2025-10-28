# Build Environments Configuration

This document explains how to build the Chrome extension for different environments (dev/prod) without changing any code.

## Environment URLs

### Development (DEV)
- **API URL:** `https://lgdev.ainnovate.tech`
- **WebSocket URL:** `wss://lgdev.ainnovate.tech/ws`

### Production (PROD)
- **API URL:** `https://lg.ainnovate.tech`
- **WebSocket URL:** `wss://lg.ainnovate.tech/ws`

## How It Works

The URLs are injected at **build time** using webpack's `DefinePlugin`. The code uses `process.env.API_URL` and `process.env.WSS_URL`, which are replaced with the actual URLs during the build process.

### Configuration Files

1. **`src-v2/shared/config/app.config.js`** - Uses environment variables with fallback to dev URLs
2. **`webpack.config.v2.js`** - DEV build configuration (injects dev URLs)
3. **`webpack.config.prod.v2.js`** - PROD build configuration (injects prod URLs)

## Build Commands

### Development Build
```bash
npm run build:dev
```
- Uses `webpack.config.v2.js`
- Injects DEV URLs
- Outputs to `dist-dev/`
- Includes source maps for debugging

### Production Build
```bash
npm run build:prod
```
- Uses `webpack.config.prod.v2.js`
- Injects PROD URLs
- Outputs to `dist-prod/`
- Minified and optimized
- No source maps

### Watch Mode (Auto-rebuild on changes)

**Development:**
```bash
npm run watch:dev
```

**Production:**
```bash
npm run watch:prod
```

## Batch Files (Windows)

You can also use the batch file for dev builds:
```bash
build-v2.bat
```

## Verifying the Build

After building, you can verify which environment URLs were injected by:

1. Open `dist-dev/background.bundle.js` or `dist-prod/background.bundle.js`
2. Search for `ainnovate.tech`
3. You should see either:
   - `lgdev.ainnovate.tech` (in `dist-dev/`)
   - `lg.ainnovate.tech` (in `dist-prod/`)

## Important Notes

- ✅ **No code changes needed** - Just run the appropriate build command
- ✅ **Single source of truth** - All URLs defined in webpack configs
- ✅ **Type-safe** - The code still uses the same `appConfig` object
- ✅ **Manifest permissions** - Both URLs are already whitelisted in `manifest.v2.json`

## Deployment Checklist

### For Development
1. Run `npm run build:dev`
2. Load `dist-dev/` folder in Chrome as unpacked extension
3. Extension will connect to `lgdev.ainnovate.tech`

### For Production
1. Run `npm run build:prod`
2. Zip the `dist-prod/` folder
3. Upload to Chrome Web Store
4. Extension will connect to `lg.ainnovate.tech`

## Troubleshooting

**Q: Extension still connecting to wrong URL?**
- Clear the `dist-dev/` or `dist-prod/` folder and rebuild
- Check browser console for the actual URL being used
- Verify you ran the correct build command
- Make sure you're loading the correct dist folder in Chrome

**Q: How to add a new environment (e.g., staging)?**
1. Create `webpack.config.staging.v2.js`
2. Add `DefinePlugin` with staging URLs
3. Add npm script: `"build:staging": "webpack --config webpack.config.staging.v2.js"`

