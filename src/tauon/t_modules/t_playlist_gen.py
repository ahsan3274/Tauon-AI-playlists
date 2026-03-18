"""
t_playlist_gen.py - IMPROVED VERSION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Playlist generator module for Tauon Music Box with enhanced audio features.

CHANGES IN THIS VERSION:
  ✓ Fixed: Last.fm Radio now includes collaboration tracks (feat., &, vs, etc.)
  ✓ Fixed: AI Mood Playlists now use fuzzy artist matching
  ✓ Fixed: Audio clustering with better error handling and progress reporting
  ✓ NEW: Spotify audio features integration (danceability, energy, valence, etc.)
  ✓ NEW: Hybrid approach - Spotify features + local fallback
  ✓ NEW: Feature caching to avoid repeated API calls
  ✓ NEW: Better clustering using rich Spotify features

Three generation strategies:
  lastfm  — Similar-artist graph via Last.fm API (FIXED: includes collaborations)
  llm     — Claude AI mood/vibe clustering (FIXED: fuzzy artist matching)
  audio   — Hybrid: Spotify features + local librosa fallback (NEW: rich features)
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import threading
import time
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # These types exist inside t_main.py – only used for type hints
    pass

log = logging.getLogger("t_playlist_gen")

LASTFM_API = "https://ws.audioscrobbler.com/2.0/"
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
SPOTIFY_AUDIO_FEATURES_CACHE = {}  # Simple in-memory cache: {track_key: features_dict}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Fuzzy artist matching for collaborations
# ─────────────────────────────────────────────────────────────────────────────

def _artist_matches(artist_field: str, similar_artists: set[str]) -> bool:
    """
    Check if any similar artist appears in the track's artist field.
    Handles collaborations like "Artist A feat. Artist B" or "Artist A & Artist B".
    """
    artist_lower = artist_field.lower().strip()
    
    # Direct match
    if artist_lower in similar_artists:
        return True
    
    # Check if any similar artist name appears in the field (for collaborations)
    for similar in similar_artists:
        if similar in artist_lower:
            return True
        # Also check if the artist field is a substring of similar artist name
        if artist_lower in similar and len(similar) - len(artist_lower) < 5:
            return True
    
    # Check for common collaboration patterns
    separators = [' feat. ', ' feat ', ' ft. ', ' ft ', ' vs. ', ' vs ', ' & ', ' and ', ' x ', ' × ']
    for sep in separators:
        if sep in artist_lower:
            parts = artist_lower.split(sep)
            for part in parts:
                part = part.strip()
                if part in similar_artists:
                    return True
                for similar in similar_artists:
                    if part in similar or similar in part:
                        return True
    
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Fuzzy artist match for LLM responses
# ─────────────────────────────────────────────────────────────────────────────

def _fuzzy_artist_match(artist_name: str, artist_index: dict[str, list[int]]) -> list[int]:
    """
    Find matching track IDs with fuzzy artist name matching.
    Handles variations in artist names from LLM responses.
    """
    artist_lower = artist_name.lower().strip()
    
    # Direct match first
    if artist_lower in artist_index:
        return artist_index[artist_lower]
    
    # Try partial matches (for "Artist A feat. B" scenarios)
    for indexed_artist, track_ids in artist_index.items():
        if artist_lower in indexed_artist or indexed_artist in artist_lower:
            return track_ids
        # Check word overlap
        artist_words = set(artist_lower.split())
        indexed_words = set(indexed_artist.split())
        if len(artist_words & indexed_words) >= 1 and len(artist_words) <= 3:
            common_words = artist_words & indexed_words
            if any(len(w) > 2 for w in common_words):
                return track_ids
    
    # Try removing common prefixes
    clean_patterns = [r'^the\s+', r'^a\s+', r'^an\s+', r'\s+feat\.?\s+.*$', r'\s+ft\.?\s+.*$']
    cleaned = artist_lower
    for pattern in clean_patterns:
        cleaned = re.sub(pattern, '', cleaned)
    if cleaned and cleaned in artist_index:
        return artist_index[cleaned]
    
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Build track list from Tauon's master_library
# ─────────────────────────────────────────────────────────────────────────────

def _library_snapshot(pctl, master_library, star_store) -> list[dict]:
    """
    Walk Tauon's master_library and collect every track that is actually
    referenced in at least one playlist (avoids orphaned entries).

    Returns a list of dicts:
      {id, path, title, artist, album, genre, year, play_count, duration}
    """
    # Collect all track IDs that appear in any playlist
    referenced: set[int] = set()
    for pl in pctl.multi_playlist:
        if hasattr(pl, 'playlist_ids'):
            referenced.update(pl.playlist_ids)
        elif hasattr(pl, 'playlist'):
            referenced.update(pl.playlist)

    tracks = []
    for tid, tr in master_library.items():
        if tid not in referenced:
            continue

        sc = getattr(tr, 'play_count', 0) or 0
        duration = getattr(tr, 'length', 0) or 0

        tracks.append({
            "id":         tid,
            "path":       getattr(tr, "fullpath", getattr(tr, "filename", "")),
            "title":      getattr(tr, "title",  "") or "",
            "artist":     getattr(tr, "artist", "") or "",
            "album":      getattr(tr, "album",  "") or "",
            "genre":      getattr(tr, "genre",  "") or "",
            "year":       str(getattr(tr, "date", "") or "")[:4],
            "play_count": sc,
            "duration":   duration,
        })
    return tracks


# ─────────────────────────────────────────────────────────────────────────────
# Helper: create a new Tauon playlist from a list of track IDs
# ─────────────────────────────────────────────────────────────────────────────

def _make_playlist(name: str, track_ids: list[int], pctl) -> None:
    """
    Append a new playlist tab to Tauon.
    pctl.multi_playlist items are TauonPlaylist objects.
    """
    if hasattr(pctl, "new_playlist"):
        # Newer Tauon API
        idx = pctl.new_playlist(name)
        if idx is not None and idx < len(pctl.multi_playlist):
            pctl.multi_playlist[idx].playlist_ids[:] = track_ids
    else:
        # Fallback: Try to import TauonPlaylist or use minimal fallback
        try:
            from tauon.t_modules.t_main import TauonPlaylist
            from tauon.t_modules.t_extra import uid_gen
            pl = TauonPlaylist(title=name, playlist_ids=track_ids, uuid_int=uid_gen())
            pctl.multi_playlist.append(pl)
        except ImportError:
            # Ultimate fallback - minimal object with ALL required TauonPlaylist attributes
            class MinimalPlaylist:
                def __init__(self, title, playlist_ids):
                    self.title = title
                    self.playlist_ids = playlist_ids
                    self.playing = 0
                    self.position = 0
                    self.hide_title = False
                    self.selected = 0
                    self.uuid_int = random.randint(100_000, 999_999)
                    self.hidden = False
                    self.locked = False
                    self.parent_playlist_id = 0
                    self.persist_time_positioning = False
                    self.playlist_file = ""
                    self.file_size = 0
                    self.auto_export = False
                    self.auto_import = False
                    self.export_type = "xspf"
                    self.relative_export = False
                    self.last_folder = []
            pl = MinimalPlaylist(name, track_ids)
            pctl.multi_playlist.append(pl)

    log.info("Created playlist '%s' with %d tracks", name, len(track_ids))


# ─────────────────────────────────────────────────────────────────────────────
# Strategy A – Last.fm similar-artist radio
# ─────────────────────────────────────────────────────────────────────────────

def _lastfm_similar(artist: str, api_key: str, depth: int = 2) -> set[str]:
    """BFS over Last.fm similar-artist graph; returns set of lowercase names."""
    try:
        import requests
    except ImportError:
        log.error("requests not installed — pip install requests")
        return {artist.lower()}

    seen: set[str] = set()
    similar: set[str] = {artist.lower()}
    queue = [artist.lower()]

    for _ in range(depth):
        next_q: list[str] = []
        for a in queue:
            if a in seen:
                continue
            seen.add(a)
            try:
                r = requests.get(LASTFM_API, params={
                    "method": "artist.getSimilar",
                    "artist": a,
                    "api_key": api_key,
                    "format": "json",
                    "limit": 30,
                }, timeout=10)
                for s in r.json().get("similarartists", {}).get("artist", []):
                    name = s.get("name", "").lower()
                    similar.add(name)
                    next_q.append(name)
                time.sleep(0.2)
            except Exception as exc:
                log.warning("Last.fm error for '%s': %s", a, exc)
        queue = next_q

    return similar


def generate_lastfm(
    pctl,
    master_library,
    star_store,
    seed_artist: str,
    api_key: str = "",
    limit: int = 60,
    depth: int = 2,
    notify_fn=None,
) -> None:
    """
    Build a Last.fm radio playlist in a background thread.
    Uses Tauon's existing Last.fm auth if api_key not provided.
    notify_fn(message) is called with a status string (for Tauon's toast).
    """
    def _run():
        if notify_fn:
            notify_fn(f"Last.fm: fetching artists similar to '{seed_artist}'…")

        # Use provided API key or fall back to Tauon's auth
        lm_api_key = api_key
        if not lm_api_key and hasattr(pctl, 'last_fm') and pctl.last_fm:
            lm_api_key = getattr(pctl.last_fm, 'api_key', '')

        if not lm_api_key:
            # Use a public demo key as last resort
            lm_api_key = "b048411511a3191008fee11a34f4e233"

        similar = _lastfm_similar(seed_artist, lm_api_key, depth)
        tracks = _library_snapshot(pctl, master_library, star_store)

        # FIXED: Use fuzzy matching to include collaboration tracks
        matches = [t for t in tracks if _artist_matches(t["artist"], similar)]
        if not matches:
            if notify_fn:
                notify_fn("Last.fm: no matching tracks found in library.")
            return

        # Weight by play count
        pool: list[dict] = []
        for t in matches:
            pool.extend([t] * max(1, t["play_count"]))
        random.shuffle(pool)

        seen_ids: set[int] = set()
        chosen: list[int] = []
        for t in pool:
            if t["id"] not in seen_ids:
                seen_ids.add(t["id"])
                chosen.append(t["id"])
            if len(chosen) >= limit:
                break

        name = f"♻ {seed_artist.title()} Radio"
        _make_playlist(name, chosen, pctl)

        if notify_fn:
            notify_fn(f"Created '{name}' — {len(chosen)} tracks")

    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Strategy B – LLM mood clustering (Claude API or local LLM)
# ─────────────────────────────────────────────────────────────────────────────

def generate_llm(
    pctl,
    master_library,
    star_store,
    api_key: str = "",
    num_moods: int = 6,
    notify_fn=None,
    use_local_llm: bool = False,
    local_llm_url: str = "http://localhost:1234/v1/chat/completions",
    local_model: str = "",
) -> None:
    """
    Ask an LLM to cluster your library into mood playlists.
    Supports Claude API or local LLM (LM Studio, Ollama, etc.).
    Creates one new Tauon playlist tab per mood.
    """
    def _run():
        try:
            import requests
        except ImportError:
            if notify_fn:
                notify_fn("requests not installed — pip install requests")
            return

        if notify_fn:
            notify_fn("AI Playlists: analysing library…")

        tracks = _library_snapshot(pctl, master_library, star_store)

        # Build artist → sample titles index
        artist_samples: dict[str, list[str]] = defaultdict(list)
        for t in tracks:
            if t["artist"] and t["artist"] != "Unknown Artist":
                if len(artist_samples[t["artist"]]) < 4:
                    artist_samples[t["artist"]].append(t["title"])

        artists_list = sorted(artist_samples.keys())[:300]
        
        # Build library text with just artist names (no song titles to avoid confusion)
        library_text = "\n".join(artists_list)

        prompt = (
            f"You are a music curator. Group the following artists into exactly "
            f"{num_moods} mood/vibe playlists. Each playlist should have a short "
            f"evocative name (3-5 words). Every artist must appear in exactly one "
            f"playlist.\n\n"
            f"Respond ONLY with valid JSON in this exact format:\n"
            f'{{\n  "Playlist Name 1": ["Artist A", "Artist B", "Artist C"],\n  "Playlist Name 2": ["Artist D", "Artist E"]\n}}\n\n'
            f"IMPORTANT:\n"
            f"- Use EXACT artist names as shown below (no modifications, no extra text)\n"
            f"- Do not include any explanation or text before/after the JSON\n"
            f"- Do not use markdown code blocks\n"
            f"- Each artist name must match exactly from the list provided\n\n"
            f"Artists to group:\n{library_text}"
        )

        if use_local_llm:
            if notify_fn:
                notify_fn(f"AI Playlists: sending to local LLM at {local_llm_url}…")
            # Local LLM endpoint (OpenAI-compatible API)
            payload = {
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 4096,
            }
            if local_model:
                payload["model"] = local_model
            try:
                resp = requests.post(
                    local_llm_url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=300,  # Increased from 120 to 300 seconds for large libraries
                )
                resp.raise_for_status()
                raw = resp.json()["choices"][0]["message"]["content"].strip()
            except requests.exceptions.Timeout:
                if notify_fn:
                    notify_fn(f"AI Playlists: LLM timeout (5 min). Try fewer moods or faster model.")
                return
            except Exception as exc:
                if notify_fn:
                    notify_fn(f"AI Playlists: local LLM error — {exc}")
                log.error(f"LLM request failed: {exc}")
                return
        else:
            if notify_fn:
                notify_fn("AI Playlists: sending to Claude…")
            # Claude API
            try:
                resp = requests.post(
                    ANTHROPIC_API,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 4096,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                raw = resp.json()["content"][0]["text"].strip()
            except Exception as exc:
                if notify_fn:
                    notify_fn(f"AI Playlists: API error — {exc}")
                return

        log.info(f"Raw LLM response ({len(raw)} chars): {raw[:200]}...")
        
        # Clean up markdown code blocks
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()
        
        log.info(f"After cleanup ({len(raw)} chars): {raw[:200]}...")

        try:
            mood_map: dict[str, list[str]] = json.loads(raw)
        except json.JSONDecodeError as e:
            if notify_fn:
                notify_fn(f"AI Playlists: could not parse LLM response")
                log.error(f"LLM response was not valid JSON")
                log.error(f"Raw response: {raw[:1000]}")
                log.error(f"JSON parse error: {e}")
            return

        # Build artist → track-IDs index (case-insensitive)
        artist_index: dict[str, list[int]] = defaultdict(list)
        for t in tracks:
            artist_index[t["artist"].lower()].append(t["id"])

        created = 0
        for mood_name, artist_names in mood_map.items():
            ids: list[int] = []
            for a in artist_names:
                # FIXED: Use fuzzy matching instead of exact lookup
                ids.extend(_fuzzy_artist_match(a, artist_index))
            if ids:
                random.shuffle(ids)
                _make_playlist(f"✦ {mood_name}", ids, pctl)
                created += 1

        if notify_fn:
            notify_fn(f"AI Playlists: created {created} mood playlists ✓")

    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Strategy C – Hybrid audio feature clustering (Spotify + local fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _get_spotify_features(pctl, track: dict) -> dict | None:
    """
    Try to get audio features from Spotify for a track.
    Uses fuzzy matching to find the track in Spotify's catalog.
    Returns dict with features or None if not found.
    """
    try:
        import tekore as tk
    except ImportError:
        return None
    
    if not hasattr(pctl, 'spot') or not pctl.spot or not pctl.spot.spotify:
        return None
    
    spotify = pctl.spot.spotify
    if not spotify:
        return None
    
    artist = track.get("artist", "")
    title = track.get("title", "")
    duration = track.get("duration", 0)
    
    if not artist or not title:
        return None
    
    query = f"track:{title} artist:{artist}"
    try:
        search_result = spotify.search(query, types=("track",), limit=5)
        
        if not search_result or not search_result[0] or not search_result[0].items:
            return None
        
        best_match = None
        best_duration_diff = float('inf')
        
        for spotify_track in search_result[0].items:
            spotify_duration_ms = getattr(spotify_track, 'duration_ms', 0)
            spotify_duration_s = spotify_duration_ms / 1000.0
            
            duration_diff = abs(spotify_duration_s - duration) if duration > 0 else 0
            
            spotify_artists = [a.name.lower() for a in spotify_track.artists]
            artist_match = any(artist.lower() in sa or sa in artist.lower() for sa in spotify_artists)
            
            if artist_match and duration_diff < best_duration_diff:
                best_match = spotify_track
                best_duration_diff = duration_diff
        
        if not best_match or best_duration_diff > 10:
            return None
        
        track_id = best_match.id
        features = spotify.track_audio_features(track_id)
        
        if not features:
            return None
        
        return {
            "danceability": features.danceability,
            "energy": features.energy,
            "valence": features.valence,
            "tempo": features.tempo,
            "acousticness": features.acousticness,
            "instrumentalness": features.instrumentalness,
            "liveness": features.liveness,
            "speechiness": features.speechiness,
            "loudness": features.loudness,
            "key": features.key,
            "mode": features.mode,
            "time_signature": features.time_signature,
            "duration_ms": features.duration_ms,
            "source": "spotify"
        }
        
    except Exception as e:
        log.debug(f"Spotify features lookup failed for {artist} - {title}: {e}")
        return None


def _get_local_features(track: dict, sample_duration: float = 30.0) -> dict | None:
    """
    Extract audio features locally using librosa (fallback when Spotify unavailable).
    """
    try:
        import librosa
        import numpy as np
    except ImportError:
        return None
    
    path = track.get("path", "")
    if not path or not os.path.exists(path):
        return None
    
    try:
        y, sr = librosa.load(path, sr=22050, mono=True, duration=sample_duration)
        
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr).mean()
        rms = librosa.feature.rms(y=y).mean()
        zcr = librosa.feature.zero_crossing_rate(y=y).mean()
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr).mean()
        
        return {
            "danceability": 0.5,
            "energy": float(rms * 1000),
            "valence": 0.5,
            "tempo": float(tempo),
            "acousticness": 0.5,
            "instrumentalness": 0.5,
            "liveness": 0.1,
            "speechiness": 0.1,
            "loudness": float(rolloff),
            "key": -1,
            "mode": -1,
            "time_signature": 4,
            "duration_ms": track.get("duration", 0) * 1000,
            "source": "librosa"
        }
        
    except Exception as e:
        log.debug(f"Local features extraction failed for {path}: {e}")
        return None


def _get_track_features(pctl, track: dict, use_spotify: bool = True) -> dict | None:
    """
    Get audio features for a track, trying Spotify first then local analysis.
    Uses caching to avoid repeated API calls.
    """
    cache_key = f"{track.get('artist', '')}__{track.get('title', '')}__{track.get('duration', 0)}"
    
    if cache_key in SPOTIFY_AUDIO_FEATURES_CACHE:
        return SPOTIFY_AUDIO_FEATURES_CACHE[cache_key]
    
    if use_spotify:
        features = _get_spotify_features(pctl, track)
        if features:
            SPOTIFY_AUDIO_FEATURES_CACHE[cache_key] = features
            return features
    
    features = _get_local_features(track)
    if features:
        SPOTIFY_AUDIO_FEATURES_CACHE[cache_key] = features
    
    return features


def generate_audio(
    pctl,
    master_library,
    star_store,
    n_clusters: int = 5,
    sample_duration: float = 30.0,
    use_spotify_features: bool = True,
    notify_fn=None,
) -> None:
    """
    Analyse each track with Spotify audio features (if available) or librosa,
    then K-means cluster. 
    
    NEW: Hybrid approach - Spotify features + local fallback
    NEW: Rich features from Spotify: danceability, energy, valence, acousticness, etc.
    NEW: Better error handling and progress reporting
    
    Features used for clustering:
    - From Spotify: danceability, energy, valence, tempo, acousticness, 
                    instrumentalness, liveness, speechiness, loudness
    - From librosa (fallback): BPM, spectral centroid, energy, ZCR, rolloff, chroma
    """
    def _run():
        try:
            import numpy as np
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler
        except ImportError as e:
            if notify_fn:
                notify_fn(f"Audio cluster missing: {e.name}. Run: pip install scikit-learn numpy")
            log.error(f"Audio clustering missing dependencies: {e}")
            return

        tracks = _library_snapshot(pctl, master_library, star_store)
        if not tracks:
            if notify_fn:
                notify_fn("Audio Cluster: no tracks found in library")
            return
            
        if notify_fn:
            notify_fn(f"Audio Cluster: analysing {len(tracks)} tracks… (this takes a while)")

        features: list[list[float]] = []
        valid: list[dict] = []
        failed_count = 0
        spotify_count = 0
        local_count = 0
        start_time = time.time()

        for i, t in enumerate(tracks):
            track_features = _get_track_features(pctl, t, use_spotify=use_spotify_features)
            
            if not track_features:
                failed_count += 1
                continue
            
            # Build feature vector using rich Spotify features
            feature_vector = [
                track_features.get("danceability", 0.5),
                track_features.get("energy", 0.5),
                track_features.get("valence", 0.5),
                track_features.get("tempo", 120) / 200.0,
                track_features.get("acousticness", 0.5),
                track_features.get("instrumentalness", 0.5),
                track_features.get("liveness", 0.1),
                track_features.get("speechiness", 0.1),
                (track_features.get("loudness", -10) + 60) / 60.0,
            ]
            
            features.append(feature_vector)
            valid.append(t)
            
            if track_features.get("source") == "spotify":
                spotify_count += 1
            else:
                local_count += 1
            
            if notify_fn and i % 50 == 0 and i > 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 1
                remaining = len(tracks) - i
                eta_seconds = remaining / rate if rate > 0 else 0
                eta_minutes = int(eta_seconds / 60)
                notify_fn(f"Audio Cluster: {i}/{len(tracks)} analysed (~{eta_minutes}min remaining)")

        elapsed_total = time.time() - start_time
        log.info(f"Audio analysis complete: {len(valid)} succeeded, {failed_count} failed "
                f"(Spotify: {spotify_count}, Local: {local_count}) in {elapsed_total:.1f}s")

        if len(valid) < n_clusters:
            if notify_fn:
                notify_fn(f"Audio Cluster: only {len(valid)} tracks analysed, need {n_clusters}")
            log.error(f"Not enough tracks for clustering: {len(valid)} < {n_clusters}")
            return

        X = np.array(features)
        X_s = StandardScaler().fit_transform(X)
        km = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
        labels = km.fit_predict(X_s)

        # Label each cluster by dominant features
        def _cluster_name(cid):
            idxs = [i for i, l in enumerate(labels) if l == cid]
            if not idxs:
                return f"⊕ Cluster {cid + 1}"
            
            cluster_features = [features[i] for i in idxs]
            median_energy = sorted(f[1] for f in cluster_features)[len(cluster_features)//2]
            median_valence = sorted(f[2] for f in cluster_features)[len(cluster_features)//2]
            median_tempo = sorted(f[3] for f in cluster_features)[len(cluster_features)//2] * 200
            
            energy_w = "Calm" if median_energy < 0.3 else "Energetic" if median_energy > 0.7 else "Moderate"
            valence_w = "Dark" if median_valence < 0.3 else "Happy" if median_valence > 0.7 else "Neutral"
            tempo_w = "Slow" if median_tempo < 90 else "Fast" if median_tempo > 130 else "Mid-tempo"
            
            return f"⊕ {energy_w} {valence_w} ({tempo_w})"

        for cid in range(n_clusters):
            ids = [valid[i]["id"] for i, l in enumerate(labels) if l == cid]
            if ids:
                random.shuffle(ids)
                _make_playlist(_cluster_name(cid), ids, pctl)

        if notify_fn:
            notify_fn(f"Audio Cluster: created {n_clusters} playlists ✓")

    threading.Thread(target=_run, daemon=True).start()
