"""
t_playlist_gen.py - Playlist Generator (LEGACY + Core Functions)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  DEPRECATED FEATURES:
        - This file is maintained for backwards compatibility
    
✅ ACTIVE FEATURES:
    - Last.fm Radio (generate_lastfm) - RECOMMENDED
    - Audio Feature Clusters (generate_audio) - RECOMMENDED

📚 NEW: Use t_playlist_gen_v2 for:
    - Mood Playlists (8 moods, IEEE paper-based)
    - Energy Playlists
    - Genre Clusters (audio-based)
    - Decade Playlists
    - Similarity Radio
    - Artist Radio (Last.fm)

For shared utilities, see: t_utils_playlist.py
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

from tauon.t_modules.t_utils_playlist import (
    normalize_artist_name,
    extract_all_artists,
    artist_matches,
    get_library_tracks,
    create_playlist,
)

if TYPE_CHECKING:
    # These types exist inside t_main.py – only used for type hints
    pass

log = logging.getLogger("t_playlist_gen")

LASTFM_API = "https://ws.audioscrobbler.com/2.0/"

# Re-export shared utilities for backwards compatibility
_library_snapshot = get_library_tracks
_make_playlist = create_playlist




# ─────────────────────────────────────────────────────────────────────────────
# Helper: Build track list from Tauon's master_library
# ─────────────────────────────────────────────────────────────────────────────

def _library_snapshot(pctl, master_library) -> list[dict]:
    """
    Walk Tauon's master_library and collect ALL tracks.

    Previously filtered by playlist membership, which excluded
    fresh imports until manually added to a playlist.

    Returns a list of dicts:
      {id, path, title, artist, album, genre, year, play_count, duration}
    """
    tracks = []
    for tid, tr in master_library.items():
        # Skip non-audio entries (network streams, etc.)
        if not getattr(tr, "fullpath", "") and not getattr(tr, "filename", ""):
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
        tracks = _library_snapshot(pctl, master_library)

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
def generate_audio(
    pctl,
    master_library,
    star_store,
    n_clusters: int = 5,
    sample_duration: float = 30.0,
    use_deep_analysis: bool = False,
    notify_fn=None,
) -> None:
    """
    Analyse each track using metadata or librosa (fully offline),
    then K-means cluster.
    
    Two modes:
    1. Fast mode (default): Use existing tags (genre, year, BPM)
    2. Deep analysis mode: Use librosa for audio features (slower but accurate)
    
    Features used for clustering:
    - Fast mode: genre, year, BPM (from tags)
    - Deep mode: BPM, energy, spectral centroid, ZCR, rolloff
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

        tracks = _library_snapshot(pctl, master_library)
        if not tracks:
            if notify_fn:
                notify_fn("Audio Cluster: no tracks found in library")
            return
        
        if use_deep_analysis:
            if notify_fn:
                notify_fn(f"Audio Cluster: analysing {len(tracks)} tracks with librosa… (this takes a while)")
        else:
            if notify_fn:
                notify_fn(f"Audio Cluster: analysing {len(tracks)} tracks using metadata…")

        features: list[list[float]] = []
        valid: list[dict] = []
        failed_count = 0
        start_time = time.time()

        for i, t in enumerate(tracks):
            if use_deep_analysis:
                # Deep analysis mode: use librosa
                track_features = _get_local_features(t, sample_duration)
            else:
                # Fast mode: use metadata tags
                track_features = _get_metadata_features(t)
            
            if not track_features:
                failed_count += 1
                continue
            
            # Build feature vector for clustering
            if use_deep_analysis:
                # Librosa features
                feature_vector = [
                    track_features.get("bpm", 120) / 200.0,  # Normalize BPM
                    track_features.get("energy", 0.5),
                    track_features.get("centroid", 0.5) / 10000,  # Normalize
                    track_features.get("zcr", 0.5),
                    track_features.get("rolloff", 0.5) / 10000,  # Normalize
                ]
            else:
                # Metadata features
                feature_vector = [
                    track_features.get("bpm", 120) / 200.0,  # Normalize BPM
                    track_features.get("genre", 0) / 12.0,    # Normalize genre
                    track_features.get("year", 1980) / 2025.0,  # Normalize year
                ]
            
            features.append(feature_vector)
            valid.append(t)
            
            if notify_fn and i % 50 == 0 and i > 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 1
                remaining = len(tracks) - i
                eta_seconds = remaining / rate if rate > 0 else 0
                eta_minutes = int(eta_seconds / 60)
                notify_fn(f"Audio Cluster: {i}/{len(tracks)} analysed (~{eta_minutes}min remaining)")

        elapsed_total = time.time() - start_time
        log.info(f"Audio analysis complete: {len(valid)} succeeded, {failed_count} failed in {elapsed_total:.1f}s")

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
            
            if use_deep_analysis:
                # Librosa-based naming
                median_bpm = sorted(f[0] for f in cluster_features)[len(cluster_features)//2] * 200
                median_energy = sorted(f[1] for f in cluster_features)[len(cluster_features)//2]
                
                energy_w = "Calm" if median_energy < 0.3 else "Energetic" if median_energy > 0.7 else "Moderate"
                tempo_w = "Slow" if median_bpm < 90 else "Fast" if median_bpm > 130 else "Mid-tempo"
                
                return f"⊕ {energy_w} ({tempo_w})"
            else:
                # Metadata-based naming
                median_bpm = sorted(f[0] for f in cluster_features)[len(cluster_features)//2] * 200
                median_genre = sorted(f[1] for f in cluster_features)[len(cluster_features)//2]
                median_year = sorted(f[2] for f in cluster_features)[len(cluster_features)//2] * 2025
                
                genre_map = {1: 'Rock', 2: 'Pop', 3: 'Electronic', 4: 'Jazz', 5: 'Classical'}
                genre_name = genre_map.get(int(median_genre * 12), 'Mixed')
                era = int(median_year / 10) * 10
                
                tempo_w = "Slow" if median_bpm < 90 else "Fast" if median_bpm > 130 else "Mid-tempo"
                
                return f"⊕ {genre_name} {era}s ({tempo_w})"

        for cid in range(n_clusters):
            ids = [valid[i]["id"] for i, l in enumerate(labels) if l == cid]
            if ids:
                random.shuffle(ids)
                _make_playlist(_cluster_name(cid), ids, pctl)

        if notify_fn:
            notify_fn(f"Audio Cluster: created {n_clusters} playlists ✓")

    threading.Thread(target=_run, daemon=True).start()
