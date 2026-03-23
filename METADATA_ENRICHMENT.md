# 🎵 Automatic Metadata Enrichment

## Problem Solved

**Issue:** Mood playlists all defaulted to "Nostalgia" because most tracks lack genre tags.

**Root Cause:** GEMS-9 algorithm needs genre for diverse mood classification:
- Without genre → default acousticness (0.50) for all tracks
- Most tracks cluster in Nostalgia region (E=0.40-0.60, V=0.52, A=0.65)

## Solution: Auto-Enrichment

**New Module:** `t_metadata_enrich.py`

Automatically fetches missing genre/mode from:

### 1. MusicBrainz (FREE, No API Key)
- ✅ Genre tags from community
- ✅ Sometimes has key/mode info
- ✅ Cached locally to avoid repeat lookups

### 2. Last.fm (Requires API Key)
- ✅ Crowdsourced genre tags
- ✅ Excellent coverage for popular music
- ✅ User adds key in Settings → Accounts

## How It Works

```
Track missing genre?
    ↓
Check local cache
    ├─ Found → Use cached genre ✓
    └─ Not found
        ↓
    Query MusicBrainz (free)
    ├─ Found → Cache + use genre ✓
    └─ Not found
        ↓
    Query Last.fm (if API key)
    ├─ Found → Cache + use genre ✓
    └─ Not found → Use BPM-based estimate
```

## Setup

### Option 1: MusicBrainz (Automatic)
No setup required! Works automatically for all tracks.

### Option 2: Last.fm (Better Coverage)
1. Get API key: https://www.last.fm/api/account/create
2. In Tauon: Settings → Accounts → AI Playlist Generator
3. Enter Last.fm API Key
4. Mood playlists will now use Last.fm genre data

## Cache Location

```
~/.local/share/TauonMusicBox/metadata-cache/genre-cache.json
```

Cache persists across sessions, so each track is only looked up once.

## Expected Improvement

**Before (no genre tags):**
```
Mood Distribution:
  Nostalgia          6 tracks
  Transcendence      2 tracks
  Unique moods: 2/9 ❌
```

**After (with enrichment):**
```
Mood Distribution:
  Power              4 tracks
  Joyful             3 tracks
  Tension            2 tracks
  Wonder             2 tracks
  Nostalgia          2 tracks
  Unique moods: 5/9 ✓
```

## Performance

- **Cache hit:** Instant (no network)
- **MusicBrainz lookup:** ~2-5 seconds per track (first time only)
- **Last.fm lookup:** ~1-3 seconds per track (first time only)
- **Subsequent runs:** All instant (cached)

## Files Modified

- `src/tauon/t_modules/t_metadata_enrich.py` - NEW
- `src/tauon/t_modules/t_playlist_gen_v2.py` - Integrated enrichment
- `src/tauon/t_modules/t_main.py` - Pass prefs to mood generation

## Technical Details

### MusicBrainz API
- Endpoint: `https://musicbrainz.org/ws/2/recording/`
- Query: `artist:"{artist}" AND recording:"{title}"`
- Rate limit: 1 request/second (enforced by timeout)

### Last.fm API
- Endpoint: `http://ws.audioscrobbler.com/2.0/`
- Method: `track.getInfo`
- Rate limit: 5 requests/second

### Caching Strategy
- Key: MD5 hash of `artist__title`
- Stored: genre, mode (if found)
- Format: JSON file
- No expiration (music metadata doesn't change)

---

**Result:** Diverse mood playlists even for untagged libraries! 🎉
