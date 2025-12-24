#!/bin/bash

# Zest .pkg Installer Creator
# Creates a signed macOS installer package

set -e

echo "🍋 Creating Zest installer package..."

# Configuration
VERSION="1.0.0"
APP_NAME="Zest"
IDENTIFIER="com.spicylemonade.zest"
INSTALL_LOCATION="/Applications"
DIST_DIR="./dist"
PKG_DIR="./pkg"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"

# Check if app bundle exists
if [ ! -d "$APP_BUNDLE" ]; then
    echo "❌ Error: App bundle not found at $APP_BUNDLE"
    echo "Please run ./build.sh first"
    exit 1
fi

# Create package directory structure
echo "📁 Creating package structure..."
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/root/Applications"
mkdir -p "$PKG_DIR/scripts"

# Copy app bundle to package root
echo "📋 Copying app bundle..."
cp -R "$APP_BUNDLE" "$PKG_DIR/root/Applications/"

# Create postinstall script
echo "📝 Creating postinstall script..."
cat > "$PKG_DIR/scripts/postinstall" << 'EOF'
#!/bin/bash

# Zest Post-Install Script
# Sets up symlinks and shell aliases

# Create symlink in /usr/local/bin
ln -sf /Applications/Zest.app/Contents/MacOS/zest /usr/local/bin/zest

# Get the user who invoked the installer (not root)
REAL_USER="${USER}"
if [ "$REAL_USER" == "root" ]; then
    REAL_USER=$(stat -f "%Su" /dev/console)
fi

USER_HOME=$(eval echo ~$REAL_USER)

# Function to add alias to shell config
add_alias_to_shell() {
    local shell_config="$1"

    if [ -f "$shell_config" ]; then
        # Check if alias already exists
        if ! grep -q "alias zest=" "$shell_config"; then
            echo "" >> "$shell_config"
            echo "# Zest CLI aliases" >> "$shell_config"
            echo "alias zest='noglob zest'" >> "$shell_config"
            echo "alias Zest='zest'" >> "$shell_config"
        fi
    else
        # Create the file if it doesn't exist
        touch "$shell_config"
        echo "# Zest CLI aliases" >> "$shell_config"
        echo "alias zest='noglob zest'" >> "$shell_config"
        echo "alias Zest='zest'" >> "$shell_config"
    fi
}

# Add aliases to shell configs
add_alias_to_shell "$USER_HOME/.zshrc"
add_alias_to_shell "$USER_HOME/.bashrc"

# Fix ownership of modified files
chown "$REAL_USER" "$USER_HOME/.zshrc" 2>/dev/null || true
chown "$REAL_USER" "$USER_HOME/.bashrc" 2>/dev/null || true

echo "✅ Zest installed successfully!"
echo "Open a new terminal and type 'zest' to get started"

exit 0
EOF

chmod +x "$PKG_DIR/scripts/postinstall"

# Build the component package
echo "📦 Building component package..."
pkgbuild \
    --root "$PKG_DIR/root" \
    --scripts "$PKG_DIR/scripts" \
    --identifier "$IDENTIFIER" \
    --version "$VERSION" \
    --install-location "$INSTALL_LOCATION" \
    "$PKG_DIR/Zest-component.pkg"

# Create Distribution XML for product archive
echo "📝 Creating distribution.xml..."
cat > "$PKG_DIR/distribution.xml" << EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="1">
    <title>Zest</title>
    <organization>com.spicylemonade</organization>
    <domains enable_localSystem="true"/>
    <options customize="never" require-scripts="false" hostArchitectures="x86_64,arm64"/>

    <welcome file="welcome.html" mime-type="text/html"/>
    <license file="license.txt"/>
    <conclusion file="conclusion.html" mime-type="text/html"/>

    <pkg-ref id="$IDENTIFIER">
        <bundle-version>
            <bundle id="$IDENTIFIER" CFBundleVersion="$VERSION" path="$INSTALL_LOCATION/$APP_NAME.app"/>
        </bundle-version>
    </pkg-ref>

    <choices-outline>
        <line choice="default">
            <line choice="$IDENTIFIER"/>
        </line>
    </choices-outline>

    <choice id="default"/>
    <choice id="$IDENTIFIER" visible="false">
        <pkg-ref id="$IDENTIFIER"/>
    </choice>

    <pkg-ref id="$IDENTIFIER" version="$VERSION" auth="root">Zest-component.pkg</pkg-ref>
