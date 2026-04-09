"""
t_spotify_discover.py — Spotify-Powered Music Discovery for Magic Radio
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Workflow:
  1. Magic Radio analyzes current track (local metadata)
  2. Queries Spotify API for similar/recommended tracks
  3. Checks which recommendations exist in local library
  4. Plays local matches immediately
  5. Queues "discoveries" (not in library) with download option
  6. User saves discoveries → downloads via YouTube → adds to library

Spotify API capabilities:
  ✅ Search tracks/artists
  ✅ Get related artists
  ✅ Get artist top tracks
  ❌ Recommendations endpoint (broken since late 2024)
  ❌ Audio streaming (DRM-protected)
  ❌ Full audio download (DRM-protected)

Fallback: If no Spotify auth, use Last.fm API for similar artists.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

log = logging.getLogger("t_spotify_discover")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

LASTFM_API = "https://ws.audioscrobbler.com/2.0/"
SPOTIFY_API = "https://api.spotify.com/v1"
LASTFM_API_KEY = "b048411511a3191008fee11a34f4e233"  # Public key

MAX_RECOMMENDATIONS = 20  # Number of Spotify recommendations per seed
MAX_LASTFM_ARTISTS = 15  # Number of similar artists from Last.fm


@dataclass
class DiscoveryTrack:
    """A track recommended by Spotify/Last.fm but not in local library."""
    artist: str
    title: str
    album: str = ""
    spotify_id: str = ""
    preview_url: str = ""  # Deprecated but sometimes available
    duration_ms: int = 0
    yt_query: str = ""
    downloaded: bool = False
    local_path: str = ""
    saved_at: float = 0.0


@dataclass
class DiscoverySession:
    """Current discovery session state."""
    seed_artist: str = ""
    seed_title: str = ""
    recommendations: list[DiscoveryTrack] = field(default_factory=list)
    local_matches: list[dict] = field(default_factory=list)  # Track IDs in library
    source: str = "unknown"  # "spotify" or "lastfm"
    created_at: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Spotify API Client
# ─────────────────────────────────────────────────────────────────────────────

class SpotifyClient:
    """Minimal Spotify API client for discovery."""

    def __init__(self, token: str = ""):
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    def is_authenticated(self) -> bool:
        return bool(self.token)

    def search_track(self, artist: str, title: str) -> Optional[dict]:
        """Search for a specific track on Spotify."""
        try:
            query = f"{artist} {title}"
            resp = self.session.get(
                f"{SPOTIFY_API}/search",
                params={"q": query, "type": "track", "limit": 5},
                timeout=10,
            )
            if resp.status_code == 200:
                tracks = resp.json().get("tracks", {}).get("items", [])
                if tracks:
                    return tracks[0]
        except Exception as e:
            log.error(f"Spotify search failed: {e}")
        return None

    def get_artist_id(self, artist_name: str) -> Optional[str]:
        """Get Spotify artist ID by name."""
        try:
            resp = self.session.get(
                f"{SPOTIFY_API}/search",
                params={"q": artist_name, "type": "artist", "limit": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                artists = resp.json().get("artists", {}).get("items", [])
                if artists:
                    return artists[0]["id"]
        except Exception as e:
            log.error(f"Spotify artist search failed: {e}")
        return None

    def get_related_artists(self, artist_id: str) -> list[str]:
        """Get related artist names from Spotify."""
        try:
            resp = self.session.get(
                f"{SPOTIFY_API}/artists/{artist_id}/related-artists",
                timeout=10,
            )
            if resp.status_code == 200:
                artists = resp.json().get("artists", [])
                return [a["name"] for a in artists[:MAX_LASTFM_ARTISTS]]
        except Exception as e:
            log.error(f"Spotify related artists failed: {e}")
        return []

    def get_artist_top_tracks(self, artist_name: str) -> list[DiscoveryTrack]:
        """Get an artist's top tracks from Spotify."""
        tracks = []
        artist_id = self.get_artist_id(artist_name)
        if not artist_id:
            return tracks

        try:
            resp = self.session.get(
                f"{SPOTIFY_API}/artists/{artist_id}/top-tracks",
                params={"market": "US"},
                timeout=10,
            )
            if resp.status_code == 200:
                for t in resp.json().get("tracks", []):
                    tracks.append(DiscoveryTrack(
                        artist=artist_name,
                        title=t["name"],
                        album=t.get("album", {}).get("name", ""),
                        spotify_id=t["id"],
                        preview_url=t.get("preview_url", ""),
                        duration_ms=t.get("duration_ms", 0),
                        yt_query=f"{artist_name} - {t['name']} official audio",
                    ))
        except Exception as e:
            log.error(f"Spotify top tracks failed: {e}")

        return tracks

    def discover_from_track(self, artist: str, title: str) -> DiscoverySession:
        """
        Get recommendations based on a track.

        Since /recommendations endpoint is broken, we:
        1. Search for the artist on Spotify
        2. Get related artists
        3. Get top tracks from related artists
        """
        session = DiscoverySession(
            seed_artist=artist,
            seed_title=title,
            source="spotify",
            created_at=time.time(),
        )

        if not self.is_authenticated():
            log.warning("Spotify not authenticated — falling back to Last.fm")
            return discover_from_lastfm(artist, title)

        # Get related artists
        artist_id = self.get_artist_id(artist)
        if not artist_id:
            log.warning(f"Could not find Spotify artist: {artist}")
            return discover_from_lastfm(artist, title)

        related = self.get_related_artists(artist_id)
        if not related:
            log.warning(f"No related artists found for: {artist}")
            return discover_from_lastfm(artist, title)

        log.info(f"Found {len(related)} related artists for {artist}")

        # Get top tracks from each related artist
        for rel_artist in related[:5]:  # Top 5 related artists
            tracks = self.get_artist_top_tracks(rel_artist)
            session.recommendations.extend(tracks)

        # Deduplicate
        seen = set()
        unique = []
        for t in session.recommendations:
            key = f"{t.artist.lower()}|{t.title.lower()}"
            if key not in seen:
                seen.add(key)
                unique.append(t)
        session.recommendations = unique[:MAX_RECOMMENDATIONS]

        log.info(f"Spotify discovery: {len(session.recommendations)} recommendations")
        return session


