# Spotify Dependencies Audit - Complete List

After removing Spotify from autoplay and audio clustering, here are ALL remaining Spotify-dependent features in Tauon.

---

## Summary

| Category | Features | Data Sent | Can Be Removed? |
|----------|----------|-----------|-----------------|
| **Core Playback** | 2 features | Continuous | ❌ No (core functionality) |
| **Library Management** | 4 features | On-demand | ⚠️ Optional |
| **Playlist Generation** | 0 features | ✅ NONE | ✅ Already removed |
| **Scrobbling** | 2 features | Every 30s | ⚠️ Optional |

---

## 1. Core Spotify Playback (t_spot.py)

### **Feature 1: Spotify Streaming Playback**
**File:** `t_spot.py`  
**Functions:** `connect()`, `control()`, `update()`  
**What it does:** Allows playing music directly from Spotify (streaming)

**Data sent to Spotify:**
```
Continuous stream during playback:
- Track ID playing
- Play/pause/skip events
- Playback position (every few seconds)
- Device information
- Account authentication token
```

**Frequency:** Continuous while playing Spotify tracks

**Can be removed?** ❌ **No** - This is core functionality for users who want to stream from Spotify

**Privacy impact:** 🟡 **Medium** - Same as official Spotify app

---

### **Feature 2: Spotify Connect / Remote Control**
**File:** `t_spot.py`  
**Functions:** `control("next")`, `control("pause")`, etc.  
**What it does:** Control Spotify playback (like Spotify Connect)

**Data sent to Spotify:**
```
Remote commands:
- Play/pause/stop
- Next/previous track
- Volume changes
- Seek commands
```

**Frequency:** On user action

**Can be removed?** ❌ **No** - Required for Spotify playback control

**Privacy impact:** 🟡 **Medium** - Standard for music player remote control

---

## 2. Library Management (t_main.py, t_spot.py)

### **Feature 3: Import Spotify Playlists**
**File:** `t_main.py`  
**Functions:** `import_spotify_playlist()`, `paste_playlist_coast_fire()`  
**What it does:** Import your Spotify playlists into Tauon

**Data sent to Spotify:**
```
On import:
- User's playlist IDs
- Playlist track listings
- User authentication token
```

**Frequency:** On-demand (user-triggered)

**Can be removed?** ⚠️ **Optional** - Power user feature, not essential

**Privacy impact:** 🟡 **Medium** - Reveals playlist contents to Spotify

**Replacement:** None needed - this is Spotify-specific feature

---

### **Feature 4: Upload Playlists to Spotify**
**File:** `t_main.py`  
**Functions:** `upload_spotify_playlist()`  
**What it does:** Create Spotify playlists from Tauon playlists

**Data sent to Spotify:**
```
On upload:
- Full playlist metadata (name, tracks)
- Track search queries (to find Spotify IDs)
- User authentication token
```

**Frequency:** On-demand (user-triggered)

**Can be removed?** ⚠️ **Optional** - Power user feature

**Privacy impact:** 🟡 **Medium** - Creates playlists in your Spotify account

**Replacement:** None needed - Spotify-specific feature

---

### **Feature 5: Spotify Likes Sync**
**File:** `t_main.py`  
**Functions:** `toggle_spotify_like_ref()`, `toggle_spotify_like_active()`  
**What it does:** Like/unlike tracks on Spotify

**Data sent to Spotify:**
```
On like/unlike:
- Track ID
- Like/unlike action
- User authentication token
```

**Frequency:** On user action

**Can be removed?** ⚠️ **Optional** - Only needed if using Spotify streaming

**Privacy impact:** 🟡 **Medium** - Updates your Spotify liked tracks

**Replacement:** Use Tauon's internal "Love" feature instead (already exists)

---

### **Feature 6: Access Spotify Library**
**File:** `t_main.py`  
**Functions:** `add_to_spotify_library()`, `add_to_spotify_library2()`  
**What it does:** Add albums/tracks to your Spotify library

**Data sent to Spotify:**
```
On add:
- Album/track IDs
- User authentication token
```

**Frequency:** On user action

**Can be removed?** ⚠️ **Optional** - Only for Spotify streaming users

**Privacy impact:** 🟡 **Medium** - Modifies your Spotify saved albums

**Replacement:** None needed - Spotify-specific feature

---

## 3. Playlist Generation (✅ REMOVED)

### ~~Feature 7: Spotify Audio Features for Clustering~~
**Status:** ✅ **REMOVED** - Now uses offline metadata/librosa only

**Old file:** `t_playlist_gen.py`  
**Old functions:** `_get_spotify_features()`, `_get_track_features()`

**Replacement:** 
- `_get_metadata_features()` - Uses genre, year, BPM from tags
- `_get_local_features()` - Uses librosa for audio analysis (offline)

---

### ~~Feature 8: Spotify Recommendations for Autoplay~~
**Status:** ✅ **REMOVED** - Now uses library-only matching

**Old file:** `t_autoplay.py`  
**Old functions:** `_queue_spotify_similar()`, `_find_library_match()`

