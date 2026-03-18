#!/bin/bash
# Run Tauon AI Playlists from source
# Uses patched modules with privacy-first features

set -e

REPO_DIR="/Users/ahsan/Documents/GitHub/Tauon-AI-playlists"
SRC_DIR="$REPO_DIR/src"

cd "$REPO_DIR"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set Python path
export PYTHONPATH="$SRC_DIR:$PYTHONPATH"

echo "🚀 Starting Tauon AI Playlists..."
echo ""
echo "✨ Privacy-first features:"
echo "  • Autoplay: 100% offline library matching"
echo "  • Audio Clustering: Metadata/librosa only (no Spotify)"
echo "  • Zero external API calls for playlist generation"
echo ""

# Run Tauon from source
python3 -m tauon "$@"
