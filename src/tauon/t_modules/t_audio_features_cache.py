#!/usr/bin/env python3
"""
Persistent Audio Features Cache for Tauon Music Box

Caches computed audio features (energy, valence, danceability, acousticness, etc.)
to disk so they persist across sessions and don't need recalculation.

Features:
- Automatic cache invalidation when track metadata changes
- JSON-based storage for easy inspection/debugging
- Incremental updates (only recalculates when needed)
- Thread-safe operations

Usage:
    from tauon.t_modules.t_audio_features_cache import AudioFeaturesCache
    
    cache = AudioFeaturesCache(user_directory)
    
    # Get features (will calculate if not cached)
    features = cache.get_features(track)
    
    # Or calculate and cache
    features = cache.calculate_and_cache(track, prefs)
    
    # Save cache to disk
    cache.save()
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("t_audio_features_cache")


class AudioFeaturesCache:
    """
    Persistent cache for audio features.
    
    Stores features in a JSON file with metadata hash for cache invalidation.
    """
    
    CACHE_VERSION = 1  # Increment when cache format changes
    
    def __init__(self, user_directory: Path, cache_filename: str = "audio_features.json"):
        """
        Initialize the audio features cache.

        Args:
            user_directory: Tauon's user data directory
            cache_filename: Name of the cache file
        """
        self.user_directory = Path(user_directory) if user_directory else Path.home() / ".local" / "share" / "TauonMusicBox"
        self.cache_file = self.user_directory / cache_filename
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_metadata: Dict[str, Any] = {
            "version": self.CACHE_VERSION,
            "created_at": None,
            "updated_at": None,
            "total_tracks": 0,
        }
        self._load()
    
    def _load(self) -> None:
        """Load cache from disk if it exists."""
        if self.cache_file.exists():
            try:
                with self.cache_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.cache = data.get("tracks", {})
                    self.cache_metadata = data.get("metadata", self.cache_metadata)
                logger.info(f"Loaded audio features cache: {len(self.cache)} tracks")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load audio features cache: {e}")
                self.cache = {}
        else:
            logger.info("No audio features cache found, will create on first save")
    
    def _save(self) -> None:
        """Save cache to disk."""
        try:
            self.user_directory.mkdir(parents=True, exist_ok=True)
            
            data = {
                "tracks": self.cache,
                "metadata": {
                    **self.cache_metadata,
                    "updated_at": time.time(),
                    "total_tracks": len(self.cache),
                },
            }
            
            # Write atomically (write to temp, then rename)
            temp_file = self.cache_file.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            temp_file.rename(self.cache_file)
            logger.info(f"Saved audio features cache: {len(self.cache)} tracks")
        except IOError as e:
            logger.error(f"Failed to save audio features cache: {e}")
    
    def _compute_metadata_hash(self, track: Dict[str, Any]) -> str:
        """
        Compute a hash of track metadata that affects audio features.
        
        This is used to detect when cached features are stale.
        
        Args:
            track: Track dictionary with metadata
            
        Returns:
            MD5 hash of relevant metadata fields
        """
        # Fields that affect audio feature calculation
        relevant_fields = {
            "genre": track.get("genre", ""),
            "bpm": track.get("bpm", 0) or track.get("misc", {}).get("bpm", 0),
            "mode": track.get("mode", None),
            "loudness": track.get("loudness", None),
        }
        
        # Create deterministic string representation
        metadata_str = json.dumps(relevant_fields, sort_keys=True)
        return hashlib.md5(metadata_str.encode("utf-8")).hexdigest()
    
    def get_features(self, track: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get cached audio features for a track.
        
        Returns None if not cached or cache is stale.
        
        Args:
            track: Track dictionary with metadata
            
        Returns:
            Cached features dict or None
        """
        track_id = self._get_track_id(track)
        if not track_id:
            return None
        
        cached = self.cache.get(track_id)
        if not cached:
            return None
        
        # Check if cache is still valid
        current_hash = self._compute_metadata_hash(track)
        if cached.get("metadata_hash") != current_hash:
            logger.debug(f"Cache stale for track {track_id}, needs recalculation")
            return None
        
        logger.debug(f"Cache hit for track {track_id}")
        return cached.get("features")
    
    def set_features(
        self,
        track: Dict[str, Any],
        features: Dict[str, Any],
        save_immediately: bool = False,
    ) -> None:
        """
        Cache audio features for a track.
        
        Args:
            track: Track dictionary with metadata
            features: Computed audio features
            save_immediately: If True, save to disk immediately
        """
        track_id = self._get_track_id(track)
        if not track_id:
            return
        
        metadata_hash = self._compute_metadata_hash(track)
        
        self.cache[track_id] = {
            "features": features,
            "metadata_hash": metadata_hash,
            "cached_at": time.time(),
            "cache_version": self.CACHE_VERSION,
        }
        
        if save_immediately:
            self._save()
    
    def calculate_and_cache(
        self,
        track: Dict[str, Any],
        calculate_fn: callable,
        save_immediately: bool = False,
    ) -> Dict[str, Any]:
        """
        Get cached features or calculate and cache them.
        
        Args:
            track: Track dictionary with metadata
            calculate_fn: Function to calculate features if not cached
            save_immediately: If True, save to disk immediately
            
        Returns:
            Audio features dict
        """
        # Try cache first
        cached = self.get_features(track)
        if cached:
            return cached
        
        # Calculate features
        track_id = self._get_track_id(track)
        logger.debug(f"Cache miss for track {track_id}, calculating features...")
        
        features = calculate_fn(track)
        
        # Cache the result
        self.set_features(track, features, save_immediately)
        
        return features
    
    def _get_track_id(self, track: Dict[str, Any]) -> Optional[str]:
        """
        Get a unique identifier for a track.
        
        Uses fullpath if available, otherwise falls back to index.
        
        Args:
            track: Track dictionary
            
        Returns:
            Unique track ID string or None
        """
        if isinstance(track, dict):
            # Try fullpath first (most reliable)
            fullpath = track.get("fullpath", "")
            if fullpath:
                return fullpath
            
            # Fall back to index
            index = track.get("index")
            if index is not None:
                return f"index:{index}"
        
        return None
    
    def invalidate(self, track: Dict[str, Any]) -> bool:
        """
        Remove cached features for a track.
        
        Args:
            track: Track dictionary
            
        Returns:
            True if entry was removed, False if not cached
        """
        track_id = self._get_track_id(track)
        if track_id and track_id in self.cache:
            del self.cache[track_id]
            return True
        return False
    
    def invalidate_all(self) -> None:
        """Clear all cached features."""
        self.cache = {}
        self.cache_metadata = {
            "version": self.CACHE_VERSION,
            "created_at": time.time(),
            "updated_at": time.time(),
            "total_tracks": 0,
        }
        self._save()
    
    def save(self) -> None:
        """Save cache to disk."""
        self._save()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache statistics
        """
        return {
            "total_tracks": len(self.cache),
            "cache_file": str(self.cache_file),
            "cache_file_exists": self.cache_file.exists(),
            "cache_version": self.CACHE_VERSION,
            "created_at": self.cache_metadata.get("created_at"),
            "updated_at": self.cache_metadata.get("updated_at"),
        }
    
    def export_to_json(self, output_path: str) -> None:
        """
        Export all cached features to a JSON file.
        
        Args:
            output_path: Path to save the export
        """
        export_data = {
            "cache_stats": self.get_stats(),
            "tracks": self.cache,
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported audio features cache to {output_path}")


# Global cache instance (singleton pattern)
_global_cache: Optional[AudioFeaturesCache] = None


def get_global_cache(user_directory: Path) -> AudioFeaturesCache:
    """
    Get or create the global audio features cache instance.

    Args:
        user_directory: Tauon's user data directory

    Returns:
        AudioFeaturesCache instance
    """
    global _global_cache
    if _global_cache is None:
        if user_directory:
            _global_cache = AudioFeaturesCache(Path(user_directory))
        else:
            # Return a dummy cache that does nothing if no user directory
            _global_cache = AudioFeaturesCache(Path.home() / ".local" / "share" / "TauonMusicBox")
    return _global_cache


def reset_global_cache() -> None:
    """Reset the global cache instance (useful for testing)."""
    global _global_cache
    if _global_cache:
        _global_cache.save()
    _global_cache = None
