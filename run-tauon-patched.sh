#!/bin/bash
# Run patched Tauon from source with AI playlist improvements

cd /Users/ahsan/Documents/GitHub/Tauon-AI-playlists

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set Python path to use our patched modules
export PYTHONPATH="$PWD/src:$PYTHONPATH"

# Run Tauon
echo "Starting Tauon with AI Playlist improvements..."
python3 -m tauon "$@"
