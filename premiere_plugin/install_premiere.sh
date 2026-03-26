#!/usr/bin/env bash
# Install Vit CEP extension for Adobe Premiere Pro.
# Creates a symlink in the CEP extensions directory.

set -euo pipefail

EXTENSION_ID="com.vit.premiere"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Determine CEP extensions directory based on platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    CEP_DIR="$HOME/Library/Application Support/Adobe/CEP/extensions"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CEP_DIR="$HOME/.local/share/Adobe/CEP/extensions"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    CEP_DIR="$APPDATA/Adobe/CEP/extensions"
else
    echo "Unsupported platform: $OSTYPE"
    exit 1
fi

TARGET="$CEP_DIR/$EXTENSION_ID"

# Create extensions directory if needed
mkdir -p "$CEP_DIR"

# Remove existing symlink or directory
if [ -L "$TARGET" ]; then
    rm "$TARGET"
    echo "Removed existing symlink."
elif [ -d "$TARGET" ]; then
    echo "Warning: $TARGET exists and is a directory. Remove it manually."
    exit 1
fi

# Create symlink
ln -s "$SCRIPT_DIR" "$TARGET"
echo "Symlinked: $TARGET -> $SCRIPT_DIR"

# Enable unsigned extensions for development (PlayerDebugMode)
if [[ "$OSTYPE" == "darwin"* ]]; then
    defaults write com.adobe.CSXS.9 PlayerDebugMode 1
    defaults write com.adobe.CSXS.10 PlayerDebugMode 1
    defaults write com.adobe.CSXS.11 PlayerDebugMode 1
    echo "Enabled PlayerDebugMode for CSXS 9/10/11."
fi

echo ""
echo "Installation complete. Restart Premiere Pro, then open:"
echo "  Window > Extensions > Vit"
