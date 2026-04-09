"""
t_yt_expand.py — YouTube Music Library Expansion
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Uses yt-dlp to search YouTube for recommended tracks and download them
as local audio files.

Workflow:
  1. Generate recommendations from existing sources (Last.fm, similarity, mood)
  2. Search YouTube for each recommendation
  3. Download audio as MP3/FLAC to ~/Music/Tauon-Downloads/
  4. Auto-import into Tauon library

Dependencies:
  pip install yt-dlp

Legal note: YouTube ToS restricts downloading content. This module
is intended for personal, offline listening only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("t_yt_expand")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_DOWNLOAD_DIR = Path.home() / "Music" / "Tauon-Downloads"
AUDIO_FORMAT = "mp3"  # mp3, flac, opus, m4a
AUDIO_QUALITY = "192K"  # For MP3: 128K, 192K, 320K
MAX_CONCURRENT = 2  # Max parallel downloads
YTDLP_TIMEOUT = 120  # Seconds per download


class DownloadStatus(str, Enum):
    PENDING = "pending"
    SEARCHING = "searching"
    DOWNLOADING = "downloading"
    IMPORTING = "importing"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"  # Already exists


@dataclass
class DownloadTask:
    artist: str
    title: str
    query: str = ""  # YouTube search query (auto-built if empty)
    status: DownloadStatus = DownloadStatus.PENDING
    youtube_url: str = ""
    youtube_title: str = ""
    local_path: str = ""
    error: str = ""
    progress: float = 0.0  # 0.0 - 1.0


@dataclass
class ExpandSession:
    """A single library expansion session."""
    tasks: list[DownloadTask] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: float = 0.0
    active: bool = False
    progress_cb: Optional[Callable] = None


# ─────────────────────────────────────────────────────────────────────────────
# yt-dlp Helpers
# ─────────────────────────────────────────────────────────────────────────────

def check_ytdlp() -> tuple[bool, str]:
    """Check if yt-dlp is available."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "yt-dlp returned non-zero exit code"
    except FileNotFoundError:
        return False, "yt-dlp not found. Install: brew install yt-dlp"
    except subprocess.TimeoutExpired:
        return False, "yt-dlp timed out"
    except Exception as e:
        return False, str(e)


def build_query(artist: str, title: str) -> str:
    """Build a YouTube search query from artist + title."""
    # Clean up common issues
    clean_artist = re.sub(r'\([^)]*\)', '', artist).strip()
    clean_title = re.sub(r'\([^)]*\)', '', title).strip()
    clean_title = re.sub(r'\[.*?\]', '', clean_title).strip()

    if clean_artist and clean_title:
        return f"{clean_artist} - {clean_title} official audio"
    elif clean_artist:
        return f"{clean_artist} full album"
    else:
        return clean_title or "music"


def search_youtube(query: str, timeout: int = YTDLP_TIMEOUT) -> list[dict]:
    """
    Search YouTube for a query and return top results.

    Returns list of dicts with: url, title, artist, duration, view_count
    """
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                f"ytsearch3:{query}",  # Top 3 results
                "--dump-json",
                "--no-download",
                "--flat-playlist",
                "--extractor-args", "youtube:player_client=web",
            ],
            capture_output=True, text=True, timeout=timeout
        )

        entries = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                info = json.loads(line)
                entries.append({
                    "url": f"https://youtube.com/watch?v={info.get('id', '')}",
                    "title": info.get("title", ""),
                    "artist": info.get("channel", ""),
                    "duration": info.get("duration", 0),
                    "view_count": info.get("view_count", 0),
                })
            except json.JSONDecodeError:
                continue

        return entries

    except subprocess.TimeoutExpired:
        log.error(f"YouTube search timed out for: {query}")
        return []
    except Exception as e:
        log.error(f"YouTube search failed: {e}")
        return []


