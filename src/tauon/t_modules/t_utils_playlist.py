"""
t_utils_playlist.py - Shared Playlist Utilities
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Shared utility functions for playlist generation.
Eliminates code duplication across t_playlist_gen modules.
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

log = logging.getLogger("t_utils_playlist")


# ─────────────────────────────────────────────────────────────────────────────
# Core Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_library_tracks(pctl, master_library) -> list[dict]:
    """
    Get all tracks from library.

    Returns a list of dicts with essential track info:
    {id, path, title, artist, album, genre, year, play_count, duration, bpm, mode, loudness, misc}

    This is a shared utility to avoid duplication across playlist generators.
    """
    # Collect all track IDs from master_library
    # Don't filter by playlist membership - use entire library
    tracks = []
    for tid, tr in master_library.items():
        sc = getattr(tr, 'play_count', 0) or 0
        duration = getattr(tr, 'length', 0) or 0

        # Get misc dict if it exists
        misc_dict = dict(getattr(tr, 'misc', {})) if hasattr(tr, 'misc') else {}

        # Get path - use "fullpath" key for cache compatibility
        fullpath = getattr(tr, "fullpath", "") or getattr(tr, "filename", "")

        tracks.append({
            "id":         tid,
            "fullpath":   fullpath,  # Use "fullpath" for cache compatibility
            "path":       fullpath,  # Also keep "path" for backwards compatibility
            "title":      getattr(tr, "title",  "") or "",
            "artist":     getattr(tr, "artist", "") or "",
            "album":      getattr(tr, "album",  "") or "",
            "genre":      getattr(tr, "genre",  "") or "",
            "year":       str(getattr(tr, "date", "") or "")[:4],
            "play_count": sc,
            "duration":   duration,
            # Audio features metadata (for get_metadata_features)
            "bpm":        misc_dict.get('bpm', 0) or getattr(tr, 'bpm', 0) or misc_dict.get('BPM', 0) or 0,
            "mode":       misc_dict.get('mode', None) or getattr(tr, 'mode', None),
            "loudness":   misc_dict.get('replaygain_track_gain', None) or misc_dict.get('loudness', None),
            "misc":       misc_dict,
        })

    return tracks


def create_playlist(name: str, track_ids: list[int], pctl) -> int:
    """
    Create a new playlist and append to Tauon's playlist list.

    Args:
        name: Playlist name
        track_ids: List of track IDs to include
        pctl: Player controller instance

    Returns:
        Index of created playlist, or -1 on failure
    """
    try:
        from tauon.t_modules.t_main import TauonPlaylist
        from tauon.t_modules.t_extra import uid_gen
        uid = uid_gen()
    except ImportError:
        # Fallback: create minimal playlist object
        import random
        class MinimalPlaylist:
            def __init__(self, title, playlist_ids):
                self.title = title
                self.playlist_ids = playlist_ids
                self.playing = 0
                self.position = 0
                self.hide_title = False
                self.selected = 0
                self.uuid_int = random.randint(100000, 999999)
                self.last_folder = []
                self.hidden = False
                self.locked = False
                self.parent_playlist_id = 0
                self.persist_time_positioning = False
                self.playlist_file = ""
                self.auto_export = False
                self.auto_import = False
                self.export_type = "xspf"
                self.relative_export = False
                self.file_size = 0
        
        pl = MinimalPlaylist(name, track_ids[:])
        pctl.multi_playlist.append(pl)
        log.info("Created playlist '%s' with %d tracks (fallback)", name, len(track_ids))
        return len(pctl.multi_playlist) - 1
    except Exception as e:
        log.error(f"Failed to create playlist '{name}': {e}")
        return -1

    # Create TauonPlaylist with all required fields
    pl = TauonPlaylist(
        title=name,
        playing=0,
        playlist_ids=track_ids[:],  # Copy the list
        position=0,
        hide_title=False,
        selected=0,
        uuid_int=uid,
        last_folder=[],
        hidden=False,
        locked=False,
        parent_playlist_id=0,
        persist_time_positioning=False,
    )
    pctl.multi_playlist.append(pl)
    log.info("Created playlist '%s' with %d tracks", name, len(track_ids))
    return len(pctl.multi_playlist) - 1


# ─────────────────────────────────────────────────────────────────────────────
# Error Handling Decorator
# ─────────────────────────────────────────────────────────────────────────────

def handle_playlist_errors(func):
    """
    Decorator to handle playlist generation errors gracefully.
    
    Catches exceptions, logs them, and shows user-friendly error messages.
    
    Usage:
        @handle_playlist_errors
        def generate_mood_playlists(...):
            ...
    """
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log.error(f"Playlist generation failed in {func.__name__}: {e}", exc_info=True)
            
            # Try to get notify_fn from kwargs or args
            notify_fn = kwargs.get('notify_fn')
            if not notify_fn and len(args) > 0:
                # notify_fn is usually one of the last args
                for arg in reversed(args):
                    if callable(arg) and 'notify' in str(arg):
                        notify_fn = arg
                        break
            
            if notify_fn:
                error_msg = str(e)[:100]  # Truncate long errors
                notify_fn(f"Playlist error: {error_msg}")
            
            return None
    
    return wrapper


# ─────────────────────────────────────────────────────────────────────────────
# Artist Matching Utilities
# ─────────────────────────────────────────────────────────────────────────────

def normalize_artist_name(artist_name: str) -> str:
    """
    Normalize artist name for better matching.
    
    - Lowercase and strip
    - Remove common prefixes (the, a, an)
    - Remove collaboration indicators (feat., ft., &, etc.)
    - Remove parentheses content
    """
    # Lowercase and strip
    name = artist_name.lower().strip()
    
    # Remove common prefixes
    for prefix in ['the ', 'a ', 'an ']:
        if name.startswith(prefix):
            name = name[len(prefix):]
    
    # Remove common collaboration indicators and everything after
    for sep in [' feat.', ' feat ', ' ft.', ' ft ', ' vs.', ' vs ', ' & ', ' and ', ' x ', ' × ', ' with ']:
        if sep in name:
            name = name.split(sep)[0].strip()
    
    # Remove parentheses and content within (common for feat. in parentheses)
    import re
    name = re.sub(r'\s*\([^)]*\)', '', name)
    
    # Remove extra whitespace
    name = ' '.join(name.split())
    
    return name


def extract_all_artists(artist_field: str) -> list[str]:
    """
    Extract all artist names from a collaboration field.
    
    Handles: "Artist A feat. Artist B", "Artist A & Artist B", etc.
    """
    artists = []
    
    # First, try splitting by common collaboration separators
    separators = [' feat.', ' feat ', ' ft.', ' ft ', ' vs.', ' vs ', ' & ', ' and ', ' x ', ' × ', ' with ']
    
    parts = [artist_field]
    for sep in separators:
        new_parts = []
        for part in parts:
            new_parts.extend(part.split(sep))
        parts = new_parts
    
    # Clean each part
    for part in parts:
        part = part.strip()
        if part:
            # Remove parentheses and content within
            import re
            part = re.sub(r'\s*\([^)]*\)', '', part)
            part = part.strip()
            if part:
                artists.append(part)
    
    # Also add the full normalized artist field
    normalized_full = normalize_artist_name(artist_field)
    if normalized_full and normalized_full not in artists:
        artists.append(normalized_full)
    
    return artists


def artist_matches(artist_field: str, similar_artists: set[str]) -> bool:
    """
    Check if any similar artist appears in the track's artist field.
    
    Handles collaborations like "Artist A feat. Artist B" or "Artist A & Artist B".
    
    Improved matching:
    1. Normalize both similar artists and track artists
    2. Extract all artists from collaboration fields
    3. Check for partial matches and word overlap
    """
    if not artist_field:
        return False
    
    # Normalize all similar artists for comparison
    normalized_similar = set()
    for similar in similar_artists:
        normalized_similar.add(normalize_artist_name(similar))
        normalized_similar.add(similar.lower().strip())
    
    # Extract all artists from the track's artist field
    track_artists = extract_all_artists(artist_field)
    
    # Check each extracted artist
    for track_artist in track_artists:
        normalized_track = normalize_artist_name(track_artist)
        
        # Direct match
        if normalized_track in normalized_similar:
            return True
        
        # Check if track artist matches any similar artist
        if track_artist.lower().strip() in normalized_similar:
            return True
        
        # Check word overlap (handles "The Strokes" vs "strokes")
        track_words = set(normalized_track.split())
        for similar in normalized_similar:
            similar_words = set(similar.split())
            # If they share significant words
            if len(track_words & similar_words) >= 1:
                if len(track_words) <= 3 or len(similar_words) <= 3:
                    return True
        
        # Check if any similar artist is contained in track artist or vice versa
        for similar in normalized_similar:
            if similar and len(similar) > 3:  # Avoid matching tiny strings
                if similar in normalized_track or normalized_track in similar:
                    # But make sure it's not a tiny substring
                    if len(similar) >= len(normalized_track) * 0.5 or len(normalized_track) >= len(similar) * 0.5:
                        return True
    
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Playlist generation thresholds
MOOD_THRESHOLD = 0.6
MIN_TRACKS_PER_PLAYLIST = 5
MAX_SIMILARITY_RESULTS = 50
DEFAULT_PLAYLIST_LIMIT = 50

# Audio feature ranges
DEFAULT_TEMPO = 120.0
TEMPO_MAX = 200.0
LOUDNESS_MIN = -60.0
LOUDNESS_MAX = 0.0

# Menu constants
MENU_WIDTH = 160
SUBMENU_WIDTH = 200
ICON_SIZE = 24
