# 🍎 Native macOS App Installation Guide

## Problem Solved ✅

This guide solves the issue where running `run-tauon-ai.sh` shows a Python script icon in the Dock that doesn't relaunch after closure.

**Solution:** Build a proper `.app` bundle that integrates natively with macOS.

---

## 🚀 Quick Start (3 Steps)

### **Step 1: Build the Native App**

```bash
cd /Users/ahsan/Documents/GitHub/Tauon-AI-playlists
./build-macos-native-app.sh
```

This will:
- ✅ Install dependencies in virtual environment
- ✅ Build the phazor audio extension
- ✅ Create a proper `.app` bundle with PyInstaller
- ✅ Sign the app for your Mac
- ✅ Install to `/Applications/Tauon-AI.app`
- ✅ Add documentation access

### **Step 2: Launch the App**

```bash
open /Applications/Tauon-AI.app
```

Or find it in your **Applications** folder and drag to Dock!

### **Step 3: (Optional) Handle Security Warning**

On first launch, macOS may show "Developer cannot be verified":

**Option A - System Settings:**
1. Go to **System Settings → Privacy & Security**
2. Scroll down and click **"Open Anyway"**

**Option B - Terminal:**
```bash
xattr -cr /Applications/Tauon-AI.app
```

---

## 📚 Accessing Documentation

### **Method 1: From Finder**
1. Right-click **Tauon-AI.app** in Applications
2. Select **"Show Package Contents"**
3. Navigate to: `Contents/Resources/Documentation/`
4. Open any `.md` file (use Marked, iA Writer, or view on GitHub)

### **Method 2: From Terminal**
```bash
open /Applications/Tauon-AI.app/Contents/Resources/Documentation/
```

### **Method 3: Create Documentation Launcher** (Optional)
```bash
# Create a quick launcher in your home directory
cat > ~/tauon-docs.command << 'EOF'
#!/bin/bash
open /Applications/Tauon-AI.app/Contents/Resources/Documentation/
EOF

chmod +x ~/tauon-docs.command
# Now double-click ~/tauon-docs.command to open docs
```

---

## 🎯 What You Get

### **Native App Benefits:**
| Feature | Python Script | Native App |
|---------|--------------|------------|
| **Dock Icon** | Python 🐍 | Tauon AI 🎵 |
| **Relaunch** | ❌ Manual | ✅ Click icon |
| **App Name** | `python3` | `Tauon AI` |
| **Spotlight** | ❌ No | ✅ Yes |
| **Launchpad** | ❌ No | ✅ Yes |
| **App Switcher** | Python | Tauon AI |
| **Documentation** | Manual | Built-in |

### **Included Documentation:**
- `README.md` - Project overview
- `HOW_TO_RUN.md` - Running instructions
- `AI_PLAYLIST_SETUP.md` - AI features guide
- `AUDIO_RECOMMENDER.md` - Recommender system docs
- `AUDIO_FEATURES_CACHE.md` - Cache system docs
- `METADATA_ENRICHMENT.md` - Metadata enrichment
- `CHANGELOG.md` - Version history

---

## 🔧 Troubleshooting

### **Issue: Build fails with "phazor not found"**

**Solution:**
```bash
# Install Xcode Command Line Tools
xcode-select --install

# Then rebuild
cd /Users/ahsan/Documents/GitHub/Tauon-AI-playlists
./build-macos-native-app.sh
```

### **Issue: App won't open (Gatekeeper)**

**Solution:**
```bash
# Remove quarantine attribute
xattr -cr /Applications/Tauon-AI.app

# Or use System Settings:
# System Settings → Privacy & Security → Open Anyway
```

### **Issue: Missing libraries (libSDL3, etc.)**

**Solution:**
```bash
# Install dependencies via Homebrew
brew install sdl3 sdl3_image ffmpeg gobject-introspection gtk+3 librsvg
```

### **Issue: App crashes on startup**

**Solution:**
```bash
# Check logs
Console.app → Filter: "Tauon"

# Run from terminal to see errors
/Applications/Tauon-AI.app/Contents/MacOS/Tauon

# Rebuild with verbose output
./build-macos-native-app.sh 2>&1 | tee build.log
```