# ─────────────────────────────────────────────────────────────────────────────
# Last.fm Fallback
# ─────────────────────────────────────────────────────────────────────────────

def discover_from_lastfm(artist: str, title: str) -> DiscoverySession:
    """
    Get recommendations from Last.fm similar artists.

    Fallback when Spotify is not available.
    """
    session = DiscoverySession(
        seed_artist=artist,
        seed_title=title,
        source="lastfm",
        created_at=time.time(),
    )

    try:
        resp = requests.get(
            LASTFM_API,
            params={
                "method": "artist.getSimilar",
                "artist": artist,
                "api_key": LASTFM_API_KEY,
                "format": "json",
                "limit": MAX_LASTFM_ARTISTS,
            },
            timeout=10,
        )

        similar = []
        for a in resp.json().get("similarartists", {}).get("artist", []):
            similar.append(a["name"])

        log.info(f"Last.fm found {len(similar)} similar artists for {artist}")

        # Build discovery tracks from similar artists' top tracks
        # (We don't have track-level data from Last.fm, so we create placeholder entries)
        for rel_artist in similar[:5]:
            session.recommendations.append(DiscoveryTrack(
                artist=rel_artist,
                title="",  # Unknown — will be filled by YouTube search
                yt_query=f"{rel_artist} popular songs",
            ))

    except Exception as e:
        log.error(f"Last.fm discovery failed: {e}")

    return session


# ─────────────────────────────────────────────────────────────────────────────
# Local Library Matching
# ─────────────────────────────────────────────────────────────────────────────

def check_local_availability(
    session: DiscoverySession,
    master_library: dict,
) -> tuple[list[int], list[DiscoveryTrack]]:
    """
    Check which discoveries exist in local library.

    Returns:
        (local_track_ids, missing_discoveries)
    """
    local_ids = []
    missing = []

    for disc in session.recommendations:
        found = _find_in_library(disc, master_library)
        if found:
            local_ids.append(found)
        else:
            missing.append(disc)

    return local_ids, missing


def _find_in_library(disc: DiscoveryTrack, library: dict) -> Optional[int]:
    """
    Fuzzy match a discovery against local library.

    Returns track_id if found, None otherwise.
    """
    disc_artist = disc.artist.lower().strip()
    disc_title = disc.title.lower().strip()

    if not disc_artist or not disc_title:
        return None  # Can't match without both

    for tid, track in library.items():
        t_artist = getattr(track, "artist", "").lower().strip()
        t_title = getattr(track, "title", "").lower().strip()

        # Exact match
        if disc_artist == t_artist and disc_title == t_title:
            return tid

        # Fuzzy: artist contains + title contains
        if (disc_artist in t_artist or t_artist in disc_artist) and \
           (disc_title in t_title or t_title in disc_title):
            return tid

        # Title exact + artist partial
        if disc_title == t_title and (disc_artist in t_artist or t_artist in disc_artist):
            return tid

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Global Discovery Manager
# ─────────────────────────────────────────────────────────────────────────────

class DiscoveryManager:
    """Manages the current discovery session."""

    def __init__(self):
        self.spotify = SpotifyClient()
        self.current_session: Optional[DiscoverySession] = None
        self.missing_tracks: list[DiscoveryTrack] = []
        self.local_queue: list[int] = []  # Track IDs to play from local library

    def discover(self, artist: str, title: str, master_library: dict) -> dict:
        """
        Run discovery for the given artist/title.

        Returns dict with:
            - local_count: number of tracks found in library
            - discovery_count: number of new tracks to discover
            - discoveries: list of DiscoveryTrack objects (missing from library)
            - source: "spotify" or "lastfm"
        """
        # Get recommendations
        self.current_session = self.spotify.discover_from_track(artist, title)

        # Check against local library
        self.local_queue, self.missing_tracks = check_local_availability(
            self.current_session, master_library
        )

        return {
            "local_count": len(self.local_queue),
            "discovery_count": len(self.missing_tracks),
            "discoveries": self.missing_tracks,
            "source": self.current_session.source,
        }

    def set_spotify_token(self, token: str) -> None:
        """Set Spotify auth token."""
        self.spotify = SpotifyClient(token)

    def get_status(self) -> dict:
        """Get current discovery status."""
        return {
            "active": self.current_session is not None,
            "seed": f"{self.current_session.seed_artist} - {self.current_session.seed_title}" if self.current_session else "",
            "local_available": len(self.local_queue),
            "discoveries_pending": len(self.missing_tracks),
            "source": self.current_session.source if self.current_session else "none",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Global singleton
# ─────────────────────────────────────────────────────────────────────────────

_discovery_manager: Optional[DiscoveryManager] = None


def get_discovery_manager() -> DiscoveryManager:
    global _discovery_manager
    if _discovery_manager is None:
        _discovery_manager = DiscoveryManager()
    return _discovery_manager
