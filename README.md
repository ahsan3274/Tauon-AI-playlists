# Tauon AI Playlists

**Tauon Music Box with intelligent playlist generation and library expansion**

A fork of [Tauon Music Box](https://github.com/Taiko2k/TauonMusicBox) that adds AI-powered playlist generation, smart discovery, and metadata enrichment — all using your existing library.

---

## What This Fork Adds

### Smart Playlist Generation

Right-click any track → **Playlists** to generate:

- **Similarity Radio** — Finds tracks in your library that sound like the current track (genre, era, BPM, energy matching)
- **Artist Radio** — Builds a playlist from similar artists via Last.fm
- **Mood Playlists** — Clusters your entire library into 8 mood-based playlists using Thayer's model
- **Energy Playlists** — High, medium, and low energy groupings
- **Genre Clusters** — K-means clustering on audio features
- **Decade Playlists** — Organize by era

### Smart Mood Discovery

Right-click any track for mood-aware discovery:

- **Mood Match** — Find more tracks in the same mood as your current track
- **Mood Transition** — Gradually shift from current mood to a target mood
- **Discover Missing Moods** — Find moods in your library you've been under-listening to

### Smart Autoplay

When your queue runs out, Tauon automatically queues similar tracks:
- 100% offline — uses your library metadata only
- Zero external API calls required
- Smart similarity matching (genre, era, BPM, energy)
- Configurable trigger threshold

### Metadata Enrichment

Automatically fixes messy metadata on startup:
- Parses artist/title from filenames like `Apocalypse_-_Cigarettes_After_Sex_128k.mp3`
- Cleans noise from titles (Official Audio, HD, bitrate tags, etc.)
- Looks up missing genre and release year from MusicBrainz and Last.fm
- Batch API queries for efficiency (one call per unique artist, 10 tracks per recording lookup)
- Runs silently on every startup — already-processed tracks are skipped

### Listen History

Every track play is logged with metadata, mood, and queue source:
- Track what you're actually listening to
- Analyze mood distribution over time
- See which recommendation sources work best for you
- CLI tool included: `python listen_stats.py`

### YouTube Library Expansion

Right-click a track → **Discover Similar Music** to find and download tracks you don't already own:
- Queries Spotify/Last.fm for similar tracks
- Cross-references against your library
- Downloads missing tracks from YouTube via yt-dlp
- Auto-imports into your library

---

## What Tauon Already Does

All the core features from Tauon Music Box:

- Fast, responsive UI with large album art and gallery browsing
- Gapless playback
- Drag-and-drop playlist creation
- Support for most common codecs and tracker file types
- CUE sheet support
- Stream from **Plex**, **Jellyfin**, or **Airsonic**
- Play count tracking with visualization
- Search artists on Rate Your Music, tracks on Genius
- Built-in topchart generator
- One-click archive extraction and import
- Lyrics fetching
- Last.fm and ListenBrainz scrobbling
- Chromecast support
- Discord Rich Presence
- Transfer playlists to Android devices

---

## Quick Start

### macOS

```bash
cd ~/Documents/GitHub/Tauon-AI-playlists
./venv/bin/python src/tauon
```

### Linux

```bash
pip install -r requirements.txt
python3 -m tauon
```

<a href='https://flathub.org/apps/details/com.github.ahsan3274.tauon-ai'><img width='240' alt='Download on Flathub' src='https://dl.flathub.org/assets/badges/flathub-badge-en.png'/></a>

**Dependencies for AI features:** `numpy` and `scikit-learn` are required for mood/genre clustering. Install them with `pip install numpy scikit-learn`.

**Optional:** `yt-dlp` for YouTube library expansion (`brew install yt-dlp` on macOS).

### Windows

Not tested. Use WSL2 or help us add Windows support.

---

## How the Features Work

### Mood Playlists

Uses Thayer's 2D mood model (energy × valence) to classify every track in your library into one of 8 moods:

| Mood | Energy | Valence | Examples |
|------|--------|---------|----------|
| Joyful | High | High | Dance, pop, jubilant music |
| Power | High | Mid | Rock anthems, hip-hop, driving electronic |
| Tension | High | Low | Dark metal, aggressive EDM |
| Wonder | Mid | High | Classical major, cinematic |
| Transcendence | High | High | Epic trance, film scores |
| Nostalgia | Low | Mid | Indie, folk, bittersweet |
| Tenderness | Low | High | Soft ballads, acoustic love |
| Peacefulness | Low | Mid | Ambient, meditation |

Each track is scored against all 8 moods using Gaussian distance in 3D feature space (energy, valence, acousticness). The dominant mood wins. Playlists get unique evocative names each time — no two runs produce the same names.

### Similarity Radio

Uses weighted Euclidean distance on audio features:
- Energy (25%), valence (20%), danceability (15%), acousticness (15%), tempo (15%), loudness (10%)
- Bonus for same genre and artist
- Returns top 50 most similar tracks from your library

### Metadata Enrichment

Runs automatically on startup with a cache to avoid reprocessing:

1. **Filename parsing** (instant, offline) — Splits `Artist_-_Title.mp3` into proper artist/title fields
2. **Artist genre lookup** (batch MusicBrainz → one call per unique artist)
3. **Recording date lookup** (batch MusicBrainz → 10 tracks per call)
4. **Fallback genre** (Last.fm for artists MusicBrainz doesn't have)

Changes are persisted to Tauon's database via `save_state()`.

---

## Settings

**Menu → Settings → Accounts** for API keys and playlist generator settings.

| Setting | What It Does |
|---------|-------------|
| **Last.fm API Key** | Required for Artist Radio. Get from [last.fm/api](https://www.last.fm/api/account/create) |
| **Autoplay** | Enable/disable smart queue extension |
| **Autoplay Threshold** | Queue when < N tracks left (default: 2) |

No API keys needed for mood playlists, similarity radio, genre clusters, decade playlists, or autoplay — these all work offline with your library metadata.

---

## Project Structure

```
src/tauon/t_modules/
├── t_playlist_gen.py        # Original playlist generation + Last.fm radio
├── t_playlist_gen_v2.py     # Audio-based mood/genre/energy/decade/similarity
├── t_autoplay.py            # Smart queue extension
├── t_mood_match.py          # Mood match, transition, discover missing
├── t_meta_enrich_batch.py   # Batch metadata enrichment
├── t_yt_expand.py           # YouTube library expansion
├── t_spotify_discover.py    # Spotify/Last.fm discovery
├── t_listen_history.py      # Listen history tracking
├── t_mood_visualizer.py     # Mood distribution display
└── t_utils_playlist.py      # Shared utilities
```

---

## Contributing

Help wanted:

1. **Windows testing** — Verify AI features work on Windows
2. **Unit tests** — Test coverage for playlist generation
3. **macOS app bundle** — Get past RunningBoard process isolation
4. **Flatpak submission** — Complete the Flathub PR process
5. **More mood names** — Expand the evocative playlist name generator

---

## License

**Original Tauon:** GPL-3.0 (Taiko2k)
**This fork:** GPL-3.0 (derivative work)

---

## Acknowledgments

- [Tauon Music Box](https://github.com/Taiko2k/TauonMusicBox) — The original player
- IEEE paper: "An Efficient Classification Algorithm for Music Mood Detection"
- Thayer's mood model — 2D arousal × valence framework
- MusicBrainz — Free, open music metadata database
- Last.fm — Artist similarity data

---

**Version:** 9.2.0-AI
**Last Updated:** April 2026
**Maintainer:** [@ahsan3274](https://github.com/ahsan3274)
**Issues:** https://github.com/ahsan3274/Tauon-AI-playlists/issues
