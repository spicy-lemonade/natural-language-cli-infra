#!/bin/bash

# Zest CLI Post-Install Script
# Run this after dragging Zest.app to Applications

set -e

echo "🍋 Zest CLI Installer"
echo "====================="
echo ""

APP_PATH="/Applications/Zest.app"
MODEL_NAME="qwen3_4b_Q5_K_M.gguf"
ZEST_DIR="$HOME/.zest"

# Check if Zest.app exists
if [ ! -d "$APP_PATH" ]; then
    echo "❌ Zest.app not found in /Applications"
    echo "   Please drag Zest.app to Applications first."
    exit 1
fi

# Create ~/.zest directory
echo "📁 Creating Zest directory..."
mkdir -p "$ZEST_DIR"

# Copy model to ~/.zest if not already there
MODEL_SRC="$APP_PATH/Contents/Resources/$MODEL_NAME"
MODEL_DEST="$ZEST_DIR/$MODEL_NAME"

if [ ! -f "$MODEL_DEST" ]; then
    if [ -f "$MODEL_SRC" ]; then
        echo "📦 Copying model (this may take a moment)..."
        cp "$MODEL_SRC" "$MODEL_DEST"
        echo "✅ Model installed"
    else
        echo "⚠️  Model not found in app bundle"
        echo "   You may need to download it separately."
    fi
else
    echo "✅ Model already installed"
fi

# Create symlink in /usr/local/bin (requires sudo)
echo ""
echo "📎 Setting up command-line access..."

if [ -w /usr/local/bin ]; then
    ln -sf "$APP_PATH/Contents/MacOS/zest-launcher" /usr/local/bin/zest
    echo "✅ Created symlink: /usr/local/bin/zest"
else
    echo "   Creating symlink requires administrator privileges."
    sudo ln -sf "$APP_PATH/Contents/MacOS/zest-launcher" /usr/local/bin/zest
    echo "✅ Created symlink: /usr/local/bin/zest"
fi

# Detect shell and add alias
SHELL_NAME=$(basename "$SHELL")
SHELL_RC=""

case "$SHELL_NAME" in
    zsh)
        SHELL_RC="$HOME/.zshrc"
        ;;
    bash)
        if [ -f "$HOME/.bash_profile" ]; then
            SHELL_RC="$HOME/.bash_profile"
        else
            SHELL_RC="$HOME/.bashrc"
        fi
        ;;
esac

if [ -n "$SHELL_RC" ]; then
    echo ""
    echo "📝 Setting up shell aliases..."

    # Check if alias already exists
    if grep -q "alias zest=" "$SHELL_RC" 2>/dev/null; then
        echo "✅ Alias already configured in $SHELL_RC"
    else
        echo "" >> "$SHELL_RC"
        echo "# Zest CLI - Natural language to CLI commands" >> "$SHELL_RC"
        echo "alias zest='noglob zest'" >> "$SHELL_RC"
        echo "✅ Added alias to $SHELL_RC"
    fi
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "Getting started:"
echo "  1. Open a new terminal window"
echo "  2. Run: zest \"your query here\""
echo "  3. Enter your purchase email when prompted"
echo ""
echo "Examples:"
echo "  zest \"find all python files modified today\""
echo "  zest \"show disk usage by folder\""
echo "  zest \"list all running processes\""
echo ""
