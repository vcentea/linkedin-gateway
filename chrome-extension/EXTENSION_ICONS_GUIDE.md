# Extension Icons Guide

## Icon Locations

### Source Icons
All extension icons are located in:
```
chrome-extension/src-v2/assets/icons/
```

### Required Icons
The manifest requires the following icon sizes:
- `icon16.png` - 16x16 pixels (shown in extension toolbar)
- `icon48.png` - 48x48 pixels (shown in extension management page)
- `icon128.png` - 128x128 pixels (shown in Chrome Web Store)

### Current Status
✅ All required icons are present in `src-v2/assets/icons/`:
- ✅ `icon16.png`
- ✅ `icon48.png`
- ✅ `icon128.png`

## Manifest Configuration

The icons are referenced in `manifest.v2.json`:

```json
{
  "icons": {
    "16": "assets/icons/icon16.png",
    "48": "assets/icons/icon48.png",
    "128": "assets/icons/icon128.png"
  }
}
```

## Build Process

### Webpack Configuration
Both development and production webpack configs are set up to copy icons:

**Development Build** (`webpack.config.v2.js`):
```javascript
new CopyPlugin({
  patterns: [
    { from: 'src-v2/assets', to: 'assets', noErrorOnMissing: true }
  ]
})
```
- Output: `chrome-extension/dist-dev/assets/icons/`

**Production Build** (`webpack.config.prod.v2.js`):
```javascript
new CopyPlugin({
  patterns: [
    { from: 'src-v2/assets', to: 'assets', noErrorOnMissing: true }
  ]
})
```
- Output: `chrome-extension/dist-prod/assets/icons/`

### Build Commands

**Development Build:**
```bash
npm run build:dev
# or
npm run watch:dev
```
Icons will be copied to: `dist-dev/assets/icons/`

**Production Build:**
```bash
npm run build:prod
# or
npm run watch:prod
```
Icons will be copied to: `dist-prod/assets/icons/`

## Verification

### After Building
1. Build the extension (dev or prod)
2. Check that icons exist in the dist folder:
   - `dist-dev/assets/icons/icon16.png` (for dev)
   - `dist-prod/assets/icons/icon16.png` (for prod)
3. Check that `manifest.json` is copied to the dist folder
4. Load the extension in Chrome and verify icons appear correctly

### Where Icons Appear
- **Extension Toolbar**: Uses `icon16.png`
- **Extension Manager**: Uses `icon48.png`
- **Chrome Web Store**: Uses `icon128.png`

## Additional Icons in Assets

The assets folder also contains:
- `icon32.png` - Not currently referenced in manifest but available
- LinkedIn Sign-in buttons (Active, Default, Hover states)
- Other PNG assets

## Updating Icons

To update the extension icons:

1. **Replace the icon files** in `src-v2/assets/icons/`:
   - Ensure they are PNG format
   - Use exact dimensions (16x16, 48x48, 128x128)
   - Maintain transparent backgrounds if needed

2. **Rebuild the extension**:
   ```bash
   npm run build:dev
   # or
   npm run build:prod
   ```

3. **Reload the extension** in Chrome:
   - Go to `chrome://extensions/`
   - Click the reload icon on your extension

## Icon Design Guidelines

### Size Requirements
- **16x16**: Simple, recognizable at tiny size
- **48x48**: Clear details, medium size
- **128x128**: Full details, high quality

### Best Practices
- Use transparent backgrounds
- Maintain consistent design across sizes
- Test visibility on light and dark backgrounds
- Keep the design simple and recognizable

## Troubleshooting

### Icons Not Showing
1. **Check build output**: Verify icons are in `dist-dev/assets/icons/` or `dist-prod/assets/icons/`
2. **Check manifest**: Ensure paths match: `"assets/icons/icon16.png"`
3. **Rebuild**: Run `npm run build:dev` or `npm run build:prod`
4. **Reload extension**: Reload in `chrome://extensions/`

### Icons Show Default Chrome Icon
- Manifest paths are incorrect
- Icons not copied during build
- Icon files are corrupted or wrong format

### Build Not Copying Icons
- Check webpack config has CopyPlugin configured
- Verify `src-v2/assets` path is correct
- Check for build errors in console