### **Issue: No sound**

**Solution:**
1. Open Tauon AI
2. Go to **Settings → Audio → Backend**
3. Try **PHAzOR** (default) or **FFmpeg**

---

## 🔄 Updating the App

When you pull new changes from git:

```bash
cd /Users/ahsan/Documents/GitHub/Tauon-AI-playlists
git pull

# Rebuild the app
./build-macos-native-app.sh
```

The script will automatically backup your old app as `Tauon-AI.app.backup`.

---

## 🗑️ Uninstall

```bash
# Remove app
rm -rf /Applications/Tauon-AI.app

# Remove backup if exists
rm -rf /Applications/Tauon-AI.app.backup

# Remove build artifacts (optional)
cd /Users/ahsan/Documents/GitHub/Tauon-AI-playlists
rm -rf build dist
```

---

## 📊 Build Output Summary

After successful build, you'll have:

```
/Applications/Tauon-AI.app/
├── Contents/
│   ├── MacOS/
│   │   └── Tauon              # Executable
│   ├── Resources/
│   │   ├── Documentation/     # 📚 All docs
│   │   ├── assets/            # App icons
│   │   └── tau-mac.icns       # App icon
│   ├── Frameworks/            # Dependencies
│   └── Info.plist             # App metadata
```

---

## 💡 Pro Tips

### **1. Add to Dock**
- Open the app
- Right-click Dock icon → Options → Keep in Dock

### **2. Launch with Spotlight**
- Press `Cmd + Space`
- Type "Tauon AI"
- Press Enter

### **3. Create Keyboard Shortcut**
```bash
# Add to System Settings → Keyboard → Keyboard Shortcuts
# App Shortcuts → Add:
# Application: Tauon AI
# Menu Title: File→Open (or any menu)
# Keyboard Shortcut: Your choice
```

### **4. Auto-launch on Login**
1. System Settings → General → Login Items
2. Click "+" under "Open at Login"
3. Select Tauon-AI.app

### **5. Quick Documentation Access**
```bash
# Add to ~/.zshrc for quick access:
alias tauondocs='open /Applications/Tauon-AI.app/Contents/Resources/Documentation/'
```

---

## 🎯 What's Different from `run-tauon-ai.sh`?

| Aspect | `run-tauon-ai.sh` | Native App |
|--------|-------------------|------------|
| **Icon** | Python script | Tauon AI |
| **Launch** | Terminal/Script | Double-click |
| **Dock** | Shows Python | Shows Tauon |
| **Relaunch** | Manual script | Click icon |
| **Integration** | None | Full macOS |
| **Documentation** | Manual | Built-in |
| **Updates** | Same script | Rebuild app |

**Recommendation:** Use native app for daily use, keep script for development/debugging.

---

## 📝 Build Script Details

The `build-macos-native-app.sh` script:

1. ✅ Checks/creates virtual environment
2. ✅ Installs Python dependencies
3. ✅ Builds phazor C extension
4. ✅ Runs PyInstaller with `mac.spec`
5. ✅ Signs app with adhoc certificate
6. ✅ Removes quarantine attributes
7. ✅ Installs to `/Applications`
8. ✅ Configures Info.plist
9. ✅ Copies documentation
10. ✅ Creates doc viewer helper

**Total time:** ~5-10 minutes (first build)
**Subsequent builds:** ~2-3 minutes

---

## 🔒 Security Notes

- **Adhoc signing:** App is signed for personal use only
- **No notarization:** Required for distribution, not personal use
- **Gatekeeper:** May show warning (normal, bypass with `xattr -cr`)
- **Privacy:** All AI features work offline (no external API calls)

---

## 📞 Support

If you encounter issues:

1. Check `build.log` for errors
2. Run `Console.app` and filter for "Tauon"
3. Check macOS version (requires macOS 12+)
4. Verify Homebrew dependencies installed
5. Review `HOW_TO_RUN.md` for troubleshooting

---

**Happy listening! 🎵**

*Last updated: March 26, 2026*
