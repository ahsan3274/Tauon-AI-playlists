#!/bin/bash
# Download Open-Source Icon Packs for Tauon AI
#━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Downloads and installs icon packs from:
# - Feather Icons (MIT) - https://feathericons.com
# - Tabler Icons (MIT) - https://tabler-icons.io
# - Material Design Icons (Apache 2.0) - https://materialdesignicons.com
#
# All icons are free for commercial use.

set -e

ICON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/src/tauon/t_modules/assets/icons"

echo "🎨 Tauon AI Icon Pack Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Installing icons to: $ICON_DIR"
echo ""

# Create icon directory
mkdir -p "$ICON_DIR"

# Download Feather Icons (MIT License)
echo "⬇️  Downloading Feather Icons (MIT)..."
FEATHER_URL="https://github.com/feathericons/feather/archive/refs/heads/master.zip"
FEATHER_ZIP="/tmp/feather-icons.zip"

curl -L -o "$FEATHER_ZIP" "$FEATHER_URL" 2>/dev/null || wget -q -O "$FEATHER_ZIP" "$FEATHER_URL"

if [ -f "$FEATHER_ZIP" ]; then
    echo "   Extracting Feather Icons..."
    unzip -q -o "$FEATHER_ZIP" -d /tmp/
    cp /tmp/feather-master/icons/*.svg "$ICON_DIR/feather/" 2>/dev/null || mkdir -p "$ICON_DIR/feather" && cp /tmp/feather-master/icons/*.svg "$ICON_DIR/feather/"
    rm "$FEATHER_ZIP"
    rm -rf /tmp/feather-master
    echo "   ✅ Feather Icons installed ($(ls -1 "$ICON_DIR/feather/"*.svg 2>/dev/null | wc -l | tr -d ' ') icons)"
else
    echo "   ❌ Failed to download Feather Icons"
fi

echo ""

# Download Tabler Icons (MIT License)
echo "⬇️  Downloading Tabler Icons (MIT)..."
TABLER_URL="https://github.com/tabler/tabler-icons/archive/refs/heads/master.zip"
TABLER_ZIP="/tmp/tabler-icons.zip"

curl -L -o "$TABLER_ZIP" "$TABLER_URL" 2>/dev/null || wget -q -O "$TABLER_ZIP" "$TABLER_URL"

if [ -f "$TABLER_ZIP" ]; then
    echo "   Extracting Tabler Icons..."
    unzip -q -o "$TABLER_ZIP" -d /tmp/
    find /tmp/tabler-icons-master/icons -name "*.svg" -exec cp {} "$ICON_DIR/tabler/" \; 2>/dev/null || mkdir -p "$ICON_DIR/tabler" && find /tmp/tabler-icons-master/icons -name "*.svg" -exec cp {} "$ICON_DIR/tabler/" \;
    rm "$TABLER_ZIP"
    rm -rf /tmp/tabler-icons-master
    echo "   ✅ Tabler Icons installed ($(ls -1 "$ICON_DIR/tabler/"*.svg 2>/dev/null | wc -l | tr -d ' ') icons)"
else
    echo "   ❌ Failed to download Tabler Icons"
fi

echo ""

# Create symlinks for commonly used icons
echo "🔗 Creating icon symlinks..."
cd "$ICON_DIR"

# Feather icons we need
for icon in radio user heart zap grid calendar bar-chart-2 pie-chart settings info plus search upload download clock music smile moon cloud coffee flame star; do
    if [ -f "feather/${icon}.svg" ]; then
        ln -sf "feather/${icon}.svg" "${icon}.svg" 2>/dev/null || true
    fi
done

echo "   ✅ Symlinks created"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ Icon installation complete!"
echo ""
echo "Installed icons:"
echo "  • Feather Icons: $(ls -1 "$ICON_DIR/feather/"*.svg 2>/dev/null | wc -l | tr -d ' ')"
echo "  • Tabler Icons: $(ls -1 "$ICON_DIR/tabler/"*.svg 2>/dev/null | wc -l | tr -d ' ')"
echo ""
echo "Location: $ICON_DIR"
echo ""
echo "To use icons in code:"
echo "  from t_icon_loader import load_icon"
echo "  icon_svg = load_icon('radio', size='medium', color='#007AFF')"
echo ""
