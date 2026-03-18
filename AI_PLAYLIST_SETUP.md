# Tauon AI Playlist Generator - Setup Complete ✅

## What Was Implemented

### 1. AI Playlist Generator Integration
- **Last.fm Radio** - Generate playlists based on similar artists
- **AI Mood Playlists** - Cluster your library into mood-based playlists using LLM
- **Audio Feature Clusters** - Offline clustering by BPM and spectral features

### 2. Local LLM Support
- **LM Studio** support (default: `http://localhost:1234/v1/chat/completions`)
- **Ollama** support (`http://localhost:11434/v1/chat/completions`)
- Toggle between Claude API and local LLM in settings

### 3. Settings UI
Located at: **Menu → Settings → Accounts → Playlist Generator**

Configuration options:
- Last.fm Gen API Key
- Seed Artist (optional, defaults to currently playing artist)
- Last.fm Track Limit (default: 60)
- Anthropic API Key (for Claude)
- **Use Local LLM** toggle
- Local LLM URL
- Model Name (optional)

## Running Tauon

### Option 1: Using the Launcher Script
```bash
cd /Users/ahsan/Documents/GitHub/Tauon-AI-playlists
./run-tauon.sh
```

### Option 2: Manual Command
```bash
cd /Users/ahsan/Documents/GitHub/Tauon-AI-playlists
source venv/bin/activate
export PYTHONPATH="$PWD/src:$PYTHONPATH"
python3 -m tauon
```

## Using the AI Playlist Generator

### Last.fm Radio
1. Get a Last.fm API key from https://www.last.fm/api/account/create
2. In Tauon: Settings → Accounts → enter your API key
3. Right-click any playlist tab → "↯ Last.fm Radio (current artist)"
4. Or set a seed artist in settings

### AI Mood Playlists (Local LLM)
1. Start LM Studio and load a model
2. In Tauon: Settings → Accounts → enable "Use Local LLM"
3. Verify the URL matches your LM Studio setup
4. Right-click playlist tab → "✦ AI Mood Playlists (Claude/Local)"
5. Choose number of moods in settings (default: 6)

### AI Mood Playlists (Claude API)
1. Get Anthropic API key from https://console.anthropic.com/
2. In Tauon: Settings → Accounts → enter API key
3. Disable "Use Local LLM" toggle
4. Right-click playlist tab → "✦ AI Mood Playlists (Claude/Local)"

### Audio Feature Clusters
- No API key required - works completely offline
- Analyzes BPM, spectral centroid, energy, etc.
- Right-click playlist tab → "⊕ Audio Feature Clusters"
- Note: Can be slow (~2-5 seconds per track)

## Files Modified

```
src/tauon/t_modules/
├── t_playlist_gen.py    (new - AI playlist generator)
├── t_main.py            (modified - added menu items and settings UI)
└── t_prefs.py           (modified - added preference fields)
```

## Dependencies Installed

Core dependencies in virtual environment:
- PyGObject (GTK3)
- PySDL3
- requests
- beautifulsoup4
- mutagen
- musicbrainzngs
- pylast
- Pillow
- PyInstaller

System dependencies (via Homebrew):
- gtk+3
- sdl3
- sdl3_image
- gobject-introspection
- py3cairo

## Troubleshooting

### App crashes on startup
Make sure GTK3 is installed:
```bash
brew install gtk+3
```

### Missing module errors
Activate the virtual environment and install:
```bash
cd /Users/ahsan/Documents/GitHub/Tauon-AI-playlists
source venv/bin/activate
pip install -r requirements.txt
```

### Local LLM not connecting
1. Ensure LM Studio server is running
2. Check the URL in Settings matches your LM Studio setup
3. Test with: `curl http://localhost:1234/v1/models`

### Last.fm errors
- Verify API key is correct
- Check network connection
- Some features require a Last.fm account

## Notes

- Running from source (not bundled app) due to macOS code signing complexities
- All your existing Tauon data is preserved in `~/.local/share/TauonMusicBox/`
- The bundled app in `/Applications/Tauon.app` is the original version (v9.1.1)
- AI playlist features create new playlist tabs - they don't modify existing playlists
