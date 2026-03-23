"""
t_metadata_enrich.py - Automatic Metadata Enrichment
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Automatically fetches missing genre/mode data from free sources:
1. MusicBrainz (free, no API key required)
2. Last.fm (requires API key in settings)

Caches results to avoid repeated lookups.
Also caches API errors to avoid hammering the service with invalid keys.
"""

import logging
import json
import hashlib
import time
from pathlib import Path
from typing import Dict, Any, Optional

log = logging.getLogger("t_metadata_enrich")

# Cache directories
CACHE_DIR = Path.home() / ".local" / "share" / "TauonMusicBox" / "metadata-cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _load_error_cache() -> dict:
    """Load error cache from disk."""
    error_file = CACHE_DIR / "error-cache.json"
    if error_file.exists():
        try:
            with open(error_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return {'lastfm_errors': {}}

def _save_error_cache(error_cache: dict):
    """Save error cache to disk."""
    error_file = CACHE_DIR / "error-cache.json"
    try:
        with open(error_file, 'w') as f:
            json.dump(error_cache, f, indent=2)
    except Exception as e:
        log.error(f"Failed to save error cache: {e}")

def _get_cache_key(artist: str, title: str) -> str:
    """Generate cache key from artist and title."""
    return hashlib.md5(f"{artist.lower()}__{title.lower()}".encode()).hexdigest()

def _get_api_key_hash(api_key: str) -> str:
    """Generate a hash of the API key for error tracking (don't store the actual key)."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]

def _load_cache() -> Dict[str, dict]:
    """Load metadata cache from disk."""
    cache_file = CACHE_DIR / "genre-cache.json"
    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def _save_cache(cache: Dict[str, dict]):
    """Save metadata cache to disk."""
    cache_file = CACHE_DIR / "genre-cache.json"
    try:
        with open(cache_file, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        log.error(f"Failed to save cache: {e}")

def _is_api_key_invalid(api_key: str) -> bool:
    """Check if API key is known to be invalid (from error cache)."""
    error_cache = _load_error_cache()
    
    key_hash = _get_api_key_hash(api_key)
    if key_hash in error_cache['lastfm_errors']:
        error_info = error_cache['lastfm_errors'][key_hash]
        error_code = error_info.get('error_code', 0)
        timestamp = error_info.get('timestamp', 0)

        # Critical errors that persist (invalid key, suspended account)
        # Don't retry for 24 hours
        if error_code in [10, 14, 19, 28]:  # Invalid/expired/suspended
            if time.time() - timestamp < 86400:  # 24 hours
                log.warning(f"Skipping Last.fm calls - API key known to be invalid (error {error_code})")
                return True

        # Rate limit - wait 1 hour
        if error_code == 24:
            if time.time() - timestamp < 3600:  # 1 hour
                log.warning(f"Skipping Last.fm calls - rate limited (error {error_code})")
                return True
    
    return False

def _mark_api_key_invalid(api_key: str, error_code: int):
    """Mark an API key as invalid in the error cache."""
    error_cache = _load_error_cache()
    
    key_hash = _get_api_key_hash(api_key)
    error_cache['lastfm_errors'][key_hash] = {
        'error_code': error_code,
        'timestamp': time.time(),
    }
    _save_error_cache(error_cache)
    log.error(f"Marked API key as invalid (error {error_code}) - will retry in 24h")

def fetch_musicbrainz_genre(artist: str, title: str) -> Optional[dict]:
    """
    Fetch genre from MusicBrainz (free, no API key).
    Returns dict with genre, mode (if available), or None if not found.
    """
    import requests
    
    try:
        # Search MusicBrainz for recording
        url = "https://musicbrainz.org/ws/2/recording/"
        params = {
            'query': f'artist:"{artist}" AND recording:"{title}"',
            'fmt': 'json',
            'limit': '1'
        }
        
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        if not data.get('recordings'):
            return None
        
        recording = data['recordings'][0]
        result = {}
        
        # Extract genre from tags
        if 'tags' in recording and recording['tags']:
            genres = [t['name'] for t in recording['tags'] if t.get('count', 0) > 0]
            if genres:
                result['genre'] = genres[0]  # Most popular genre
        
        # Extract key/mode if available
        if 'disambiguation' in recording:
            disambig = recording['disambiguation'].lower()
            if 'major' in disambig:
                result['mode'] = 1
            elif 'minor' in disambig:
                result['mode'] = 0
        
        return result if result else None
        
    except Exception as e:
        log.debug(f"MusicBrainz lookup failed: {e}")
        return None

# Last.fm API error codes
LASTFM_ERROR_CODES = {
    10: "Invalid API key",
    11: "Service offline",
    12: "Session method required",
    13: "Invalid method signature",
    14: "Authentication failed",
    15: "Invalid format",
    16: "Invalid parameters",
    17: "Resource not found",
    18: "Operation failed",
    19: "Session expired",
    20: "Trial expired",
    21: "Not enough content",
    22: "Not enough members",
    23: "Invalid zip code",
    24: "Rate limit exceeded",
    25: "Temporary failure",
    26: "Login required",
    27: "Permission denied",
    28: "Account suspended",
    29: "Subscription required",
}

def fetch_lastfm_genre(artist: str, title: str, api_key: str) -> Optional[dict]:
    """
    Fetch genre from Last.fm (requires API key).
    Returns dict with genre, or None if not found.
    
    Handles API errors including:
    - Error 10: Invalid API key
    - Error 19: Session expired
    - Error 24: Rate limit exceeded
    - Error 25: Temporary failure
    """
    import requests

    if not api_key:
        return None
    
    # Check if API key is known to be invalid (from error cache)
    if _is_api_key_invalid(api_key):
        return None

    try:
        url = "http://ws.audioscrobbler.com/2.0/"
        params = {
            'method': 'track.getInfo',
            'api_key': api_key,
            'artist': artist,
            'track': title,
            'format': 'json'
        }

        resp = requests.get(url, params=params, timeout=5)
        
        # Last.fm returns 403 for invalid API keys, but still includes JSON error body
        if resp.status_code == 403:
            try:
                data = resp.json()
                if 'error' in data:
                    error_code = data.get('error', 0)
                    error_message = data.get('message', 'Forbidden')
                    log.error(f"Last.fm API error {error_code}: {error_message}")
                    if error_code in [10, 14, 19, 28]:
                        _mark_api_key_invalid(api_key, error_code)
                        log.critical("Last.fm API key appears invalid or expired. Please update in Settings > Accounts.")
                    return None
            except:
                pass
            log.warning(f"Last.fm HTTP 403 Forbidden - check API key")
            return None
        
        if resp.status_code != 200:
            log.warning(f"Last.fm HTTP error: {resp.status_code}")
            return None

        data = resp.json()
        
        # Check for API-level errors (Last.fm returns error in response even with HTTP 200)
        if 'error' in data:
            error_code = data.get('error', 0)
            error_message = data.get('message', 'Unknown error')
            
            if error_code in LASTFM_ERROR_CODES:
                log.error(f"Last.fm API error {error_code}: {LASTFM_ERROR_CODES[error_code]} - {error_message}")
            else:
                log.error(f"Last.fm API error {error_code}: {error_message}")
            
            # Mark API key as invalid for critical errors
            if error_code in [10, 14, 19, 28]:  # Invalid/expired/suspended
                _mark_api_key_invalid(api_key, error_code)
                log.critical("Last.fm API key appears invalid or expired. Please update in Settings > Accounts.")
            elif error_code == 24:  # Rate limit
                _mark_api_key_invalid(api_key, error_code)
                log.warning("Last.fm rate limit hit - will retry in 1 hour")
            
            return None
        
        if 'track' not in data or 'toptags' not in data['track']:
            return None

        tags = data['track']['toptags'].get('tag', [])
        if tags:
            # Filter to genre-like tags
            genre_tags = [t['name'] for t in tags[:5]
                         if t['name'].lower() in [
                             'rock', 'pop', 'electronic', 'hip hop', 'rap',
                             'metal', 'punk', 'indie', 'alternative', 'folk',
                             'jazz', 'blues', 'classical', 'ambient', 'country',
                             'r&b', 'soul', 'funk', 'disco', 'house', 'techno',
                             'trance', 'dance', 'reggae', 'ska', 'latin',
                             'hardcore', 'grunge', 'emo', 'gothic'
                         ]]
            if genre_tags:
                return {'genre': genre_tags[0]}

        return None

    except requests.exceptions.Timeout:
        log.warning(f"Last.fm timeout for '{artist} - {title}'")
        return None
    except requests.exceptions.RequestException as e:
        log.error(f"Last.fm request failed: {e}")
        return None
    except Exception as e:
        log.exception(f"Last.fm lookup failed: {e}")
        return None

def enrich_track_metadata(track: dict, prefs=None) -> dict:
    """
    Enrich track metadata with genre/mode from external sources.
    
    Args:
        track: Track dict with artist, title, and optionally genre/mode
        prefs: Tauon preferences (for Last.fm API key)
    
    Returns:
        Enhanced track dict with genre/mode filled in
    """
    # Don't enrich if genre already exists
    if track.get('genre'):
        return track
    
    artist = track.get('artist', '')
    title = track.get('title', '')
    
    if not artist or not title:
        return track
    
    # Check cache first
    cache = _load_cache()
    cache_key = _get_cache_key(artist, title)
    
    if cache_key in cache:
        cached = cache[cache_key]
        if cached.get('genre'):
            track['genre'] = cached['genre']
        if cached.get('mode') is not None:
            track['mode'] = cached['mode']
        return track
    
    # Try MusicBrainz (free)
    mb_result = fetch_musicbrainz_genre(artist, title)
    if mb_result:
        if mb_result.get('genre'):
            track['genre'] = mb_result['genre']
        if mb_result.get('mode') is not None:
            track['mode'] = mb_result['mode']
        
        # Cache result
        cache[cache_key] = mb_result
        _save_cache(cache)
        log.info(f"Enriched {artist} - {title}: {mb_result}")
        return track
    
    # Try Last.fm (if API key available)
    if prefs and hasattr(prefs, 'lastfm_gen_api_key') and prefs.lastfm_gen_api_key:
        lf_result = fetch_lastfm_genre(artist, title, prefs.lastfm_gen_api_key)
        if lf_result and lf_result.get('genre'):
            track['genre'] = lf_result['genre']
            cache[cache_key] = lf_result
            _save_cache(cache)
            log.info(f"Last.fm enriched {artist} - {title}: {lf_result}")
    
    return track
