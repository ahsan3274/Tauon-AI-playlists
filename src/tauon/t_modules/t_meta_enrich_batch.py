"""
t_meta_enrich_batch.py — Batch Metadata Enrichment
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scans library for tracks with missing/poor metadata and enriches them.

What it fixes:
  1. Artist embedded in filename (e.g. "Apocalypse_-_Cigarettes_After_Sex_128k.mp3")
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
import os
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

# Split on common separators: " - ", " _ ", " - ", " | "
# Must match actual separators, NOT single underscores within words
_SEPARATOR_RE = re.compile(
    r'\s*(?:'
    r'_\s*-\s*_'         # _-_  (most common in messy downloads)
    r'|\s-\s'            # space-dash-space
    r'|\s_\s'            # space-underscore-space
    r'|__+'               # double+ underscore
    r'|--+'               # double+ dash
    r'|\s*[_\-–—|/~]{2,}\s*'  # 2+ separator chars
    r')'
)

# Noise words that commonly appear in titles
_TITLE_NOISE = re.compile(
    r'\s*(?:\(?(?:official|audio|music|video|lyric|lyrics|hd|hq|remix|edit|mix|version|full|extended|radio|clip)\s*\)?|'
    r'\d+k|kbps|mp3|flac|aac|ogg|m4a)\s*$',
    re.IGNORECASE
)

# Track number prefixes like "01. ", "1 - ", "01 - "
_TRACK_NUM_RE = re.compile(r'^\s*\d+[\.\s\-_]*')

# Words that look more like artist names (multi-word, proper nouns)
_ARTIST_INDICATORS = {
    'the ', 'a ', 'an ', 'after sex', 'cigarettes', 'black', 'saint',
    'pink', 'white', 'red', 'blue', 'green', 'gold', 'silver', 'iron',
    'rolling', 'dead', 'beatles', 'stones', 'queen', 'king', 'dark',
    'lana', 'del', 'rey', 'arctic', 'monkeys', 'weeknd', 'drake',
    'eminem', 'taylor', 'swift', 'kendrick', 'lamar', 'frank', 'ocean',
    'frank ocean', 'kanye', 'west', 'radiohead', 'coldplay', 'imagine',
    'dragons', 'one republic', 'maroon', '5', 'twenty one pilots',
    'panic', 'disco', 'fall out boy', 'my chemical romance', 'green day',
    'blink 182', 'sum 41', 'simple plan', 'good charlotte', 'new found glory',
    'sleeping at last', 'birdy', 'halsey', 'sia', 'adele', 'beyonce',
    'rihanna', 'nicki', 'minaj', 'cardi', 'b', 'doja', 'cat',
    'billie eilish', 'olivia rodrigo', 'sabrina carpenter', 'charli xcx',
    'dua lipa', 'ariana grande', 'selena gomez', 'shawn mendes',
    'the neighbourhood', 'alt j', 'foster the people', 'mgmt',
    'tame impala', 'gorillaz', 'daft punk', 'justice', 'massive attack',
    'portishead', 'tricky', 'bjork', 'björk', 'st vincent', 'fka twigs',
    'grimes', 'phoenix', 'm83', 'death grips', 'crystal castles',
    'lcd soundsystem', 'james blake', 'bon iver', 'fleet foxes',
    'iron & wine', 'sufjan stevens', 'ray la montagne', 'damien rice',
    'joni mitchell', 'neil young', 'bob dylan', 'leonard cohen',
    'tom waits', 'nick cave', 'johnny cash', 'willie nelson',
    'neighbourhood', 'lana del rey', 'cigarettes after sex',
    'weeknd', 'the weeknd',
}

# Words that look more like song titles
_TITLE_WORDS = {
    'love', 'heart', 'fire', 'rain', 'night', 'day', 'dream', 'sun',
    'moon', 'star', 'stars', 'sky', 'life', 'death', 'time', 'world', 'home',
    'run', 'fly', 'dance', 'sing', 'cry', 'laugh', 'fall', 'rise',
    'blue', 'red', 'black', 'white', 'gold', 'dark', 'light',
    'apocalypse', 'paradise', 'heaven', 'hell', 'ocean', 'river',
    'mountain', 'city', 'street', 'road', 'way', 'end', 'beginning',
    'feel', 'want', 'need', 'give', 'take', 'make', 'break', 'shake',
    'alone', 'together', 'forever', 'never', 'always', 'again', 'back',
    'up', 'down', 'out', 'in', 'over', 'under', 'through', 'around',
    'tonight', 'today', 'yesterday', 'tomorrow', 'morning', 'evening',
    'girl', 'boy', 'man', 'woman', 'baby', 'kid', 'child',
    'song', 'dance', 'music', 'sound', 'voice', 'silence', 'noise',
    'eyes', 'hands', 'face', 'body', 'soul', 'mind',
}

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

def clean_filename(raw: str) -> str:
    """
    Strip bitrate, extension, track numbers, and noise from a filename.

    "01. Apocalypse_-_Cigarettes_After_Sex_128k.mp3" → "Apocalypse_-_Cigarettes_After_Sex"
    """
    name = raw.rsplit(".", 1)[0] if "." in raw else raw
    name = _TRACK_NUM_RE.sub('', name)
    name = re.sub(r'[\s_]*(?:\d+k|kbps|hq|hd|lossless)\s*$', '', name, flags=re.IGNORECASE)
    return name.strip()


def split_parts(raw: str) -> tuple[str, str]:
    """Split on first separator. Returns (part1, part2) or (raw, "")."""
    parts = _SEPARATOR_RE.split(raw, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return raw, ""


def is_likely_artist(text: str) -> bool:
    """Heuristic: does this text look more like an artist name?"""
    if not text or len(text) < 2:
        return False

    lower = text.lower().strip()

    for indicator in _ARTIST_INDICATORS:
        if indicator in lower:
            return True

    # Multi-word (3+) strongly suggests artist
    if len(text.split()) >= 3:
        return True

    # Single common title word → probably a title, not artist
    if lower in _TITLE_WORDS:
        return False

    # Two words where first is "The", "A", etc. → artist
    words = lower.split()
    if len(words) == 2 and words[0] in ('the', 'a', 'an'):
        return True

    return False


def disambiguate_artist_title(part1: str, part2: str) -> tuple[str, str]:
    """
    Given two parts from a split, figure out which is artist and which is title.

    Strategy:
    1. Strong heuristic → use that
    2. Ambiguous → try both orderings with MusicBrainz, use the one that matches
    3. Fallback → first=artist (most common convention)
    """
    if not part1 or not part2:
        return part1 or "", part2 or ""

    p1_artist = is_likely_artist(part1)
    p2_artist = is_likely_artist(part2)

    if p1_artist and not p2_artist:
        # Sanity check: verify with MusicBrainz
        mb_result = _validate_with_musicbrainz(part1, part2)
        if mb_result:
            return mb_result
        return part1, part2
    elif p2_artist and not p1_artist:
        # Sanity check: verify with MusicBrainz
        mb_result = _validate_with_musicbrainz(part1, part2)
        if mb_result:
            return mb_result
        return part2, part1
    elif p1_artist and p2_artist:
        # Both look like artists — try MusicBrainz to disambiguate
        mb_result = _validate_with_musicbrainz(part1, part2)
        if mb_result:
            return mb_result
        # Fallback: longer is probably the artist
        if len(part1) >= len(part2):
            return part1, part2
        return part2, part1
    else:
        # Neither strongly looks like an artist — validate with MusicBrainz
        mb_result = _validate_with_musicbrainz(part1, part2)
        if mb_result:
            return mb_result
        # Default: first=artist, second=title
        return part1, part2


def _validate_with_musicbrainz(part1: str, part2: str) -> Optional[tuple[str, str]]:
    """
    Try both orderings with MusicBrainz and pick the correct one.

    The correct ordering is where the first result's artist matches the query artist.
    """
    for artist, title in [(part1, part2), (part2, part1)]:
        try:
            query = f'recording:{title} artist:"{artist}"'
            resp = requests.get(
                f"{MUSICBRAINZ_API}/recording/",
                params={"query": query, "fmt": "json", "limit": 3},
                headers={"User-Agent": MUSICBRAINZ_APP},
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                recs = data.get("recordings", [])
                if recs:
                    # Check if the first result's artist matches our query
                    first = recs[0]
                    credits = first.get("artist-credit", [])
                    if credits:
                        actual_artist = credits[0].get("name", "").lower()
                        query_artist = artist.lower()
                        # Check for match (allow partial - "weeknd" matches "the weeknd")
                        if query_artist in actual_artist or actual_artist in query_artist:
                            time.sleep(0.5)
                            return artist, title
            time.sleep(1.1)
        except Exception:
            pass
    return None


def parse_filename(filepath: str) -> tuple[str, str]:
    """
    Parse artist and title from a file path.

    Examples:
    - "Apocalypse_-_Cigarettes_After_Sex_128k.mp3" → ("Cigarettes After Sex", "Apocalypse")
    - "01. Victor_Ray_-_Falling_Into_Place.mp3" → ("Victor Ray", "Falling Into Place")
    - "Unknown_-_Song.mp3" → ("", "Song")
    """
    filename = os.path.basename(filepath)
    cleaned = clean_filename(filename)

    if not cleaned:
        return "", ""

    part1, part2 = split_parts(cleaned)

    if not part2:
        return "", part1

    # Convert underscores to spaces BEFORE disambiguation (for MusicBrainz queries)
    part1 = part1.replace('_', ' ').strip()
    part2 = part2.replace('_', ' ').strip()

    artist, title = disambiguate_artist_title(part1, part2)

    # Check if artist is actually "unknown"
    if artist.lower() in _UNKNOWN_ARTISTS:
        artist = ""

    return artist, title


def parse_artist_from_title(title: str) -> tuple[str, str]:
    """
    Try to extract artist and title from a combined title string.

    Handles:
    - "Artist - Title"
    - "Title - Artist" (reversed)

    Returns (artist, title). If no pattern matches, returns ("", original_title).
    """
    if not title or len(title) < 3:
        return "", title

    clean = _TITLE_NOISE.sub('', title).strip()

    parts = _SEPARATOR_RE.split(clean, maxsplit=1)
    if len(parts) != 2:
        return "", title

    part1, part2 = parts[0].strip(), parts[1].strip()
    if not part1 or not part2:
        return "", title

    artist, title_out = disambiguate_artist_title(part1, part2)

    if len(artist) < 2 or len(title_out) < 2:
        return "", title

    if artist.lower() in _UNKNOWN_ARTISTS:
        return "", title_out

    return artist, title_out


def clean_title(title: str) -> str:
    """Remove noise from a title string."""
    if not title:
        return ""
    cleaned = _TITLE_NOISE.sub('', title).strip()
    cleaned = re.sub(r'[\s_]*(?:\d+k|kbps|mp3|flac)\s*$', '', cleaned, flags=re.IGNORECASE).strip()
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
        query = f'recording:{title} artist:"{artist}"'
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

        rec = recordings[0]
        result = {"genre": None, "date": None, "album": None}

        releases = rec.get("releases", [])
        if releases:
            rel = releases[0]
            result["date"] = rel.get("date", "")[:4] or None
            result["album"] = rel.get("title", "")

        tags = rec.get("tags", [])
        if tags:
            tags.sort(key=lambda t: -t.get("count", 0))
            result["genre"] = tags[0].get("name", "").lower()

        time.sleep(REQUEST_DELAY)
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
    """
    results = []
    total = len(master_library)
    done = 0

    if progress_cb:
        progress_cb("Scanning library for tracks needing enrichment…", 0, total)

    for tid, track in master_library.items():
        done += 1
        result = EnrichmentResult(track_id=tid)

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
        # First try the title field
        parsed_artist, parsed_title = parse_artist_from_title(title)

        # If that didn't work, try the filename (this is where most messy data lives)
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
    """Run library enrichment with UI notifications."""
    def _run():
        if notify_fn:
            notify_fn("Enriching library metadata… (runs in background)")

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