</installer-gui-script>
EOF

# Create welcome message
cat > "$PKG_DIR/welcome.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        h1 { color: #FF6B35; }
    </style>
</head>
<body>
    <h1>🍋 Welcome to Zest</h1>
    <p>Transform natural language into CLI commands with a locally-running AI model.</p>
    <p><strong>Features:</strong></p>
    <ul>
        <li>Runs completely offline on your Mac</li>
        <li>No cloud, no API keys, no tracking</li>
        <li>GPU acceleration with Apple Metal</li>
        <li>Privacy-first design</li>
    </ul>
</body>
</html>
EOF

# Create license file
cat > "$PKG_DIR/license.txt" << 'EOF'
ZEST END USER LICENSE AGREEMENT

Copyright (c) 2025 Spicy Lemonade

This software is licensed, not sold. By installing Zest, you agree to the following terms:

1. LICENSE GRANT
   Subject to payment and compliance with these terms, Spicy Lemonade grants you a
   non-exclusive, non-transferable license to use Zest on up to 2 devices.

2. RESTRICTIONS
   You may not:
   - Reverse engineer, decompile, or disassemble the software
   - Share your license with others
   - Use the software on more than 2 devices simultaneously
   - Remove or modify any copyright notices

3. PRIVACY
   Zest runs entirely offline. No data is collected or transmitted except for:
   - License activation and validation
   - Anonymous usage analytics (if enabled)

4. DISCLAIMER
   This software is provided "as is" without warranty of any kind.

For full terms, visit: https://spicylemonade.com/terms
EOF

# Create conclusion message
cat > "$PKG_DIR/conclusion.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        h1 { color: #4CAF50; }
        code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }
    </style>
</head>
<body>
    <h1>✅ Installation Complete!</h1>
    <p>Zest has been installed successfully.</p>

    <h2>Getting Started</h2>
    <ol>
        <li>Open Terminal</li>
        <li>Type <code>zest "your command here"</code></li>
        <li>Follow the activation prompts</li>
    </ol>

    <h2>Example Usage</h2>
    <pre><code>zest "find all python files modified in the last 7 days"
zest "compress the logs directory into logs.tar.gz"
zest "show me the 10 largest files in my Downloads folder"</code></pre>

    <p>For help, visit: <a href="https://spicylemonade.com/docs">https://spicylemonade.com/docs</a></p>
</body>
</html>
EOF

# Build the final product archive
echo "🎁 Building product archive..."
productbuild \
    --distribution "$PKG_DIR/distribution.xml" \
    --package-path "$PKG_DIR" \
    --resources "$PKG_DIR" \
    "$DIST_DIR/Zest-$VERSION.pkg"

# Optional: Sign the installer (requires Developer ID Installer certificate)
# Uncomment and configure:
# echo "✍️  Signing installer..."
# productsign \
#     --sign "Developer ID Installer: Your Name (TEAM_ID)" \
#     "$DIST_DIR/Zest-$VERSION.pkg" \
#     "$DIST_DIR/Zest-$VERSION-signed.pkg"
# mv "$DIST_DIR/Zest-$VERSION-signed.pkg" "$DIST_DIR/Zest-$VERSION.pkg"

echo "✅ Installer created successfully!"
echo ""
echo "📦 Installer: $DIST_DIR/Zest-$VERSION.pkg"
echo ""
echo "Next steps:"
echo "1. Test: sudo installer -pkg $DIST_DIR/Zest-$VERSION.pkg -target /"
echo "2. Sign with Developer ID Installer certificate"
echo "3. Notarize with Apple: xcrun notarytool submit ..."
echo "4. Staple notarization: xcrun stapler staple ..."
