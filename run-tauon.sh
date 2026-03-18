#!/bin/bash
# Tauon Music Box - AI Playlist Generator Edition
# Launch script for running from source on macOS

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Set environment variables
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"

# Launch Tauon
echo "Starting Tauon Music Box with AI Playlist Generator..."
python3 -m tauon "$@"
