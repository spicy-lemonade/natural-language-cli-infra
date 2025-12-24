#!/bin/bash

# Zest macOS Build Script
# This script packages Zest into a macOS .app bundle using PyInstaller

set -e  # Exit on any error

echo "🍋 Starting Zest build process..."

# Configuration
VERSION="1.0.0"
APP_NAME="Zest"
MODEL_FILE="$HOME/.zest/gemma3_4b_Q4_K_M.gguf"
BUILD_DIR="./build"
DIST_DIR="./dist"

# Check if model exists
if [ ! -f "$MODEL_FILE" ]; then
    echo "❌ Error: Model file not found at $MODEL_FILE"
    echo "Please download the model first."
    exit 1
fi

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf "$BUILD_DIR" "$DIST_DIR"

# Install PyInstaller if not already installed
echo "📦 Checking PyInstaller..."
pip install pyinstaller

# Create the executable with PyInstaller
echo "🔨 Building executable with PyInstaller..."
pyinstaller \
    --name="zest" \
    --onefile \
    --windowed \
    --add-data "$MODEL_FILE:models" \
    --hidden-import=llama_cpp \
    --hidden-import=requests \
    --hidden-import=sqlite3 \
    --hidden-import=json \
    --collect-all llama_cpp \
    main.py

echo "✅ Executable built successfully"

# Create App Bundle structure
echo "📁 Creating App Bundle structure..."
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources/models"
mkdir -p "$APP_BUNDLE/Contents/Frameworks"

# Move the executable
echo "📋 Moving executable..."
mv "$DIST_DIR/zest" "$APP_BUNDLE/Contents/MacOS/zest"
chmod +x "$APP_BUNDLE/Contents/MacOS/zest"

# Copy model to Resources
echo "📋 Copying model..."
cp "$MODEL_FILE" "$APP_BUNDLE/Contents/Resources/models/"

# Create Info.plist
echo "📝 Creating Info.plist..."
cat > "$APP_BUNDLE/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>zest</string>
    <key>CFBundleIdentifier</key>
    <string>com.spicylemonade.zest</string>
    <key>CFBundleName</key>
    <string>Zest</string>
    <key>CFBundleDisplayName</key>
    <string>Zest</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>ZEST</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>LSEnvironment</key>
    <dict>
        <key>MODEL_PATH</key>
        <string>Contents/Resources/models/gemma3_4b_Q4_K_M.gguf</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ App Bundle created at: $APP_BUNDLE"

# Optional: Code signing (requires Developer ID)
# Uncomment and configure with your signing identity:
# echo "✍️  Signing app bundle..."
# codesign --deep --force --verify --verbose \
#     --sign "Developer ID Application: Your Name (TEAM_ID)" \
#     --options runtime \
#     "$APP_BUNDLE"

echo "🎉 Build complete!"
echo ""
echo "Next steps:"
echo "1. Test the app: open $APP_BUNDLE"
echo "2. Create installer: ./create_installer.sh"
echo "3. Sign and notarize for distribution"
