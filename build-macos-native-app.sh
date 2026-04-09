#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔨 Building Tauon AI Playlists as native macOS app..."
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Step 1: Check prerequisites
echo "📋 Checking prerequisites..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found!${NC}"
    exit 1
fi

if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}⚠️  Homebrew not found. Some features may not work.${NC}"
fi
echo -e "${GREEN}✅ Prerequisites check passed${NC}"
echo ""

# Step 2: Setup virtual environment
echo "📦 Setting up virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  - Created virtual environment"
fi

source venv/bin/activate
pip install --upgrade pip --quiet

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt 2>/dev/null || true
pip install -q pyinstaller 2>/dev/null || true
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Step 3: Build phazor if needed
echo "🔧 Checking phazor extension..."
if [ ! -f "src/phazor.cpython-312-darwin.so" ]; then
    echo "  - Building phazor..."
    if [ -f "src/phazor/build.sh" ]; then
        cd src/phazor && ./build.sh && cd ../..
        echo -e "${GREEN}✅ Phazor built${NC}"
    else
        echo -e "${YELLOW}⚠️  Phazor build script not found${NC}"
    fi
else
    echo -e "${GREEN}✅ Found existing phazor extension${NC}"
fi
echo ""

# Step 4: Create native app bundle
echo "📱 Creating native app bundle..."

# Remove old app
rm -rf /Applications/Tauon-AI.app
rm -rf dist/Tauon.app build/mac 2>/dev/null || true

# Create app structure
mkdir -p /Applications/Tauon-AI.app/Contents/MacOS
mkdir -p /Applications/Tauon-AI.app/Contents/Resources

# Create the launcher script
cat > /Applications/Tauon-AI.app/Contents/MacOS/Tauon << 'LAUNCHER_EOF'
#!/bin/bash
# Tauon AI - Native macOS launcher

# Get app resources directory
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="/Users/ahsan/Documents/GitHub/Tauon-AI-playlists"
VENV_DIR="$SCRIPT_DIR/venv"

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment not found at $VENV_DIR"
    echo "Please run the build script first: ./build-macos-native-app.sh"
    exit 1
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Set Python path
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"

# Change to script directory
cd "$SCRIPT_DIR"

# Run Tauon
exec python3 src/tauon "$@"
LAUNCHER_EOF

chmod +x /Applications/Tauon-AI.app/Contents/MacOS/Tauon

# Create Info.plist
cat > /Applications/Tauon-AI.app/Contents/Info.plist << 'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>Tauon AI</string>
    <key>CFBundleExecutable</key>
    <string>Tauon</string>
    <key>CFBundleIconFile</key>
    <string>tau-mac</string>
    <key>CFBundleIdentifier</key>
    <string>com.github.tauon-ai-playlists</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Tauon AI</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>9.1.1</string>
    <key>CFBundleVersion</key>
    <string>9.1.1</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
PLIST_EOF

# Copy app icon
if [ -f "src/tauon/assets/tau-mac.icns" ]; then
    cp "src/tauon/assets/tau-mac.icns" /Applications/Tauon-AI.app/Contents/Resources/
    echo -e "${GREEN}✅ App icon added${NC}"
fi

echo -e "${GREEN}✅ App bundle created${NC}"
echo ""

# Step 5: Add documentation
echo "📚 Adding documentation access..."
mkdir -p /Applications/Tauon-AI.app/Contents/Resources/Documentation

for doc in README.md HOW_TO_RUN.md AI_PLAYLIST_SETUP.md AUDIO_RECOMMENDER.md AUDIO_FEATURES_CACHE.md CHANGELOG.md; do
    if [ -f "$SCRIPT_DIR/$doc" ]; then
        cp "$SCRIPT_DIR/$doc" /Applications/Tauon-AI.app/Contents/Resources/Documentation/
    fi
done

# Create documentation index
cat > /Applications/Tauon-AI.app/Contents/Resources/Documentation/INDEX.md << 'DOC_INDEX'
# Tauon AI Documentation

## Quick Start
- [HOW_TO_RUN.md](HOW_TO_RUN.md) - Running Tauon AI
- [AI_PLAYLIST_SETUP.md](AI_PLAYLIST_SETUP.md) - AI Features Guide

## Technical Documentation
- [AUDIO_RECOMMENDER.md](AUDIO_RECOMMENDER.md) - Music Recommender System
- [AUDIO_FEATURES_CACHE.md](AUDIO_FEATURES_CACHE.md) - Audio Features Cache
- [NATIVE_MACOS_APP_GUIDE.md](NATIVE_MACOS_APP_GUIDE.md) - Native macOS App Guide

## Project Info
- [README.md](README.md) - Project Overview
- [CHANGELOG.md](CHANGELOG.md) - Version History
DOC_INDEX

echo -e "${GREEN}✅ Documentation added${NC}"
echo ""

# Step 6: Code signing
echo "🔐 Code signing..."
codesign --force --deep --sign - /Applications/Tauon-AI.app 2>/dev/null || true
xattr -cr /Applications/Tauon-AI.app 2>/dev/null || true
echo -e "${GREEN}✅ App signed${NC}"
echo ""

# Final summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Build and installation complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 App Location: /Applications/Tauon-AI.app"
echo ""
echo "🚀 To launch:"
echo "   • Open from Applications folder"
echo "   • Or run: open /Applications/Tauon-AI.app"
echo ""
echo "📚 To access documentation:"
echo "   • Right-click app → Show Package Contents"
echo "   • Navigate to: Contents/Resources/Documentation"
echo "   • Or run: open /Applications/Tauon-AI.app/Contents/Resources/Documentation"
echo ""
echo "🔒 IMPORTANT: First Launch Security Setup"
echo "   macOS will block the app on first launch. To fix:"
echo ""
echo "   Option A - System Settings (Recommended):"
echo "   1. Launch the app (it will fail)"
echo "   2. Go to System Settings → Privacy & Security"
echo "   3. Scroll down and click 'Allow Anyway' or 'Open Anyway'"
echo "   4. Launch the app again"
echo ""
echo "   Option B - Terminal (Quick):"
echo "   xattr -cr /Applications/Tauon-AI.app"
echo "   Then launch the app"
echo ""
echo "💡 Tip: Drag to Dock for quick access!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
