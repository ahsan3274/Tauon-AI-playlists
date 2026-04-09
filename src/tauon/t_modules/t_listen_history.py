"""
t_listen_history.py — Listening History Tracker
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Records every track play event with metadata, audio features, and queue source.
Append-only JSONL format — one JSON object per line.

Storage: ~/.local/share/TauonMusicBox/listen_history.jsonl
         ~/.local/share/TauonMusicBox/listen_history_stats.json (cached stats)

Design:
  - Zero external API calls
  - Minimal performance impact (async write, <1ms)
  - Rich metadata for recommendation analysis
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

log = logging.getLogger("t_listen_history")


class QueueSource(str, Enum):
    MANUAL = "manual"           # User clicked/pressed play
    AUTOPLAY = "autoplay"       # t_autoplay.py queued it
    SIMILARITY_RADIO = "similarity_radio"  # t_playlist_gen_v2.py
    SHUFFLE = "shuffle"         # True shuffle mode
    REPEAT = "repeat"           # Repeat track/album
    NORMAL_QUEUE = "normal"     # Sequential playlist playback
    RADIO = "radio"             # Internet radio stream


class ListenHistory:
    def __init__(self, data_dir: str | None = None):
        self.data_dir = data_dir or os.path.expanduser("~/.local/share/TauonMusicBox")
        self.history_file = os.path.join(self.data_dir, "listen_history.jsonl")
        self.enabled = False
        self._lock = threading.Lock()

        # Track how the current queue was populated
        self._queue_source = QueueSource.NORMAL_QUEUE
        self._seed_track_id: int | None = None  # For autoplay/similarity radio
        self._seed_track_title: str = ""

    def ensure_dir(self) -> None:
        """Create data directory if it doesn't exist."""
        os.makedirs(self.data_dir, exist_ok=True)

    def set_queue_source(self, source: QueueSource, seed_track_id: int | None = None, seed_title: str = "") -> None:
        """Tag the current queue with its source (called when queue is built)."""
        self._queue_source = source
        self._seed_track_id = seed_track_id
        self._seed_track_title = seed_title

    def log_play(self, track: Any, audio_features: dict | None = None, play_duration: float | None = None) -> None:
        """
        Record a track play event. Called when playback starts or ends.

        Args:
            track: TrackClass object from master_library
            audio_features: Pre-computed features from audio features cache
            play_duration: How long the track played (seconds) — set on track end
        """
        if not self.enabled:
            return

        try:
            entry = self._build_entry(track, audio_features, play_duration)
            self._write_entry(entry)
        except Exception:
            log.exception("Failed to write listen history entry")

    def _build_entry(self, track: Any, audio_features: dict | None = None, play_duration: float | None = None) -> dict:
        """Build a history entry from track data."""
        now = datetime.now(timezone.utc)

        # Extract metadata from track object
        entry: dict[str, Any] = {
            "ts": now.isoformat(),
            "ts_epoch": now.timestamp(),
            "source": self._queue_source.value,
            "artist": getattr(track, "artist", "") or "",
            "title": getattr(track, "title", "") or "",
            "album": getattr(track, "album", "") or "",
            "genre": getattr(track, "genre", "") or "",
            "date": getattr(track, "date", 0) or 0,
            "duration": getattr(track, "length", 0) or 0,
            "track_id": getattr(track, "index", -1),
            "file_path": getattr(track, "fullpath", "") or "",
            "parent_folder": getattr(track, "parent_folder_path", "") or "",
            "file_ext": getattr(track, "file_ext", "") or "",
        }

        # Seed track reference (for similarity radio / autoplay)
        if self._seed_track_id is not None:
            entry["seed_track_id"] = self._seed_track_id
            entry["seed_track_title"] = self._seed_track_title

        # Play duration (if this is a track-end log)
        if play_duration is not None:
            entry["play_duration"] = round(play_duration, 1)
            # Calculate completion rate (1.0 = listened fully)
            if entry["duration"] and entry["duration"] > 0:
                entry["completion"] = round(min(play_duration / entry["duration"], 1.0), 3)

        # Audio features
        if audio_features:
            entry["audio_features"] = {
                "energy": audio_features.get("energy"),
                "valence": audio_features.get("valence"),
                "danceability": audio_features.get("danceability"),
                "acousticness": audio_features.get("acousticness"),
                "tempo": audio_features.get("tempo"),
                "loudness": audio_features.get("loudness"),
                "mood_scores": audio_features.get("mood_scores"),
                "top_mood": audio_features.get("top_mood"),
                "source_type": audio_features.get("source"),  # "metadata" or "spotify"
            }

        return entry

    def _write_entry(self, entry: dict) -> None:
        """Append entry to JSONL file (thread-safe)."""
        self.ensure_dir()
        with self._lock:
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_entries(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Read recent entries (newest first)."""
        if not os.path.exists(self.history_file):
            return []

        with self._lock:
            with open(self.history_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

        # Reverse for newest-first, apply offset and limit
        lines = lines[::-1][offset:offset + limit]
        return [json.loads(line) for line in lines if line.strip()]

    def count_entries(self) -> int:
        """Total number of recorded plays."""
        if not os.path.exists(self.history_file):
            return 0
        with self._lock:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())

    def get_stats(self) -> dict:
        """Generate summary statistics from history."""
        if not os.path.exists(self.history_file):
            return {"total_plays": 0, "message": "No history recorded"}

        with self._lock:
            with open(self.history_file, "r", encoding="utf-8") as f:
                entries = [json.loads(line) for line in f if line.strip()]

        if not entries:
            return {"total_plays": 0, "message": "No history recorded"}

        stats: dict[str, Any] = {
            "total_plays": len(entries),
            "total_hours": round(sum(e.get("play_duration", e.get("duration", 0)) for e in entries) / 3600, 1),
            "unique_tracks": len({e.get("track_id") for e in entries}),
            "unique_artists": len({e.get("artist") for e in entries if e.get("artist")}),
            "unique_albums": len({e.get("album") for e in entries if e.get("album")}),
        }

        # Queue source distribution
        source_counts: dict[str, int] = {}
        for e in entries:
            src = e.get("source", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1
        stats["source_distribution"] = source_counts

        # Top genres
        genre_counts: dict[str, int] = {}
        for e in entries:
            g = e.get("genre", "").strip()
            if g:
                genre_counts[g] = genre_counts.get(g, 0) + 1
        stats["top_genres"] = sorted(genre_counts.items(), key=lambda x: -x[1])[:10]

        # Top artists
        artist_counts: dict[str, int] = {}
        for e in entries:
            a = e.get("artist", "").strip()
            if a:
                artist_counts[a] = artist_counts.get(a, 0) + 1
        stats["top_artists"] = sorted(artist_counts.items(), key=lambda x: -x[1])[:10]

        # Audio feature averages (only for entries with features)
        feature_entries = [e for e in entries if e.get("audio_features")]
        if feature_entries:
            af_stats: dict[str, float] = {}
            for key in ["energy", "valence", "danceability", "acousticness", "tempo"]:
                vals = [e["audio_features"].get(key) for e in feature_entries if e["audio_features"].get(key) is not None]
                if vals:
                    af_stats[f"avg_{key}"] = round(sum(vals) / len(vals), 3)
                    af_stats[f"min_{key}"] = round(min(vals), 3)
                    af_stats[f"max_{key}"] = round(max(vals), 3)
            stats["audio_features"] = af_stats

            # Mood distribution
            mood_counts: dict[str, int] = {}
            for e in feature_entries:
                mood = e.get("audio_features", {}).get("top_mood")
                if mood:
                    mood_counts[mood] = mood_counts.get(mood, 0) + 1
            stats["mood_distribution"] = sorted(mood_counts.items(), key=lambda x: -x[1])

            # Completion rate (skip vs listen)
            completions = [e.get("completion") for e in entries if e.get("completion") is not None]
            if completions:
                avg_completion = sum(completions) / len(completions)
                skipped = sum(1 for c in completions if c < 0.3)
                stats["avg_completion_rate"] = round(avg_completion, 3)
                stats["skip_rate"] = round(skipped / len(completions), 3)

        return stats


# ── Global singleton ─────────────────────────────────────────────────────────

_history: ListenHistory | None = None


def get_listen_history() -> ListenHistory:
    """Get or create the global listen history tracker."""
    global _history
    if _history is None:
        _history = ListenHistory()
    return _history


def get_global_history(data_dir: str | None = None) -> ListenHistory:
    """Initialize with data directory (call once at startup)."""
    global _history
    _history = ListenHistory(data_dir)
    return _history
