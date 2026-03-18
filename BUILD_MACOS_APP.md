# Building a Signed macOS App from Your Fork

## Option 1: Run from Source (Recommended for Development)

Use the `run-tauon-patched.sh` script to run your modified version.

## Option 2: Build Your Own Signed App Bundle

### Prerequisites
```bash
# Install PyInstaller and dependencies
pip install pyinstaller
pip install -r requirements.txt
```

### Build Steps

1. **Modify the source code** in `src/tauon/t_modules/t_playlist_gen.py`

2. **Build with PyInstaller**:
   ```bash
   cd /Users/ahsan/Documents/GitHub/Tauon-AI-playlists
   pyinstaller mac.spec
   ```

3. **Adhoc sign the app**:
   ```bash
   codesign --force --deep --sign - dist/Tauon.app
   ```

4. **Remove quarantine attribute** (if needed):
   ```bash
   xattr -cr dist/Tauon.app
   ```

5. **Create DMG** (optional):
   ```bash
   hdiutil create -volname "Tauon AI" -srcfolder dist/Tauon.app -ov -format UDZO Tauon-AI.dmg
   ```

### Install Your Built App

```bash
# Backup original
cp -R /Applications/Tauon.app /Applications/Tauon.app.backup

# Install your version
cp -R dist/Tauon.app /Applications/Tauon-AI.app

# Sign and remove quarantine
codesign --force --deep --sign - /Applications/Tauon-AI.app
xattr -cr /Applications/Tauon-AI.app
```

### First Launch

On first launch, macOS may show a warning. To bypass:
1. Right-click the app → Open
2. Click "Open" in the warning dialog

Or use:
```bash
xattr -cr /Applications/Tauon-AI.app
```

## Why This Works

- **Adhoc signing** (`codesign -s -`) signs with no identity - works for personal use
- **Notarization** is only required for distribution to other users
- **Gatekeeper** can be bypassed for personal apps with `xattr -cr`

## Limitations

- App will show "Developer cannot be verified" warning (normal for adhoc signed)
- Must be re-signed after each code change
- Cannot distribute to others without Apple Developer ID ($99/year)
