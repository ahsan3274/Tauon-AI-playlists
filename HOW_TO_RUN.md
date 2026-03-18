# 🚀 How to Run Tauon AI (Privacy-First Build)

## ⚠️ IMPORTANT: macOS App Bundling Issue

The PyInstaller-built app has library conflicts on macOS (`libharfbuzz` vs `libpangocairo`). 

**Solution:** Run from source instead of using the bundled app.

---

## ✅ Method 1: Run from Source (Recommended)

### **Step 1: Use the Launcher Script**

```bash
cd /Users/ahsan/Documents/GitHub/Tauon-AI-playlists
./run-tauon-ai.sh
```

### **Step 2: (Optional) Create Desktop Shortcut**

```bash
# Create a .command file for double-click launching
cat > ~/Desktop/Tauon\ AI.command << 'EOF'
#!/bin/bash
cd /Users/ahsan/Documents/GitHub/Tauon-AI-playlists
./run-tauon-ai.sh
EOF

chmod +x ~/Desktop/Tauon\ AI.command
```

### **Step 3: (Optional) Add to Dock**

1. Open `run-tauon-ai.sh` from Finder
2. Right-click → Open With → Terminal
3. Once running, right-click the Terminal icon in Dock
4. Options → Keep in Dock

---

## 🎯 What Works

### **✅ Privacy-First Features:**
- **Autoplay** - 100% offline library matching
  - Zero Spotify API calls
  - 100% match rate (all tracks from your library)
  - Similarity scoring: genre, era, BPM, folder
  
- **Audio Clustering** - Metadata/librosa only
  - Fast mode: Uses genre, year, BPM tags (instant)
  - Deep mode: Uses librosa audio analysis (optional)
  - Zero external API calls

- **Last.fm Radio** - Fixed collaboration detection
  - Now finds "Artist A feat. Artist B" tracks
  
- **AI Mood Playlists** - Fixed fuzzy matching
  - Now properly matches all artists from LLM response

### **✅ Working Features:**
- Local file playback ✅
- Gapless playback ✅
- CUE sheets ✅
- Plex/Jellyfin/Airsonic streaming ✅
- Lyrics ✅
- Play counting ✅
- Cover art download ✅

### **⚠️ Disabled Features:**
- Spotify streaming (requires tekore in venv)
- Tidal streaming (requires tidalapi in venv)
- Discord Rich Presence (optional)
- Chromecast (optional)
- Milkdrop visualizer (requires PyOpenGL)

---

## 🔧 Troubleshooting

### **Issue: "Module not found" errors**

**Solution:** Make sure virtual environment is activated:
```bash
cd /Users/ahsan/Documents/GitHub/Tauon-AI-playlists
source venv/bin/activate
./run-tauon-ai.sh
```

### **Issue: Window doesn't appear**

**Solution:** Check if another instance is running:
```bash
pkill -f tauon
./run-tauon-ai.sh
```

### **Issue: No sound**

**Solution:** Check audio backend in Settings → Audio → Backend
- Try PHAzOR (default) or FFmpeg

### **Issue: Can't find my music**

**Solution:** Add music folders in Settings → Music Folders

---

## 📊 Performance Comparison

| Feature | Bundled App | Source Run |
|---------|-------------|------------|
| **Startup** | Fast | Fast |
| **Autoplay** | ❌ Crashes | ✅ Works |
| **Clustering** | ❌ Crashes | ✅ Works |
| **Privacy** | 🟡 Medium | ✅ Perfect |
| **Stability** | ❌ Crashes | ✅ Stable |

---

## 📝 What's Different from Bundled App?

**Bundled App (PyInstaller):**
- ❌ Library conflicts (`libharfbuzz`)
- ❌ Crashes on startup
- ❌ Can't use patched modules

**Source Run:**
- ✅ No library conflicts
- ✅ Uses patched modules directly
- ✅ All privacy features work
- ✅ Stable and tested

---

## 🔒 Privacy Guarantees

When running from source with patched modules:

- ✅ **Autoplay:** Zero API calls (100% offline)
- ✅ **Clustering:** Zero API calls (metadata/librosa only)
- ✅ **Last.fm Radio:** Only uses Last.fm API (optional)
- ✅ **AI Mood:** Only uses LLM API if enabled (optional)
- ✅ **Your data:** Stays on your computer

**See:** `SPOTIFY_DEPENDENCIES_AUDIT.md` for complete audit

---

## 🎯 Quick Start

```bash
# 1. Go to repo
cd /Users/ahsan/Documents/GitHub/Tauon-AI-playlists

# 2. Run launcher
./run-tauon-ai.sh

# 3. Enjoy privacy-first music! 🎵
```

---

## 📚 Documentation Files

- `README.md` - Overview and features
- `IMPROVEMENTS.md` - Detailed changelog
- `AUTOPLAY_INTEGRATION.md` - Autoplay guide
- `SPOTIFY_DEPENDENCIES_AUDIT.md` - Privacy audit
- `BUILD_MACOS_APP.md` - Building instructions
- `HOW_TO_RUN.md` - This file

---

**Happy listening! 🎵🔒**
