#!/bin/bash

# Zest DMG Build Script
# Creates a distributable DMG containing the Zest CLI and model
# Usage: ./build_dmg.sh [fp16|q5]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_DIR/build"
DIST_DIR="$PROJECT_DIR/dist"

# This version MUST match the VERSION constant in main.py
VERSION="1.0.0"
APP_NAME="Zest"
BUNDLE_ID="com.zestcli.zest"
GCS_BUCKET="nlcli-models"

# Verify version matches main.py
MAIN_PY_VERSION=$(grep -m1 'VERSION = "' "$PROJECT_DIR/main.py" | sed 's/.*VERSION = "\([^"]*\)".*/\1/')
if [ "$VERSION" != "$MAIN_PY_VERSION" ]; then
    echo "❌ Version mismatch!"
    echo "   build_dmg.sh: $VERSION"
    echo "   main.py: $MAIN_PY_VERSION"
    echo "   Please update VERSION in both files to match."
    exit 1
fi

# Product configuration
PRODUCT="${1:-q5}"
case "$PRODUCT" in
    fp16|fp)
        PRODUCT="fp16"
        MODEL_NAME="qwen3_4b_fp16.gguf"
        PRODUCT_SUFFIX="-FP16"
        ;;
    q5)
        MODEL_NAME="qwen3_4b_Q5_K_M.gguf"
        PRODUCT_SUFFIX="-Q5"
        ;;
    *)
        echo "Usage: $0 [fp16|q5]"
        echo "  fp16  - Build DMG with full precision model (~8GB)"
        echo "  q5    - Build DMG with quantized model (~3GB)"
        exit 1
        ;;
esac

echo "🍋 Zest DMG Build Script v$VERSION"
echo "=================================="
echo "Building: $APP_NAME$PRODUCT_SUFFIX"
echo "Model: $MODEL_NAME"
echo ""

# Clean previous builds for this product
echo "🧹 Cleaning previous builds..."
rm -rf "$BUILD_DIR" "$DIST_DIR/${APP_NAME}${PRODUCT_SUFFIX}"*
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Check for required tools
echo "🔍 Checking dependencies..."
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 required"; exit 1; }
command -v pip3 >/dev/null 2>&1 || { echo "❌ pip3 required"; exit 1; }

# Create virtual environment for build
echo "📦 Setting up build environment..."
python3 -m venv "$BUILD_DIR/venv"
source "$BUILD_DIR/venv/bin/activate"

# Install dependencies
pip install --upgrade pip
pip install pyinstaller
pip install -r "$PROJECT_DIR/requirements.txt"

# Download model from GCS if not present locally
MODEL_PATH="$BUILD_DIR/$MODEL_NAME"
if [ ! -f "$MODEL_PATH" ]; then
    echo "📥 Downloading model from GCS (this may take a while)..."
    if command -v gsutil >/dev/null 2>&1; then
        gsutil cp "gs://$GCS_BUCKET/$MODEL_NAME" "$MODEL_PATH"
    else
        echo "⚠️  gsutil not found. Trying public URL..."
        curl -L --progress-bar -o "$MODEL_PATH" \
            "https://storage.googleapis.com/$GCS_BUCKET/$MODEL_NAME" || {
            echo "❌ Failed to download model."
            echo "   Install gsutil: pip install gsutil"
            echo "   Or ensure the bucket is publicly accessible."
            exit 1
        }
    fi
fi

echo "✅ Model ready: $(du -h "$MODEL_PATH" | cut -f1)"

# Build executable with PyInstaller
echo "🔨 Building executable..."
cd "$PROJECT_DIR"
pyinstaller \
    --name="zest" \
    --onefile \
    --console \
    --distpath="$BUILD_DIR/pyinstaller_dist" \
    --workpath="$BUILD_DIR/pyinstaller_work" \
    --specpath="$BUILD_DIR" \
    --hidden-import=llama_cpp \
    --hidden-import=requests \
    --hidden-import=json \
    --collect-all llama_cpp \
    main.py

# Create app bundle structure
echo "📁 Creating app bundle..."
APP_BUNDLE="$DIST_DIR/${APP_NAME}${PRODUCT_SUFFIX}.app"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

# Copy executable
cp "$BUILD_DIR/pyinstaller_dist/zest" "$APP_BUNDLE/Contents/MacOS/zest"
chmod +x "$APP_BUNDLE/Contents/MacOS/zest"