**Replacement:**
- `_queue_library_similar()` - Scores tracks by genre, era, BPM, folder
- `calculate_similarity()` - Pure offline similarity scoring

---

## 4. Scrobbling (t_main.py)

### **Feature 9: Last.fm Scrobbling**
**File:** `t_main.py`  
**Class:** `LastScrob`  
**Functions:** `scrob_full_track()`, `listen_track()`, `update()`  
**What it does:** Send play history to Last.fm

**Data sent to Last.fm:**
```
Every 30 seconds during playback:
- Artist name
- Track title
- Album name
- Timestamp
- Track duration

On scrobble (after 50% play or 4 minutes):
- Full track metadata
- Play timestamp
```

**Frequency:** 
- "Now playing" updates: Every 30 seconds
- Scrobbles: Once per track (after completion)

**Can be removed?** ⚠️ **Optional** - Can be made opt-in

**Privacy impact:** 🟡 **Medium** - Builds listening profile on Last.fm

**Replacement:** Use Tauon's internal play counting (already exists, local only)

---

### **Feature 10: ListenBrainz Scrobbling**
**File:** `t_main.py`  
**Class:** `ListenBrainz` (tauon.lb)  
**Functions:** `listen_full()`, `listen_playing()`  
**What it does:** Send play history to ListenBrainz

**Data sent to ListenBrainz:**
```
Same as Last.fm:
- Artist, title, album, timestamp
- Track metadata
```

**Frequency:** Same as Last.fm

**Can be removed?** ⚠️ **Optional** - Can be made opt-in

**Privacy impact:** 🟢 **Low** - ListenBrainz is non-profit, privacy-focused

**Replacement:** Use Tauon's internal play counting

---

## 5. Other Services

### **Feature 11: Jellyfin/Subsonic Streaming**
**File:** `t_jellyfin.py`, `t_subsonic.py`  
**Functions:** Various streaming functions  
**What it does:** Stream from self-hosted servers

**Data sent:**
```
To your own server:
- Track requests
- Play/pause/scrobble events
```

**Frequency:** During playback

**Can be removed?** ❌ **No** - Core functionality for self-hosted streaming

**Privacy impact:** ✅ **None** - Your own server, you control the data

---

### **Feature 12: Plex Streaming**
**File:** `t_plex.py` (if exists)  
**What it does:** Stream from Plex server

**Data sent:** To your Plex server

**Privacy impact:** 🟢 **Low** - Your own server

---

## Recommendations

### **High Priority (Privacy-Critical)**

1. **Make scrobbling opt-in, not default**
   - Currently: Auto-submits if API key is set
   - Recommended: Ask user "Enable scrobbling?" on first run
   - Add clear toggle in Settings → Privacy

2. **Document data flow clearly**
   - Add privacy notice in Settings
   - Show what data each feature sends
   - Make it easy to disable

### **Medium Priority (User Choice)**

3. **Spotify import/upload features**
   - Keep as-is (Spotify-specific features)
   - Document that they require Spotify account
   - Not needed for local library users

4. **Spotify likes sync**
   - Only activate if user enables Spotify streaming
   - Don't prompt local-only users

### **Low Priority (Already Good)**

5. **Core Spotify playback**
   - Keep as-is (users who want Spotify streaming need this)
   - Clearly labeled as "Spotify" feature

6. **Self-hosted streaming (Jellyfin/Subsonic)**
   - Already privacy-respecting (your own server)
   - No changes needed

---

## After This Audit: What's Left?

### **Removed (Privacy-First):**
- ✅ Spotify audio features for clustering
- ✅ Spotify recommendations for autoplay
- ✅ All Spotify API calls from playlist generation

### **Remaining (Core Features):**
- 🟡 Spotify streaming playback (user choice)
- 🟡 Spotify library management (user choice)
- 🟡 Scrobbling to Last.fm/ListenBrainz (should be opt-in)
- ✅ Self-hosted streaming (privacy-respecting)

### **Net Result:**
- **Playlist generation:** 100% offline ✅
- **Autoplay:** 100% offline ✅
- **Core playback:** User's choice (Spotify or local) ✅
- **Scrobbling:** Should be opt-in ⚠️

---

## Privacy Score

| Feature Category | Before | After |
|-----------------|--------|-------|
| Playlist Generation | 🟡 Medium | ✅ Perfect |
| Autoplay | 🟡 Medium | ✅ Perfect |
| Core Playback | 🟡 Medium | 🟡 Medium (unchanged) |
| Scrobbling | 🟡 Medium | 🟡 Medium (should be opt-in) |
| **Overall** | 🟡 **Medium** | 🟢 **Good** |

---

## Next Steps (Optional)

To achieve **Perfect Privacy**:

1. Make scrobbling opt-in (not default)
2. Add clear privacy indicators in UI
3. Document what data each feature sends
4. Add "Privacy Mode" that disables all external APIs

This would make Tauon the **most privacy-focused music player** available.
