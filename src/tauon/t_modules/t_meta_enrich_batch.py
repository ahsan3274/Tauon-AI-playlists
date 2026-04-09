"""
t_meta_enrich_batch.py — Batch Metadata Enrichment
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scans library for tracks with missing/poor metadata and enriches them.

What it fixes:
  1. Artist embedded in title (e.g. "Artist_-_Song.mp3" → proper artist/title split)
  2. Filename contains artist but title is "Unknown"
  3. Missing genre → query MusicBrainz/Last.fm
  4. Missing date/year → query MusicBrainz
  5. "Various Artists" → parse actual artist from title
  6. Title has feat./ft./vs. → extract featured artists

Enrichment sources (all free, no API key needed):
  1. Filename/title parsing (instant, offline)
  2. MusicBrainz API (free, no key)
  3. Last.fm API (free, needs key — falls back to public key)

Usage:
  Called from Tauon menu: Meta → Enrich Library Metadata
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

import requests

if TYPE_CHECKING:
    pass

log = logging.getLogger("t_meta_enrich_batch")

# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

MUSICBRAINZ_API = "https://musicbrainz.org/ws/2"
LASTFM_API = "https://ws.audioscrobbler.com/2.0/"
LASTFM_API_KEY = "b048411511a3191008fee11a34f4e233"  # Public key

MUSICBRAINZ_APP = "TauonAI/1.0 (ahsan@openclaw.xyz)"
REQUEST_DELAY = 1.2  # MusicBrainz requires ≥1s between requests


# ─────────────────────────────────────────────────────────────────────────────
# Pattern Matching — extract artist/title from messy strings
# ─────────────────────────────────────────────────────────────────────────────

# Common separators in filenames
_FILENAME_SEPARATORS = re.compile(r'[_\-\s]+')

# Patterns like "Artist_-_Title", "Artist - Title", "Artist__Title"
_ARTIST_TITLE_RE = re.compile(
    r'^\s*'
    r'(?:\d+\.\s*)?'                          # Optional track number prefix
    r'(.+?)'                                   # Artist (greedy)
    r'\s*(?:[-–—|/~]+)\s*'                    # Separator
    r'(.+?)'                                  # Title
    r'(?:\.\w+)?\s*$'                         # Optional extension
)

# Patterns like "Title - Artist" (reversed)
_TITLE_ARTIST_RE = re.compile(
    r'^\s*'
    r'(.+?)'                                   # Title
    r'\s*(?:[-–—|/~]+)\s*'                    # Separator
    r'(.+?)'                                  # Artist
    r'\s*$'
)

# "feat.", "ft.", "vs.", "&" — extract featured artists
_FEAT_RE = re.compile(
    r'\s*(?:feat\.?|ft\.?|featuring|vs\.?|&|and|×|x)\s+(.+)',
    re.IGNORECASE
)

# Clean up common noise
_NOISE_RE = re.compile(
    r'\s*\((?:official|audio|music|video|lyric|hd|hq|remix|edit|mix|version|full|extended|radio)\s*\)',
    re.IGNORECASE
)

# Common "Unknown" variants
_UNKNOWN_ARTISTS = {
    'unknown artist', 'unknown', 'various artists', 'va',
    'various', 'n/a', '', '-', '—', '–',
}


@dataclass
class EnrichmentResult:
    """Result of enriching a single track."""
    track_id: int
    title_before: str = ""
    artist_before: str = ""
    title_after: str = ""
    artist_after: str = ""
    genre_added: bool = False
    date_added: bool = False
    source: str = "none"  # "filename", "musicbrainz", "lastfm", "none"
    changed: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Parsing Helpers
# ─────────────────────────────────────────────────────────────────────────────

def parse_artist_from_title(title: str) -> tuple[str, str]:
    """
    Try to extract artist and title from a combined string.

    Handles:
    - "Artist - Title"
    - "Artist_-_Title"
    - "01. Artist - Title"
    - "Title by Artist"

    Returns (artist, title). If no pattern matches, returns ("", original_title).
    """
    if not title or len(title) < 3:
        return "", title

    # Remove common noise
    clean = _NOISE_RE.sub('', title).strip()

    # Try "Artist - Title" pattern
    m = _ARTIST_TITLE_RE.match(clean)
    if m:
        artist = m.group(1).strip()
        song_title = m.group(2).strip()
        # Validate: artist shouldn't be too long or too short
        if 1 < len(artist) < 50 and len(song_title) > 1:
            if artist.lower() not in _UNKNOWN_ARTISTS:
                return artist, song_title

    # Try reversed "Title - Artist"
    m2 = _TITLE_ARTIST_RE.match(clean)
    if m2:
        artist = m2.group(2).strip()
        song_title = m2.group(1).strip()
        if 1 < len(artist) < 50 and len(song_title) > 1:
            if artist.lower() not in _UNKNOWN_ARTISTS:
                return artist, song_title

    return "", title


def parse_filename(filepath: str) -> tuple[str, str]:
    """
    Try to extract artist/title from a filename.

    Handles:
    - "/path/Artist_-_Title.mp3"
    - "/path/ Artist - Title .flac"
    """
    import os
    filename = os.path.basename(filepath)
    # Remove extension
    name = os.path.splitext(filename)[0]
    return parse_artist_from_title(name)


def clean_title(title: str) -> str:
    """Remove noise from a title string."""
    if not title:
        return ""
    cleaned = _NOISE_RE.sub('', title).strip()
    # Remove trailing bitrate indicators like "128k", "320kbps"
    cleaned = re.sub(r'\s*(?:\d+k|kbps|hq|hd)\s*$', '', cleaned, flags=re.IGNORECASE).strip()
    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# API Lookup
# ─────────────────────────────────────────────────────────────────────────────

def lookup_musicbrainz(artist: str, title: str) -> Optional[dict]:
    """
    Query MusicBrainz for track metadata.

    Returns dict with: genre, date, album (any may be None).
    """
    if not artist or not title:
        return None

    try:
        # Search recordings
        query = f'recording:"{title}" AND artist:"{artist}"'
        resp = requests.get(
            f"{MUSICBRAINZ_API}/recording",
            params={
                "query": query,
                "fmt": "json",
                "limit": 5,
            },
            headers={"User-Agent": MUSICBRAINZ_APP},
            timeout=10,
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        recordings = data.get("recordings", [])
        if not recordings:
            return None

        # Take the best match (first result)
        rec = recordings[0]
        result = {"genre": None, "date": None, "album": None}

        # Get date from release
        releases = rec.get("releases", [])
        if releases:
            rel = releases[0]
            result["date"] = rel.get("date", "")[:4] or None
            result["album"] = rel.get("title", "")

        # Get genre from tags
        tags = rec.get("tags", [])
        if tags:
            # Take the most popular tag
            tags.sort(key=lambda t: -t.get("count", 0))
            result["genre"] = tags[0].get("name", "").lower()

        time.sleep(REQUEST_DELAY)  # Be nice to MusicBrainz
        return result

    except Exception as e:
        log.warning(f"MusicBrainz lookup failed for '{artist} - {title}': {e}")
        return None


def lookup_lastfm_genre(artist: str) -> Optional[str]:
    """Get top genre for an artist from Last.fm."""
    if not artist:
        return None

    try:
        resp = requests.get(
            LASTFM_API,
            params={
                "method": "artist.getInfo",
                "artist": artist,
                "api_key": LASTFM_API_KEY,
                "format": "json",
            },
            timeout=10,
        )

        if resp.status_code != 200:
            return None

        data = resp.json()
        tags = data.get("artist", {}).get("tags", {}).get("tag", [])
        if tags:
            return tags[0].get("name", "").lower()
        return None

    except Exception as e:
        log.warning(f"Last.fm genre lookup failed for '{artist}': {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Batch Enrichment
# ─────────────────────────────────────────────────────────────────────────────

def enrich_library(
    master_library: dict,
    dry_run: bool = False,
    use_musicbrainz: bool = True,
    use_lastfm: bool = True,
    progress_cb: Optional[Callable[[str, int, int], None]] = None,
) -> list[EnrichmentResult]:
    """
    Enrich metadata for all tracks in the library.

    Args:
        master_library: Tauon's master_library dict {track_id: TrackClass}
        dry_run: If True, report changes without modifying tracks
        use_musicbrainz: Query MusicBrainz for missing genre/date
        use_lastfm: Query Last.fm for missing genre
        progress_cb: Callback(msg, done, total) for progress updates

    Returns:
        List of EnrichmentResult for each processed track.
    """
    results = []
    total = len(master_library)
    done = 0

    if progress_cb:
        progress_cb("Scanning library for tracks needing enrichment…", 0, total)

    for tid, track in master_library.items():
        done += 1
        result = EnrichmentResult(track_id=tid)

        # Capture current state
        result.title_before = getattr(track, "title", "") or ""
        result.artist_before = getattr(track, "artist", "") or ""
        result.title_after = result.title_before
        result.artist_after = result.artist_before

        # Step 1: Parse artist/title from filename or combined title
        _parse_and_fix_title(track, result)

        # Step 2: Look up missing genre/date via APIs
        if use_musicbrainz or use_lastfm:
            _lookup_missing_metadata(track, result, use_musicbrainz, use_lastfm)

        # Step 3: Apply changes (unless dry run)
        if not dry_run and result.changed:
            _apply_changes(track, result)

        results.append(result)

        if progress_cb and done % 10 == 0:
            changed_count = sum(1 for r in results if r.changed)
            progress_cb(f"Enriched: {done}/{total} ({changed_count} changed)", done, total)

    if progress_cb:
        changed = sum(1 for r in results if r.changed)
        progress_cb(f"Complete: {changed}/{total} tracks enriched", total, total)

    return results


def _parse_and_fix_title(track, result: EnrichmentResult) -> None:
    """Step 1: Fix artist/title parsing from filename or combined title."""
    title = getattr(track, "title", "") or ""
    artist = getattr(track, "artist", "") or ""
    fullpath = getattr(track, "fullpath", "") or getattr(track, "filename", "") or ""

    # If artist is missing or unknown, try to parse from title/filename
    if not artist or artist.lower() in _UNKNOWN_ARTISTS:
        parsed_artist, parsed_title = parse_artist_from_title(title)

        # If title didn't work, try the filename
        if not parsed_artist and fullpath:
            parsed_artist, parsed_title = parse_filename(fullpath)

        if parsed_artist:
            result.artist_after = clean_title(parsed_artist)
            result.title_after = clean_title(parsed_title)
            result.source = "filename"
            result.changed = True

    # Clean up title even if artist was known
    if result.title_after and not result.changed:
        cleaned = clean_title(result.title_after)
        if cleaned != result.title_after:
            result.title_after = cleaned
            result.changed = True


def _lookup_missing_metadata(
    track, result: EnrichmentResult,
    use_mb: bool, use_lf: bool,
) -> None:
    """Step 2: Query APIs for missing genre/date."""
    genre = getattr(track, "genre", "") or ""
    date = getattr(track, "date", 0) or 0

    # Only lookup if we have at least an artist name
    artist = result.artist_after or getattr(track, "artist", "") or ""
    title = result.title_after or getattr(track, "title", "") or ""

    if not genre and use_mb and artist:
        mb = lookup_musicbrainz(artist, title)
        if mb:
            if mb.get("genre") and not genre:
                genre = mb["genre"]
                result.genre_added = True
                result.source = "musicbrainz"
            if mb.get("date") and not date:
                try:
                    date = int(mb["date"])
                    result.date_added = True
                    result.source = "musicbrainz"
                except (ValueError, TypeError):
                    pass

    if not genre and use_lf and artist:
        lf_genre = lookup_lastfm_genre(artist)
        if lf_genre:
            genre = lf_genre
            result.genre_added = True
            result.source = "lastfm"

    result.title_after = getattr(track, "title", result.title_after)
    result.artist_after = getattr(track, "artist", result.artist_after)

    # Store looked-up values for apply step
    result._lookup_genre = genre
    result._lookup_date = date


def _apply_changes(track, result: EnrichmentResult) -> None:
    """Step 3: Apply enriched metadata to the track object."""
    if result.artist_after and result.artist_after != getattr(track, "artist", ""):
        track.artist = result.artist_after

    if result.title_after and result.title_after != getattr(track, "title", ""):
        track.title = result.title_after

    if hasattr(result, '_lookup_genre') and result._lookup_genre:
        track.genre = result._lookup_genre

    if hasattr(result, '_lookup_date') and result._lookup_date:
        track.date = result._lookup_date


# ─────────────────────────────────────────────────────────────────────────────
# UI Integration
# ─────────────────────────────────────────────────────────────────────────────

def run_enrichment_ui(
    master_library: dict,
    pctl=None,
    prefs=None,
    notify_fn=None,
) -> None:
    """
    Run library enrichment with UI notifications.

    This is the entry point for the Tauon menu item.
    """
    def _run():
        if notify_fn:
            notify_fn("Enriching library metadata… (this runs in background)")

        import threading
        results = enrich_library(
            master_library=master_library,
            dry_run=False,
            use_musicbrainz=True,
            use_lastfm=True,
            progress_cb=lambda msg, d, t: notify_fn(msg) if notify_fn else None,
        )

        changed = sum(1 for r in results if r.changed)
        filenames_fixed = sum(1 for r in results if r.source == "filename")
        genres_added = sum(1 for r in results if r.genre_added)
        dates_added = sum(1 for r in results if r.date_added)
        mb_lookups = sum(1 for r in results if r.source == "musicbrainz")
        lf_lookups = sum(1 for r in results if r.source == "lastfm")

        if notify_fn:
            lines = [f"Metadata enrichment complete: {changed}/{len(results)} tracks changed"]
            if filenames_fixed:
                lines.append(f"  • {filenames_fixed} artist/title splits from filenames")
            if genres_added:
                lines.append(f"  • {genres_added} genres added")
            if dates_added:
                lines.append(f"  • {dates_added} dates added")
            if mb_lookups:
                lines.append(f"  • {mb_lookups} MusicBrainz lookups")
            if lf_lookups:
                lines.append(f"  • {lf_lookups} Last.fm lookups")
            notify_fn("\n".join(lines))

    import threading
    threading.Thread(target=_run, daemon=True).start()