# Copy model
echo "📦 Copying model to bundle..."
cp "$MODEL_PATH" "$APP_BUNDLE/Contents/Resources/$MODEL_NAME"

# Copy icon if exists
if [ -f "$PROJECT_DIR/resources/icon.icns" ]; then
    cp "$PROJECT_DIR/resources/icon.icns" "$APP_BUNDLE/Contents/Resources/AppIcon.icns"
fi

# Copy license
if [ -f "$PROJECT_DIR/resources/MODEL_LICENSE.txt" ]; then
    cp "$PROJECT_DIR/resources/MODEL_LICENSE.txt" "$APP_BUNDLE/Contents/Resources/"
fi

# Create Info.plist
cat > "$APP_BUNDLE/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>zest-launcher</string>
    <key>CFBundleIdentifier</key>
    <string>${BUNDLE_ID}.${PRODUCT}</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}${PRODUCT_SUFFIX}</string>
    <key>CFBundleDisplayName</key>
    <string>${APP_NAME} ${PRODUCT_SUFFIX}</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>ZEST</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.developer-tools</string>
    <key>ZestProduct</key>
    <string>$PRODUCT</string>
</dict>
</plist>
EOF

# Create launcher script
cat > "$APP_BUNDLE/Contents/MacOS/zest-launcher" << LAUNCHER
#!/bin/bash
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
RESOURCES_DIR="\$(dirname "\$SCRIPT_DIR")/Resources"
MODEL_SRC="\$RESOURCES_DIR/$MODEL_NAME"
MODEL_DEST="\$HOME/.zest/$MODEL_NAME"

# Ensure model is in place
if [ ! -f "\$MODEL_DEST" ]; then
    mkdir -p "\$HOME/.zest"
    echo "🍋 Installing Zest model (first run only)..."
    cp "\$MODEL_SRC" "\$MODEL_DEST"
    echo "✅ Model installed."
fi

# Run the CLI
exec "\$SCRIPT_DIR/zest" "\$@"
LAUNCHER
chmod +x "$APP_BUNDLE/Contents/MacOS/zest-launcher"

# Code signing (optional)
if [ -n "$APPLE_SIGNING_IDENTITY" ]; then
    echo "✍️  Signing app bundle..."
    codesign --deep --force --verify --verbose \
        --sign "$APPLE_SIGNING_IDENTITY" \
        --options runtime \
        "$APP_BUNDLE"
fi

# Create DMG staging directory
echo "📀 Creating DMG..."
DMG_STAGING="$BUILD_DIR/dmg_staging"
mkdir -p "$DMG_STAGING"

# Copy app bundle
cp -R "$APP_BUNDLE" "$DMG_STAGING/"

# Create Applications symlink
ln -s /Applications "$DMG_STAGING/Applications"

# Copy documentation
cp "$PROJECT_DIR/resources/MODEL_LICENSE.txt" "$DMG_STAGING/" 2>/dev/null || true
cp "$PROJECT_DIR/resources/README_INSTALL.txt" "$DMG_STAGING/" 2>/dev/null || true

# Create DMG
DMG_NAME="${APP_NAME}${PRODUCT_SUFFIX}-${VERSION}.dmg"
DMG_PATH="$DIST_DIR/$DMG_NAME"

hdiutil create \
    -volname "${APP_NAME} ${PRODUCT_SUFFIX} ${VERSION}" \
    -srcfolder "$DMG_STAGING" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

# Notarization (optional)
if [ -n "$APPLE_ID" ] && [ -n "$APPLE_TEAM_ID" ]; then
    echo "📝 Notarizing DMG..."
    xcrun notarytool submit "$DMG_PATH" \
        --apple-id "$APPLE_ID" \
        --team-id "$APPLE_TEAM_ID" \
        --password "@keychain:AC_PASSWORD" \
        --wait
    xcrun stapler staple "$DMG_PATH"
fi

# Cleanup
deactivate
echo ""
echo "=============================================="
echo "✅ Build complete!"
echo "=============================================="
echo ""
echo "📦 DMG: $DMG_PATH"
echo "📏 Size: $(du -h "$DMG_PATH" | cut -f1)"
echo ""
echo "To build the other model, run:"
if [ "$PRODUCT" = "fp16" ]; then
    echo "  ./build_dmg.sh q5"
else
    echo "  ./build_dmg.sh fp16"
fi
echo ""
echo "Next steps:"
echo "1. Test the DMG by mounting and installing"
echo "2. Upload to Polar for distribution"
