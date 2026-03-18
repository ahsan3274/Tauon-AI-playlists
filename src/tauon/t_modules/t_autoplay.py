"""
t_autoplay.py - Spotify-like Autoplay for Tauon
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Automatically queue similar tracks when current track ends.
Uses multiple strategies:
  1. Spotify audio features (if available)
  2. Last.fm similar artists
  3. Library-based similar tracks (fallback)

Add to t_main.py advance() function to trigger when queue is ending.
"""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

log = logging.getLogger("t_autoplay")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

AUToplay_THRESHOLD = 2  # Trigger autoplay when < N tracks left in queue
MAX_AUToplay_QUEUE = 10  # Maximum tracks to auto-queue at once
AUToplay_COOLDOWN = 30  # Seconds between autoplay triggers


# ─────────────────────────────────────────────────────────────────────────────
# Autoplay Manager Class
# ─────────────────────────────────────────────────────────────────────────────

class AutoplayManager:
    def __init__(self, tauon):
        self.tauon = tauon
        self.pctl = tauon.pctl
        self.last_trigger_time = 0
        self.enabled = False
        self.use_spotify = True
        self.use_lastfm = True
        self.fallback_library = True
        
    def should_trigger_autoplay(self) -> bool:
        """Check if conditions are right to trigger autoplay."""
        # Check if enabled
        if not self.enabled:
            return False
        
        # Check cooldown
        now = time.time()
        if now - self.last_trigger_time < AUToplay_COOLDOWN:
            return False
        
        # Check queue length (use preference if available)
        threshold = getattr(self.tauon.prefs, 'autoplay_threshold', AUToplay_THRESHOLD)
        tracks_remaining = len(self.pctl.track_queue) - self.pctl.queue_step - 1
        if tracks_remaining > threshold:
            return False
        
        # Check if we're already at max queue size
        if len(self.pctl.track_queue) > MAX_AUToplay_QUEUE * 2:
            return False
        
        return True
    
    def get_current_track_info(self):
        """Get info about currently playing track."""
        if self.pctl.queue_step >= len(self.pctl.track_queue):
            return None
        
        track_id = self.pctl.track_queue[self.pctl.queue_step]
        track = self.pctl.master_library.get(track_id)
        
        if not track:
            return None
        
        return {
            "id": track_id,
            "artist": getattr(track, "artist", ""),
            "title": getattr(track, "title", ""),
            "album": getattr(track, "album", ""),
            "genre": getattr(track, "genre", ""),
            "duration": getattr(track, "length", 0),
        }
    
    def trigger_autoplay(self) -> int:
        """Main autoplay trigger - queue similar tracks."""
        if not self.should_trigger_autoplay():
            return 0
        
        track_info = self.get_current_track_info()
        if not track_info:
            return 0
        
        log.info(f"Autoplay: triggering based on '{track_info['artist']} - {track_info['title']}'")
        self.last_trigger_time = time.time()
        
        # Try strategies in order of preference
        queued = 0
        
        # Strategy 1: Spotify audio features + similar tracks
        if self.use_spotify and queued < MAX_AUToplay_QUEUE:
            queued += self._queue_spotify_similar(track_info, MAX_AUToplay_QUEUE - queued)
        
        # Strategy 2: Last.fm similar artists
        if self.use_lastfm and queued < MAX_AUToplay_QUEUE:
            queued += self._queue_lastfm_similar(track_info, MAX_AUToplay_QUEUE - queued)
        
        # Strategy 3: Library-based similar tracks
        if self.fallback_library and queued < MAX_AUToplay_QUEUE:
            queued += self._queue_library_similar(track_info, MAX_AUToplay_QUEUE - queued)
        
        log.info(f"Autoplay: queued {queued} tracks")
        return queued
    
    def _queue_spotify_similar(self, track: dict, limit: int) -> int:
        """Queue tracks similar to current using Spotify audio features."""
        try:
            import tekore as tk
        except ImportError:
            return 0
        
        # Check if Spotify is available
        if not hasattr(self.pctl, 'spot') or not self.pctl.spot or not self.pctl.spot.spotify:
            return 0
        
        spotify = self.pctl.spot.spotify
        artist = track.get("artist", "")
        title = track.get("title", "")
        
        if not artist or not title:
            return 0
        
        # Search for current track on Spotify
        query = f"track:{title} artist:{artist}"
        try:
            search_result = spotify.search(query, types=("track",), limit=1)
            
            if not search_result or not search_result[0] or not search_result[0].items:
                return 0
            
            spotify_track = search_result[0].items[0]
            track_id = spotify_track.id
            
            # Get audio features for current track
            features = spotify.track_audio_features(track_id)
            if not features:
                return 0
            
            # Get recommendations based on audio features
            # Use similar energy, valence, danceability
            recs = spotify.recommendations(
                seed_tracks=[track_id],
                limit=limit,
                target_energy=features.energy,
                target_valence=features.valence,
                target_danceability=features.danceability,
                target_tempo=features.tempo,
            )
            
            if not recs or not recs.tracks:
                return 0
            
            # Queue the recommended tracks
            queued = 0
            for rec_track in recs.tracks:
                # Try to match with library track
                rec_artist = ", ".join([a.name for a in rec_track.artists])
                rec_title = rec_track.name
                rec_duration = rec_track.duration_ms / 1000.0
                
                # Find matching track in library
                match = self._find_library_match(rec_artist, rec_title, rec_duration)
                if match:
                    self._add_to_queue(match["id"])
                    queued += 1
            
            return queued
            
        except Exception as e:
            log.debug(f"Spotify autoplay failed: {e}")
            return 0
    
    def _queue_lastfm_similar(self, track: dict, limit: int) -> int:
        """Queue tracks from similar artists using Last.fm."""
        try:
            import requests
        except ImportError:
            return 0
        
        artist = track.get("artist", "")
        if not artist:
            return 0
        
        # Get similar artists from Last.fm
        api_key = "b048411511a3191008fee11a34f4e233"  # Public demo key
        try:
            r = requests.get(
                "https://ws.audioscrobbler.com/2.0/",
                params={
                    "method": "artist.getSimilar",
                    "artist": artist,
                    "api_key": api_key,
                    "format": "json",
                    "limit": 10,
                },
                timeout=10
            )
            
            similar_artists = [
                a["name"].lower() 
                for a in r.json().get("similarartists", {}).get("artist", [])
            ]
            
            if not similar_artists:
                return 0
            
            # Find tracks from similar artists in library
            queued = 0
            library_tracks = self._get_library_tracks_by_artists(similar_artists)
            
            # Filter out already queued tracks
            queued_ids = set(self.pctl.track_queue)
            
            for track_id in library_tracks:
                if track_id not in queued_ids and queued < limit:
                    self._add_to_queue(track_id)
                    queued_ids.add(track_id)
                    queued += 1
            
            return queued
            
        except Exception as e:
            log.debug(f"Last.fm autoplay failed: {e}")
            return 0
    
    def _queue_library_similar(self, track: dict, limit: int) -> int:
        """Queue similar tracks from library (genre/artist based)."""
        artist = track.get("artist", "")
        genre = track.get("genre", "")
        
        if not artist and not genre:
            return 0
        
        # Get all tracks from library
        all_tracks = self._get_all_library_tracks()
        
        # Score tracks by similarity
        scored = []
        for tid, t in all_tracks.items():
            if tid in self.pctl.track_queue:
                continue  # Skip already queued
            
            score = 0
            
            # Same artist = high score
            if t.get("artist", "").lower() == artist.lower():
                score += 10
            elif artist.lower() in t.get("artist", "").lower():
                score += 5
            
            # Same genre = medium score
            if genre and genre.lower() in t.get("genre", "").lower():
                score += 3
            
            # Same folder/album = bonus
            if t.get("parent_folder_path") == track.get("parent_folder_path"):
                score += 2
            
            if score > 0:
                scored.append((score, tid))
        
        # Sort by score and take top tracks
        scored.sort(reverse=True)
        
        queued = 0
        for _, tid in scored[:limit]:
            self._add_to_queue(tid)
            queued += 1
        
        return queued
    
    def _find_library_match(self, artist: str, title: str, duration: float) -> dict | None:
        """Find matching track in library by artist/title/duration."""
        all_tracks = self._get_all_library_tracks()
        
        for tid, t in all_tracks.items():
            t_artist = t.get("artist", "").lower()
            t_title = t.get("title", "").lower()
            t_duration = t.get("duration", 0)
            
            # Check artist match
            if artist.lower() not in t_artist and t_artist not in artist.lower():
                continue
            
            # Check title match (fuzzy)
            if title.lower() not in t_title and t_title not in title.lower():
                continue
            
            # Check duration match (within 10 seconds)
            if t_duration > 0 and abs(t_duration - duration) > 10:
                continue
            
            return {"id": tid, "artist": t_artist, "title": t_title}
        
        return None
    
    def _get_library_tracks_by_artists(self, artists: list[str]) -> list[int]:
        """Get track IDs from library for given artist names."""
        all_tracks = self._get_all_library_tracks()
        track_ids = []
        
        for tid, t in all_tracks.items():
            t_artist = t.get("artist", "").lower()
            if any(a in t_artist for a in artists):
                track_ids.append(tid)
        
        # Shuffle to get variety
        random.shuffle(track_ids)
        return track_ids
    
    def _get_all_library_tracks(self) -> dict:
        """Get all tracks from library as dict."""
        result = {}
        for tid, tr in self.pctl.master_library.items():
            result[tid] = {
                "id": tid,
                "artist": getattr(tr, "artist", "").lower(),
                "title": getattr(tr, "title", ""),
                "genre": getattr(tr, "genre", ""),
                "duration": getattr(tr, "length", 0),
                "parent_folder_path": getattr(tr, "parent_folder_path", ""),
            }
        return result
    
    def _add_to_queue(self, track_id: int) -> None:
        """Add track ID to queue."""
        self.pctl.track_queue.append(track_id)


# ─────────────────────────────────────────────────────────────────────────────
# Integration Helper
# ─────────────────────────────────────────────────────────────────────────────

def setup_autoplay(tauon) -> AutoplayManager:
    """Initialize and return autoplay manager."""
    manager = AutoplayManager(tauon)
    
    # Load preferences
    manager.enabled = getattr(tauon.prefs, 'autoplay_enable', False)
    manager.use_spotify = getattr(tauon.prefs, 'autoplay_use_spotify', True) and hasattr(tauon.pctl, 'spot') and tauon.pctl.spot
    manager.use_lastfm = getattr(tauon.prefs, 'autoplay_use_lastfm', True)
    manager.fallback_library = getattr(tauon.prefs, 'autoplay_use_library', True)
    
    # Store reference to manager in tauon for updating enabled state
    tauon.autoplay_manager = manager
    
    return manager