def download_audio(
    url: str,
    output_dir: str,
    artist: str,
    title: str,
    progress_callback: Optional[Callable[[float], None]] = None,
    timeout: int = YTDLP_TIMEOUT,
) -> tuple[bool, str]:
    """
    Download audio from YouTube URL.

    Returns (success, local_path_or_error)
    """
    os.makedirs(output_dir, exist_ok=True)

    # Sanitize filename
    safe_artist = re.sub(r'[^\w\s-]', '', artist).strip()
    safe_title = re.sub(r'[^\w\s-]', '', title).strip()
    filename = f"{safe_artist} - {safe_title}.{AUDIO_FORMAT}"
    # Truncate if too long
    if len(filename) > 200:
        filename = filename[:200] + "." + AUDIO_FORMAT

    output_template = str(Path(output_dir) / filename)

    cmd = [
        "yt-dlp",
        url,
        "--extract-audio",
        "--audio-format", AUDIO_FORMAT,
        "--audio-quality", AUDIO_QUALITY,
        "--output", output_template,
        "--no-playlist",
        "--restrict-filenames",
        "--no-mtime",
        "--quiet",
        "--no-warnings",
        "--embed-thumbnail",
        "--embed-metadata",
        "--progress",
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Monitor progress
        start_time = time.time()
        while True:
            try:
                stdout, stderr = process.communicate(timeout=5)
                break
            except subprocess.TimeoutExpired:
                if process.poll() is not None:
                    break
                elapsed = time.time() - start_time
                # Heuristic progress (most downloads are 30-120s)
                progress = min(elapsed / 90.0, 0.95)
                if progress_callback:
                    progress_callback(progress)

        if process.returncode != 0:
            error_msg = stderr.strip()[-200:] if stderr else "unknown error"
            return False, f"yt-dlp exit {process.returncode}: {error_msg}"

        # Find the downloaded file
        for f in Path(output_dir).iterdir():
            if f.name.startswith(f"{safe_artist} - {safe_title}") and f.suffix == f".{AUDIO_FORMAT}":
                return True, str(f)

        # Fallback: find most recent file in output_dir
        recent = max(Path(output_dir).iterdir(), key=lambda p: p.stat().st_mtime, default=None)
        if recent and (time.time() - recent.stat().st_mtime) < 30:
            return True, str(recent)

        return False, "Download completed but file not found"

    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# Session Manager
# ─────────────────────────────────────────────────────────────────────────────

class ExpandManager:
    """Manages library expansion sessions."""

    def __init__(self, download_dir: str | None = None, max_concurrent: int = MAX_CONCURRENT):
        self.download_dir = download_dir or str(DEFAULT_DOWNLOAD_DIR)
        self.max_concurrent = max_concurrent
        self.session: Optional[ExpandSession] = None
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(max_concurrent)

    def start_session(
        self,
        tracks: list[tuple[str, str]],  # [(artist, title), ...]
        progress_cb: Optional[Callable] = None,
    ) -> ExpandSession:
        """
        Start a download session for a list of (artist, title) pairs.

        Returns immediately — downloads run in background.
        """
        with self._lock:
            if self.session and self.session.active:
                raise RuntimeError("A session is already active. Stop it first.")

            self.session = ExpandSession(
                tasks=[
                    DownloadTask(
                        artist=artist,
                        title=title,
                        query=build_query(artist, title),
                    )
                    for artist, title in tracks
                ],
                started_at=time.time(),
                active=True,
                progress_cb=progress_cb,
            )

        # Start background worker
        threading.Thread(target=self._run_session, daemon=True).start()
        return self.session

    def stop_session(self) -> None:
        """Stop the current session (marks remaining tasks as skipped)."""
        with self._lock:
            if self.session:
                self.session.active = False
                for task in self.session.tasks:
                    if task.status in (DownloadStatus.PENDING, DownloadStatus.SEARCHING):
                        task.status = DownloadStatus.SKIPPED

    def get_status(self) -> dict:
        """Get current session status."""
        with self._lock:
            if not self.session:
                return {"active": False, "total": 0}

            tasks = self.session.tasks
            total = len(tasks)
            complete = sum(1 for t in tasks if t.status == DownloadStatus.COMPLETE)
            failed = sum(1 for t in tasks if t.status == DownloadStatus.FAILED)
            pending = sum(1 for t in tasks if t.status == DownloadStatus.PENDING)
            downloading = sum(1 for t in tasks if t.status == DownloadStatus.DOWNLOADING)
            skipped = sum(1 for t in tasks if t.status == DownloadStatus.SKIPPED)

            return {
                "active": self.session.active,
                "total": total,
                "complete": complete,
                "failed": failed,
                "pending": pending,
                "downloading": downloading,
                "skipped": skipped,
                "tasks": [
                    {
                        "artist": t.artist,
                        "title": t.title,
                        "status": t.status.value,
                        "progress": t.progress,
                        "error": t.error,
                        "local_path": t.local_path,
                    }
                    for t in tasks
                ],
            }

    def _run_session(self) -> None:
        """Run all downloads in the session."""
        session = self.session
        if not session:
            return

        for task in session.tasks:
            if not session.active:
                break

            try:
                self._download_single(task)
            except Exception as e:
                task.status = DownloadStatus.FAILED
                task.error = str(e)
                log.error(f"Download failed for {task.artist} - {task.title}: {e}")

            if session.progress_cb:
                session.progress_cb(self.get_status())

        session.active = False
        session.completed_at = time.time()

    def _download_single(self, task: DownloadTask) -> None:
        """Download a single track."""
        # Check if file already exists
        existing = self._find_existing(task.artist, task.title)
        if existing:
            task.status = DownloadStatus.SKIPPED
            task.local_path = existing
            log.info(f"Skipping {task.artist} - {task.title}: already exists")
            return

        # Search YouTube
        task.status = DownloadStatus.SEARCHING
        log.info(f"Searching YouTube: {task.query}")
        results = search_youtube(task.query)

        if not results:
            task.status = DownloadStatus.FAILED
            task.error = "No YouTube results found"
            return

        # Pick best result (prefer longer tracks, avoid compilations)
        best = self._pick_best_result(results, task.artist, task.title)
        if not best:
            task.status = DownloadStatus.FAILED
            task.error = "No suitable result found"
            return

        task.youtube_url = best["url"]
        task.youtube_title = best["title"]

        # Download
        task.status = DownloadStatus.DOWNLOADING
        log.info(f"Downloading: {task.artist} - {task.title}")

        success, result = download_audio(
            best["url"],
            self.download_dir,
            task.artist,
            task.title,
            progress_callback=lambda p: setattr(task, 'progress', p),
        )

        if success:
            task.local_path = result
            task.status = DownloadStatus.COMPLETE
            task.progress = 1.0
            log.info(f"Downloaded: {task.artist} - {task.title} -> {result}")
        else:
            task.status = DownloadStatus.FAILED
            task.error = result

    def _pick_best_result(self, results: list[dict], artist: str, title: str) -> Optional[dict]:
        """
        Pick the best YouTube result.

        Prefers:
        1. Results containing artist name
        2. Results with "official" in title
        3. Longer duration (full track vs snippet)
        """
        artist_lower = artist.lower()
        title_lower = title.lower()

        scored = []
        for r in results:
            score = 0
            yt_title = r.get("title", "").lower()

            # Prefer results with artist name
            if artist_lower in yt_title:
                score += 10

            # Prefer results with track title
            if title_lower in yt_title:
                score += 5

            # Prefer official uploads / music videos
            if "official" in yt_title:
                score += 3
            if "music video" in yt_title:
                score += 2

            # Penalize very short tracks (likely snippets)
            duration = r.get("duration", 0)
            if duration > 180:  # > 3 min
                score += 2
            elif duration < 60:
                score -= 5

            # Penalize compilations / mixes
            for bad in ["mix", "compilation", "playlist", "full album"]:
                if bad in yt_title:
                    score -= 3

            scored.append((score, r))

        scored.sort(key=lambda x: -x[0])

        if scored and scored[0][0] > -5:
            return scored[0][1]
        return None

    def _find_existing(self, artist: str, title: str) -> Optional[str]:
        """Check if track already exists in download directory or library."""
        safe_title = re.sub(r'[^\w\s-]', '', title).strip().lower()

        for f in Path(self.download_dir).iterdir():
            fname_lower = f.name.lower()
            if safe_title in fname_lower and f.suffix == f".{AUDIO_FORMAT}":
                return str(f)

        return None


# ─────────────────────────────────────────────────────────────────────────────
# Global singleton
# ─────────────────────────────────────────────────────────────────────────────

_expand_manager: Optional[ExpandManager] = None


def get_expand_manager(download_dir: str | None = None) -> ExpandManager:
    global _expand_manager
    if _expand_manager is None:
        _expand_manager = ExpandManager(download_dir)
    return _expand_manager
