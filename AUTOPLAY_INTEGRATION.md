# Autoplay Integration Guide

## What Was Implemented

A **Spotify-like autoplay** feature that automatically queues similar tracks when your queue is ending.

### Features
- ✅ Automatically detects when queue is ending (< 2 tracks left)
- ✅ Uses **library metadata matching** (genre, year, artist, folder, BPM)
- ✅ **100% offline** - zero external API calls
- ✅ **100% match rate** - all queued tracks exist in your library
- ✅ Cooldown system to avoid spam (30s between triggers)
- ✅ Max queue limit (10 tracks at once)
- ✅ Privacy-first design - no data leaves your computer

---

## How It Works

### Flow Diagram

```
Track is ending?
    ↓
Check queue length (< 2 tracks?)
    ↓
Trigger Autoplay
    ↓
Analyze current track metadata
    ↓
Score ALL tracks in library by similarity:
    - Same genre: +15 points
    - Same era: +8 points
    - Same folder: +5 points
    - BPM match: +6 points
    - Same artist: +2 points
    ↓
Take top matches + add variety
    ↓
Add to queue (max 10 tracks)
```

### Similarity Scoring

**Factors (in order of weight):**

| Factor | Points | Description |
|--------|--------|-------------|
| Same genre | +15 | Exact genre match (e.g., both "Rock") |
| Same era | +8 | Within 10 years (e.g., 1970s vs 1980s) |
| Same folder | +5 | Same album or folder |
| BPM match | +6 | Within 10 BPM |
| Same artist | +2 | Same artist (small bonus for variety) |

**Example:**
```
Currently playing: "Queen - Bohemian Rhapsody" (Rock, 1975, 72 BPM)

Top matches:
1. "Queen - We Are The Champions" (Rock, 1977, 68 BPM)
   Score: 15 (genre) + 8 (era) + 5 (folder) + 6 (BPM) + 2 (artist) = 36

2. "Led Zeppelin - Stairway to Heaven" (Rock, 1971, 82 BPM)
   Score: 15 (genre) + 8 (era) + 3 (BPM) = 26

3. "The Beatles - Bohemian Rhapsody" (Rock, 1969, 120 BPM)
   Score: 15 (genre) + 4 (era) = 19
```

---

## Configuration

### Preferences (in Settings → Accounts → AI Playlist Generator → Autoplay)

- **Enable Autoplay** - Master toggle
- **Trigger when < N tracks left** - Number input (1-10, default: 2)

### Constants (in `t_autoplay.py`)

Edit these at the top of the file:

```python
AUToplay_THRESHOLD = 2  # Trigger when < N tracks left
MAX_AUToplay_QUEUE = 10  # Max tracks to queue at once
AUToplay_COOLDOWN = 30  # Seconds between triggers
```

---

## Testing

1. **Enable autoplay** in Settings → Accounts → AI Playlist Generator → Autoplay
2. **Play a track** from your library
3. **Let the queue run down** to the last 1-2 tracks
4. **Watch for notification**: "Autoplay: queued X similar tracks"
5. **Check the queue** - new tracks should be added

---

## Privacy Guarantees

**Data that DOES NOT leave your computer:**
- ❌ Track titles
- ❌ Artist names
- ❌ Album information
- ❌ Play history
- ❌ Listening habits
- ❌ Library structure
- ❌ File paths

**External API calls:**
- ✅ **ZERO** - Autoplay is 100% offline

---

## Comparison: Old vs New Approach

| Aspect | Old (Spotify-based) | New (Library-based) |
|--------|---------------------|---------------------|
| **Match rate** | 20-30% | 100% |
| **API calls** | 3 per trigger | 0 |
| **Privacy** | 🟡 Medium | ✅ Perfect |
| **Speed** | Slow (API latency) | Instant |
| **Works offline** | ❌ No | ✅ Yes |
| **Data sent** | Track IDs, searches | None |

---

## Code Location

```
src/tauon/t_modules/
├── t_autoplay.py          # Autoplay manager (100% offline)
├── t_main.py              # Integration in advance() function
└── t_prefs.py             # Autoplay preferences
```

---

## Future Enhancements (Optional)

- [ ] Add "Deep Analysis" mode using librosa for better similarity detection
- [ ] User-configurable similarity weights (prefer genre over era, etc.)
- [ ] Blacklist artists/genres from autoplay
- [ ] "Magic Radio" button for any track
- [ ] BPM-based variety (alternate fast/slow tracks)
