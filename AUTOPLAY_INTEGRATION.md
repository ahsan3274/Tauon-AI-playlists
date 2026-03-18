# Spotify-like Autoplay Integration Guide

## What Was Implemented

A **Spotify-like autoplay** feature that automatically queues similar tracks when your queue is ending.

### Features
- ✅ Automatically detects when queue is ending (< 2 tracks left)
- ✅ Uses **Spotify recommendations** based on audio features (if available)
- ✅ Falls back to **Last.fm similar artists**
- ✅ Falls back to **library-based similarity** (genre, artist, folder)
- ✅ Cooldown system to avoid spam (30s between triggers)
- ✅ Max queue limit (10 tracks at once)

---

## Files to Modify

### 1. Add to `t_prefs.py`

Add these preference fields around line 380:

```python
# Autoplay preferences
autoplay_enable: bool = False
autoplay_use_spotify: bool = True
autoplay_use_lastfm: bool = True
autoplay_use_library: bool = True
```

---

### 2. Import in `t_main.py`

At the top of `t_main.py`, add the import (around line 116, after t_playlist_gen import):

```python
# Autoplay manager
try:
    from tauon.t_modules.t_autoplay import setup_autoplay, AutoplayManager
    _autoplay_available = True
except ImportError:
    _autoplay_available = False
    AutoplayManager = None
```

---

### 3. Initialize in `Tauon` class `__init__`

In the `Tauon.__init__()` method, add initialization (search for other initializations like `self.spot_ctl`):

```python
# Initialize autoplay manager
if _autoplay_available:
    self.autoplay = setup_autoplay(self)
else:
    self.autoplay = None
```

---

### 4. Trigger in `advance()` function

In the `advance()` function in `t_main.py`, add the trigger check.

**Find this section** (around line 3547 in the `advance` function):

```python
def advance(
    self, rr: bool = False, quiet: bool = False, inplace: bool = False, end: bool = False,
    force: bool = False, play: bool = True, dry: bool = False,
) -> int | None:

    if self.playing_state == PlayingState.PAUSED and not self.prefs.resume_on_jump:
        play = False
        self.playerCommand = "stop"
        self.playerCommandReady = True
```

**Add this right after the function starts** (after the `advance` function definition, before the first logic):

```python
    # ── Autoplay Trigger ─────────────────────────────────────
    # Trigger autoplay when queue is ending (but not on startup/repeat)
    if not dry and not end and not force and self.autoplay and self.autoplay.enabled:
        if self.autoplay.should_trigger_autoplay():
            queued = self.autoplay.trigger_autoplay()
            if queued > 0:
                self.show_message(f"Autoplay: queued {queued} similar tracks", mode="info")
    # ──────────────────────────────────────────────────────────
```

---

### 5. Add UI Toggle (Optional)

Add a menu item to enable/disable autoplay. Find the playback menu section and add:

```python
# Autoplay toggle
if _autoplay_available:
    def toggle_autoplay():
        if self.autoplay:
            self.autoplay.enabled = not self.autoplay.enabled
            status = "enabled" if self.autoplay.enabled else "disabled"
            self.show_message(f"Autoplay {status}")
    
    playback_menu.add(MenuItem(
        _("Autoplay Similar Tracks"), 
        toggle_autoplay,
        hint="Automatically queue similar tracks when queue ends"
    ))
```

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
Strategy 1: Spotify Recommendations
    - Get current track audio features
    - Request similar tracks from Spotify API
    - Match with library tracks
    ↓
Strategy 2: Last.fm Similar Artists
    - Get similar artists from Last.fm
    - Find tracks from those artists in library
    ↓
Strategy 3: Library Similarity
    - Match by genre, artist, folder
    - Score and rank tracks
    ↓
Add to queue (max 10 tracks)
```

### Strategies Explained

**1. Spotify Recommendations (Best)**
- Uses `spotify.track_audio_features()` to get current track's features
- Uses `spotify.recommendations()` with target energy, valence, danceability
- Returns tracks with similar audio profile
- **Pros:** Most accurate, considers mood/energy
- **Cons:** Requires Spotify API, deprecated but still works

**2. Last.fm Similar Artists**
- Uses `artist.getSimilar` API
- Finds tracks from similar artists in your library
- **Pros:** Works for any track in library
- **Cons:** Requires Last.fm API, artist-level only

**3. Library Similarity (Fallback)**
- Scores tracks by: same artist, same genre, same folder
- **Pros:** Works offline, no API needed
- **Cons:** Less sophisticated matching

---

## Configuration

### Preferences (in Settings)

Add these toggles in your settings UI:

- **Enable Autoplay** - Master toggle
- **Use Spotify** - Use Spotify recommendations (requires Spotify connected)
- **Use Last.fm** - Use Last.fm similar artists (requires API key)
- **Use Library** - Fallback to library matching

### Constants (in `t_autoplay.py`)

Edit these at the top of the file:

```python
AUToplay_THRESHOLD = 2  # Trigger when < N tracks left
MAX_AUToplay_QUEUE = 10  # Max tracks to queue at once
AUToplay_COOLDOWN = 30  # Seconds between triggers
```

---

## Testing

1. **Enable autoplay** in settings or via menu
2. **Play a track** from your library
3. **Let the queue run down** to the last 1-2 tracks
4. **Watch for notification**: "Autoplay: queued X similar tracks"
5. **Check the queue** - new tracks should be added

### Debug Mode

Enable logging to see what's happening:

```python
import logging
logging.getLogger("t_autoplay").setLevel(logging.DEBUG)
```

---

## Known Limitations

1. **Spotify API deprecated** - May stop working in future
2. **Requires library match** - Can only queue tracks you already have
3. **No crossfade** - Just queues tracks, doesn't blend
4. **Cooldown** - Won't trigger if you manually add tracks frequently

---

## Future Enhancements

- [ ] Add "autoplay radio" mode (continuous)
- [ ] User-configurable similarity thresholds
- [ ] Blacklist artists/genres from autoplay
- [ ] "Magic radio" button for current track
- [ ] Integrate with existing Last.fm radio feature

---

## Code Location

```
src/tauon/t_modules/
├── t_autoplay.py          # NEW - Autoplay manager
├── t_main.py              # MODIFIED - Integration points
└── t_prefs.py             # MODIFIED - New preferences
```
