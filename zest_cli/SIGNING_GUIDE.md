# Code Signing & Notarization Guide

This guide covers how to sign and notarize Zest for distribution outside the Mac App Store.

## Prerequisites

1. **Apple Developer Account** ($99/year)
2. **Developer ID Certificates**:
   - Developer ID Application (for signing .app)
   - Developer ID Installer (for signing .pkg)

## Step 1: Get Developer ID Certificates

### Option A: Using Xcode

1. Open Xcode
2. Go to **Xcode > Preferences > Accounts**
3. Add your Apple ID
4. Click **Manage Certificates**
5. Click **+** and select:
   - Developer ID Application
   - Developer ID Installer

### Option B: Using Developer Portal

1. Go to [Apple Developer Certificates](https://developer.apple.com/account/resources/certificates/list)
2. Create **Developer ID Application** certificate
3. Create **Developer ID Installer** certificate
4. Download and install both certificates

## Step 2: Find Your Team ID

```bash
# List all signing identities
security find-identity -v -p codesigning

# Output will look like:
# 1) ABC123DEF456 "Developer ID Application: Your Name (TEAM123)"
# 2) XYZ789GHI012 "Developer ID Installer: Your Name (TEAM123)"
#
# Your Team ID is: TEAM123
```

## Step 3: Sign the App Bundle

Edit `build.sh` and uncomment the code signing section:

```bash
# Sign the app bundle
codesign --deep --force --verify --verbose \
    --sign "Developer ID Application: Your Name (TEAM_ID)" \
    --options runtime \
    --entitlements entitlements.plist \
    "$APP_BUNDLE"
```

### Create entitlements.plist

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <key>com.apple.security.cs.allow-dyld-environment-variables</key>
    <true/>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
</dict>
</plist>
```

These entitlements are needed for PyInstaller bundles that load dynamic libraries.

## Step 4: Sign the Installer

Edit `create_installer.sh` and uncomment the signing section:

```bash
# Sign the installer package
productsign \
    --sign "Developer ID Installer: Your Name (TEAM_ID)" \
    "$DIST_DIR/Zest-$VERSION.pkg" \
    "$DIST_DIR/Zest-$VERSION-signed.pkg"

mv "$DIST_DIR/Zest-$VERSION-signed.pkg" "$DIST_DIR/Zest-$VERSION.pkg"
```

## Step 5: Notarize with Apple

Notarization is required for macOS 10.15+ to avoid Gatekeeper warnings.

### 5.1: Create App-Specific Password

1. Go to [appleid.apple.com](https://appleid.apple.com)
2. Sign in
3. Go to **Security > App-Specific Passwords**
4. Generate a new password
5. Save it securely

### 5.2: Store Credentials in Keychain

```bash
xcrun notarytool store-credentials "zest-notarize" \
    --apple-id "your-apple-id@example.com" \
    --team-id "TEAM123" \
    --password "your-app-specific-password"
```

### 5.3: Submit for Notarization

```bash
# Submit the signed .pkg
xcrun notarytool submit \
    ./dist/Zest-1.0.0.pkg \
    --keychain-profile "zest-notarize" \
    --wait

# This will output a submission ID
```

### 5.4: Check Notarization Status

```bash
# If you didn't use --wait, check status manually:
xcrun notarytool info SUBMISSION_ID \
    --keychain-profile "zest-notarize"
```

### 5.5: Get Notarization Log (if failed)

```bash
xcrun notarytool log SUBMISSION_ID \
    --keychain-profile "zest-notarize" \
    notarization-log.json

# View the log
cat notarization-log.json
```

## Step 6: Staple the Notarization Ticket

Once notarization succeeds, staple the ticket to the package:

```bash
xcrun stapler staple ./dist/Zest-1.0.0.pkg

# Verify stapling
xcrun stapler validate ./dist/Zest-1.0.0.pkg
```

## Step 7: Verify Everything Works

```bash
# Check code signature
codesign -vvv --deep --strict ./dist/Zest.app

# Check installer signature
pkgutil --check-signature ./dist/Zest-1.0.0.pkg

# Check notarization
spctl -a -vvv -t install ./dist/Zest-1.0.0.pkg
```

## Complete Build & Sign Workflow

Create a `release.sh` script:

```bash
#!/bin/bash
set -e

VERSION="1.0.0"

# Build
echo "🔨 Building..."
./build.sh

# Create installer
echo "📦 Creating installer..."
./create_installer.sh

# Notarize
echo "📝 Submitting for notarization..."
xcrun notarytool submit \
    ./dist/Zest-$VERSION.pkg \
    --keychain-profile "zest-notarize" \
    --wait

# Staple
echo "✅ Stapling notarization..."
xcrun stapler staple ./dist/Zest-$VERSION.pkg

# Verify
echo "🔍 Verifying..."
spctl -a -vvv -t install ./dist/Zest-$VERSION.pkg

echo "🎉 Release ready: ./dist/Zest-$VERSION.pkg"
```

## Common Issues

### "code object is not signed at all"

- Make sure you uncommented the signing section in `build.sh`
- Verify your certificate is installed: `security find-identity -v`

### "bundle format unrecognized, invalid, or unsuitable"

- Check Info.plist is valid XML
- Ensure CFBundleExecutable matches the actual executable name

### "The signature does not include a secure timestamp"

- Add `--timestamp` flag to codesign:
  ```bash
  codesign --timestamp --deep --force ...
  ```

### Notarization fails with "Invalid binary"

- PyInstaller bundles may need additional entitlements
- Check notarization log for specific issues
- May need to sign individual dylibs inside the bundle

### "Stapling failed"

- Wait a few minutes after notarization before stapling
- Ensure notarization actually succeeded (check status)

## Testing Distribution

### Test on a Different Mac

1. Copy the .pkg to another Mac (or use a VM)
2. Double-click to install
3. You should NOT see any Gatekeeper warnings
4. The app should run without "cannot verify developer" messages

### Test Gatekeeper

```bash
# Clear Gatekeeper cache
sudo spctl --master-disable
sudo spctl --master-enable

# Try to install
sudo installer -pkg ./dist/Zest-1.0.0.pkg -target /
```

## Resources

- [Apple Code Signing Guide](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/)
- [Notarization Documentation](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [Hardened Runtime Entitlements](https://developer.apple.com/documentation/security/hardened_runtime)

## Quick Reference

```bash
# Sign app
codesign --sign "Developer ID Application: Name (TEAM)" --options runtime app.app

# Sign pkg
productsign --sign "Developer ID Installer: Name (TEAM)" input.pkg output.pkg

# Notarize
xcrun notarytool submit file.pkg --keychain-profile "profile-name" --wait

# Staple
xcrun stapler staple file.pkg

# Verify
spctl -a -vvv -t install file.pkg
```
