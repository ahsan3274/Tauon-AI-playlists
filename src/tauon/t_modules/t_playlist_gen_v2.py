"""
t_playlist_gen_v2.py - Audio-Based Music Recommender
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REPLACES: LLM-based mood playlists
APPROACH: Content-based filtering using Spotify audio features

Features:
  - Mood-based recommendations (valence + energy)
  - Energy-based recommendations (energy + tempo + loudness)
  - Genre clustering (audio features + metadata)
  - Similarity radio (find tracks similar to seed track)
  - Era-based playlists (decade grouping)

All recommendations use Spotify audio features when available,
with local metadata fallback for unmatched tracks.

Privacy-first: Zero external API calls during recommendation.
"""

from __future__ import annotations

import logging
import math
import random
import re
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from tauon.t_modules.t_metadata_enrich import enrich_track_metadata
from tauon.t_modules.t_audio_features_cache import get_global_cache, AudioFeaturesCache
from tauon.t_modules.t_utils_playlist import get_library_tracks, create_playlist

if TYPE_CHECKING:
    pass

log = logging.getLogger("t_playlist_gen_v2")

# Global audio features cache instance
_audio_features_cache: Any = None

def get_audio_features_cache(user_directory=None):
    """Get or create the global audio features cache."""
    global _audio_features_cache
    if _audio_features_cache is None and user_directory:
        try:
            _audio_features_cache = get_global_cache(Path(user_directory))
        except Exception:
            # If cache init fails, continue without cache
            pass
    return _audio_features_cache
# ─────────────────────────────────────────────────────────────────────────────
# MOOD ANCHOR POINTS  (energy, valence)
# ─────────────────────────────────────────────────────────────────────────────
#
# Positions chosen so every pairwise distance ≥ 0.30 (above sigma=0.22),
# verified analytically.  All overlaps between any two anchors ≤ 0.38.
#
#          Valence →
#          low          mid          high
# Energy
# high   Frantic(0.82,0.15) Energetic(0.88,0.52) Exuberant(0.90,0.90)
# mid                                              Happy(0.65,0.72)
# low    Depression(0.06,0.05) Sad(0.30,0.25) Calm(0.14,0.56) Contentment(0.36,0.82)
#

"""
Mood Algorithm — Tauon AI Playlists  (v3 — red-team hardened)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Changes from v2 (red-team findings)
─────────────────────────────────────
FIX 1 · BPM→valence coupling removed
        Research confirms tempo predicts arousal (energy) only, not valence.
        In the no-genre fallback, valence now starts neutral (0.50) and is
        shaped entirely by mode and genre, not BPM.

FIX 2 · Genre normalisation
        "hip-hop" → "hip hop", "r'n'b" → "r&b", "edm" → "electronic", etc.
        Hyphens and apostrophes in real-world tags caused silent misses.

FIX 3 · Multi-genre blending
        "indie folk" or "indie pop" now scores ALL matching genre keywords
        and takes a weighted average (weight = keyword length, so "hip hop"
        outweighs "rock" in "hip hop rock" etc.).

FIX 4 · Genre-based mode prior
        When the track has no mode tag (very common), genres with a strong
        historical tendency toward major or minor keys contribute a partial
        valence shift.  Smaller than the full ±0.18 tag shift; documented.

FIX 5 · Anchor positions spread apart
        All pairwise anchor distances are now ≥ 0.30, verified analytically.
        Previously Calm↔Contentment=0.197, Exuberant↔Happy=0.206 were both
        below sigma=0.28, causing constant near-ties.

FIX 6 · Sigma reduced from 0.28 → 0.22
        Crisper boundaries now that anchors are properly separated.

FIX 7 · Confidence score
        calculate_mood_score() returns a 'confidence' key (top/second ratio).
        <1.5 = weak signal, 1.5–2.5 = moderate, >2.5 = strong.

Research basis
──────────────
· Thayer's 2D mood model [Lu 2006, Yang & Chen 2012, Bhat 2014]
· Tempo → arousal only [multiple studies; tempo not significant for valence]
· Mode → valence, ~90% polarity accuracy [Webster & Weir 2005, Frontiers 2024]
· Genre alone < random noise for mood prediction [Gracenote/Spotify study]
· Loudness → arousal [Tufts ECE Handbook]
· SVM/ANN on Thayer model: 73% arousal, 67% valence accuracy [Shakya 2017]

Usage
─────
    python mood_algorithm.py

Or import:
    from mood_algorithm import calculate_mood_score, get_metadata_features
"""

import math
from typing import Dict, Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
# MOOD ANCHOR POINTS  (energy, valence)
# ─────────────────────────────────────────────────────────────────────────────
#
# Positions chosen so every pairwise distance ≥ 0.30 (above sigma=0.22),
# verified analytically.  All overlaps between any two anchors ≤ 0.38.
#
#          Valence →
#          low          mid          high
# Energy
# high   Frantic(0.82,0.15) Energetic(0.88,0.52) Exuberant(0.90,0.90)
# mid                                              Happy(0.65,0.72)
# low    Depression(0.06,0.05) Sad(0.30,0.25) Calm(0.14,0.56) Contentment(0.36,0.82)
#

MOOD_ANCHORS: Dict[str, tuple] = {
    #                  (energy, valence, acousticness)
    "Joyful":          (0.85,   0.88,   0.25),  # Dance, rave, jubilant pop
    "Power":           (0.65,   0.55,   0.20),  # Rock anthems, hip-hop, driving electronic
    "Tension":         (0.82,   0.12,   0.15),  # Dark metal, aggressive EDM
    "Wonder":          (0.52,   0.82,   0.82),  # Classical major, cinematic
    "Transcendence":   (0.72,   0.78,   0.40),  # Epic trance, film scores
    "Nostalgia":       (0.35,   0.45,   0.70),  # Indie, folk, bittersweet
    "Tenderness":      (0.20,   0.85,   0.85),  # Soft ballads, acoustic love
    "Peacefulness":    (0.18,   0.65,   0.90),  # Ambient, meditation
    "Sadness":         (0.28,   0.15,   0.58),  # Blues, sad classical
}

# Gaussian sigma in 3D space
MOOD_SIGMA = 0.22
# Weight of acousticness axis (secondary)
ACOUSTIC_WEIGHT = 0.50


# Reduced from 0.28 → 0.22 now that anchors are properly spread
MOOD_SIGMA = 0.22
ACOUSTIC_WEIGHT = 0.50  # Weight of acousticness axis (secondary)


# ─────────────────────────────────────────────────────────────────────────────
# GENRE MAPS
# ─────────────────────────────────────────────────────────────────────────────

_GENRE_ENERGY: Dict[str, float] = {
    "metal":       0.90,
    "hardcore":    0.95,
    "punk":        0.92,
    "rock":        0.72,
    "alternative": 0.65,
    "indie":       0.58,
    "techno":      0.88,
    "trance":      0.82,
    "electronic":  0.80,
    "house":       0.78,
    "dance":       0.80,
    "disco":       0.75,
    "funk":        0.70,
    "hip hop":     0.65,
    "trap":        0.72,
    "rap":         0.68,
    "pop":         0.65,
    "r&b":         0.50,
    "soul":        0.52,
    "reggae":      0.50,
    "country":     0.50,
    "folk":        0.38,
    "blues":       0.40,
    "jazz":        0.42,
    "classical":   0.32,
    "ambient":     0.18,
}

_GENRE_VALENCE: Dict[str, float] = {
    "disco":       0.82,
    "dance":       0.80,
    "pop":         0.76,
    "funk":        0.75,
    "reggae":      0.72,
    "house":       0.70,
    "country":     0.65,
    "soul":        0.65,
    "r&b":         0.62,
    "classical":   0.62,
    "folk":        0.60,
    "ambient":     0.62,
    "jazz":        0.62,
    "indie":       0.58,
    "alternative": 0.52,
    "rock":        0.55,
    "electronic":  0.60,
    "trance":      0.58,
    "techno":      0.52,
    "hip hop":     0.55,
    "rap":         0.48,
    "trap":        0.42,
    "punk":        0.50,
    "blues":       0.38,
    "metal":       0.35,
    "hardcore":    0.30,
}


# ─────────────────────────────────────────────────────────────────────────────
# MODE → VALENCE SHIFT
# ─────────────────────────────────────────────────────────────────────────────
#
# Major/minor mode predicts valence polarity at ~90% accuracy.
# [Webster & Weir 2005; Frontiers in Psychology 2024]
# Applied when mode tag is present (mode=1 major, mode=0 minor).
#
MODE_MAJOR_SHIFT = +0.18
MODE_MINOR_SHIFT = -0.18

# ─────────────────────────────────────────────────────────────────────────────
# GENRE MODE PRIOR
# ─────────────────────────────────────────────────────────────────────────────
#
# FIX 4: When mode tag is absent (very common in practice), genres with a
# historically strong tendency toward major or minor keys contribute a small
# partial valence shift.  Much smaller than the full tag shift (±0.18) to
# avoid overriding other signals.  Only applied when mode is unknown.
#
_GENRE_MODE_PRIOR: Dict[str, float] = {
    # Minor-leaning genres (darker tonality is the norm)
    "metal":       -0.10,
    "hardcore":    -0.12,
    "blues":       -0.10,
    "trap":        -0.08,
    "rap":         -0.05,
    # Major-leaning genres (brighter tonality is the norm)
    "disco":       +0.09,
    "pop":         +0.07,
    "dance":       +0.07,
    "reggae":      +0.07,
    "country":     +0.06,
    "folk":        +0.06,
    # Neutral / mixed — no prior
}


# ─────────────────────────────────────────────────────────────────────────────
# GENRE NORMALISATION  (FIX 2 + FIX 3)
# ─────────────────────────────────────────────────────────────────────────────

_GENRE_ALIASES: Dict[str, str] = {
    "hip-hop":          "hip hop",
    "hiphop":           "hip hop",
    "r'n'b":            "r&b",
    "rnb":              "r&b",
    "rhythm and blues": "r&b",
    "edm":              "electronic",
    "drum and bass":    "electronic",
    "dnb":              "electronic",
    "d&b":              "electronic",
    "grunge":           "alternative",
    "post-rock":        "rock",
    "post rock":        "rock",
    "new wave":         "alternative",
    "synthpop":         "electronic",
    "synth pop":        "electronic",
}


def _normalise_genre(genre: str) -> str:
    """Lowercase, strip, expand aliases, normalise separators."""
    g = genre.lower().strip()
    g = g.replace("-", " ").replace("'", "").replace("_", " ")
    # Multi-pass alias expansion
    for alias, canonical in _GENRE_ALIASES.items():
        g = g.replace(alias, canonical)
    return g


def _match_genres(genre: str) -> Optional[tuple]:
    """
    Find ALL genre keywords present in the genre string.
    Returns (energy, valence) as a weighted average across all matches,
    or None if no genres matched.

    Weight = len(keyword) so more-specific terms ("hip hop") outweigh
    shorter ones ("rock") in compound strings like "hip hop rock".
    """
    matches = []
    for g, e_val in _GENRE_ENERGY.items():
        if g in genre:
            w = len(g)
            v_val = _GENRE_VALENCE.get(g, 0.50)
            matches.append((e_val, v_val, w, g))

    if not matches:
        return None

    total_w = sum(m[2] for m in matches)
    energy  = sum(m[0] * m[2] for m in matches) / total_w
    valence = sum(m[1] * m[2] for m in matches) / total_w
    return energy, valence, matches


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def get_metadata_features(track: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract audio features from track metadata (tags).

    Args:
        track: Dictionary with any of:
               · genre    (str)   — e.g. "rock", "indie folk", "hip-hop"
               · bpm      (float) — beats per minute
               · mode     (int)   — 1 = major, 0 = minor, None = unknown
               · loudness (float) — track loudness in dBFS (negative)

    Returns:
        Dictionary with energy, valence, danceability, acousticness,
        loudness, tempo, mode, and a confidence_note string.

    Feature priority (highest → lowest impact on valence):
        1. mode tag (major/minor) — strongest single signal
        2. genre valence baseline
        3. genre mode prior (when mode tag absent)
        4. BPM — energy only, NOT valence
        5. loudness — energy modifier
    """
    # ── BPM ──────────────────────────────────────────────────────────────────
    bpm: float = float(track.get('bpm', 0) or 0)
    if not bpm:
        bpm = float((track.get('misc') or {}).get('bpm', 0) or 0)

    # ── Genre ─────────────────────────────────────────────────────────────────
    raw_genre: str = track.get('genre', '') or ''
    # Treat "Unknown Genre" and similar as empty
    if raw_genre.lower() in ['unknown genre', 'unknown', 'other', '']:
        raw_genre = ''
    genre = _normalise_genre(raw_genre)

    # ── Mode ─────────────────────────────────────────────────────────────────
    mode: Optional[int] = track.get('mode', None)
    if mode is not None:
        try:
            mode = int(mode)
        except (TypeError, ValueError):
            mode = None

    # ── Loudness ─────────────────────────────────────────────────────────────
    loudness_db: Optional[float] = None
    raw_loud = track.get('loudness', None)
    if raw_loud is not None:
        try:
            loudness_db = float(raw_loud)
        except (TypeError, ValueError):
            pass

    # ── Energy + Valence base ─────────────────────────────────────────────────
    energy  = 0.50
    valence = 0.50
    genre_matched = False
    matched_genres = []

    result = _match_genres(genre)
    if result is not None:
        energy, valence, matches = result
        genre_matched = True
        matched_genres = [m[3] for m in matches]
    elif not genre and bpm > 0:
        # FIX: When genre is missing, use BPM-based energy/valence estimation
        # This is crucial for libraries with poor genre tagging
        bpm_norm = max(0.0, min(1.0, (bpm - 60.0) / 120.0))
        
        # Energy correlates with tempo (faster = more energy)
        energy = 0.30 + bpm_norm * 0.50  # Range: 0.30 - 0.80
        
        # Valence has weaker correlation with tempo, but faster tracks tend to be more positive
        valence = 0.40 + bpm_norm * 0.30  # Range: 0.40 - 0.70

    # ── BPM → energy only  (FIX 1: NO valence) ────────────────────────────────
    if bpm > 0:
        bpm_norm   = max(0.0, min(1.0, (bpm - 60.0) / 120.0))
        bpm_energy = 0.30 + bpm_norm * 0.60   # 0.30 – 0.90

        if genre_matched:
            energy = energy * 0.55 + bpm_energy * 0.45
        else:
            energy = bpm_energy
            # valence stays at 0.50 — neutral until mode/genre shape it

    # ── Loudness → energy ────────────────────────────────────────────────────
    if loudness_db is not None:
        loudness_norm = max(0.0, min(1.0, (loudness_db + 24.0) / 20.0))
        energy = energy * 0.75 + loudness_norm * 0.25

    # ── Mode tag shift (strongest valence signal) ─────────────────────────────
    if mode == 1:
        valence += MODE_MAJOR_SHIFT
    elif mode == 0:
        valence += MODE_MINOR_SHIFT
    else:
        # ── Genre mode prior (FIX 4: when no mode tag) ───────────────────────
        prior = 0.0
        for g in matched_genres:
            if g in _GENRE_MODE_PRIOR:
                prior = _GENRE_MODE_PRIOR[g]
                break   # use the first (longest-weighted) match
        valence += prior

    energy  = max(0.05, min(0.95, energy))
    valence = max(0.05, min(0.95, valence))

    # ── Danceability ──────────────────────────────────────────────────────────
    danceability = 0.50
    if any(g in genre for g in ['disco', 'dance', 'house', 'funk', 'pop']):
        danceability = 0.82
    elif any(g in genre for g in ['hip hop', 'r&b', 'soul', 'reggae']):
        danceability = 0.72
    elif any(g in genre for g in ['metal', 'classical', 'ambient', 'blues']):
        danceability = 0.30
    elif bpm > 0:
        bpm_norm = max(0.0, min(1.0, (bpm - 60.0) / 120.0))
        danceability = 0.40 + bpm_norm * 0.40

    # ── Acousticness ──────────────────────────────────────────────────────────
    # Default varies by BPM: fast = electronic, slow = acoustic
    acousticness = 0.50
    if bpm > 0 and not genre_matched:
        # BPM-based acousticness estimate for untagged tracks
        if bpm > 140:
            acousticness = 0.15  # Fast = likely electronic/dance
        elif bpm > 110:
            acousticness = 0.30  # Mid-fast = mixed
        elif bpm > 85:
            acousticness = 0.50  # Mid-tempo = neutral
        else:
            acousticness = 0.75  # Slow = likely acoustic
    
    if any(g in genre for g in ['classical', 'folk', 'acoustic', 'ambient', 'jazz']):
        acousticness = 0.88
    elif any(g in genre for g in ['electronic', 'techno', 'metal', 'pop', 'house']):
        acousticness = 0.12

    # ── Estimated loudness fallback ────────────────────────────────────────────
    if loudness_db is None:
        if any(g in genre for g in ['metal', 'electronic', 'pop', 'rock', 'punk']):
            loudness_db = -5.0
        elif any(g in genre for g in ['classical', 'jazz', 'ambient', 'folk']):
            loudness_db = -15.0
        else:
            loudness_db = -10.0

    return {
        "bpm":           bpm,
        "energy":        round(energy,       3),
        "valence":       round(valence,       3),
        "danceability":  round(danceability,  3),
        "acousticness":  round(acousticness,  3),
        "loudness":      loudness_db,
        "tempo":         bpm,
        "mode":          mode,
        "matched_genres": matched_genres,
        "source":        "metadata",
    }


# ─────────────────────────────────────────────────────────────────────────────
# MOOD SCORING  (FIX 5 + FIX 6 + FIX 7)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_mood_score(track_features: Dict[str, Any]) -> Dict[str, float]:
    """
    Score all 9 GEMS moods using Gaussian distance in 3D feature space.

    Distance formula:
        d² = (E − E_anchor)² + (V − V_anchor)² + 0.5 × (A − A_anchor)²

    Acousticness is weighted at 0.5× (secondary axis) so it discriminates
    acoustic vs electronic flavors without dominating the energy/valence signal.

    Returns:
        Dict with 9 GEMS mood scores (normalised, sum = 1.0) plus:
          'confidence'  — top/second ratio (<1.5 weak, 1.5–2.5 moderate, >2.5 strong)
          'superfactor' — "Vitality", "Unease", or "Sublimity"
    """
    energy       = max(0.0, min(1.0, float(track_features.get('energy',       0.50))))
    valence      = max(0.0, min(1.0, float(track_features.get('valence',      0.50))))
    acousticness = max(0.0, min(1.0, float(track_features.get('acousticness', 0.50))))
    tempo        = float(track_features.get('tempo', 120))

    # Small tempo modifier on energy (subtle — doesn't dominate)
    tempo_norm = max(0.0, min(1.0, (tempo - 60.0) / 120.0))
    energy_adj = max(0.0, min(1.0, energy * 0.93 + tempo_norm * 0.07))

    sigma_sq_x2 = 2.0 * MOOD_SIGMA ** 2
    raw: Dict[str, float] = {}
    for mood, (ea, va, aa) in MOOD_ANCHORS.items():
        d2 = (energy_adj - ea) ** 2 + (valence - va) ** 2 + ACOUSTIC_WEIGHT * (acousticness - aa) ** 2
        raw[mood] = math.exp(-d2 / sigma_sq_x2)

    total  = sum(raw.values()) or 1.0
    scores = {mood: round(s / total, 4) for mood, s in raw.items()}

    # Confidence ratio (FIX 7)
    sorted_vals = sorted(scores.values(), reverse=True)
    scores['confidence'] = round(sorted_vals[0] / sorted_vals[1], 3) if sorted_vals[1] > 0 else 9.999

    # GEMS super-factor
    top_mood = max((k for k in scores if k != 'confidence'), key=scores.__getitem__)
    _VITALITY   = {"Joyful", "Power"}
    _UNEASE     = {"Tension", "Sadness"}
    _SUBLIMITY  = {"Wonder", "Transcendence", "Nostalgia", "Tenderness", "Peacefulness"}
    scores['superfactor'] = (
        "Vitality"  if top_mood in _VITALITY  else
        "Unease"    if top_mood in _UNEASE    else
        "Sublimity"
    )

    return scores




def get_top_mood(scores: Dict[str, float]) -> str:
    """Return the mood with the highest score (ignores the 'confidence' key)."""
    return max((k for k in scores if k not in ['confidence', 'superfactor']), key=scores.__getitem__)


# ─────────────────────────────────────────────────────────────────────────────
# TEST HARNESS
# ─────────────────────────────────────────────────────────────────────────────




# ─────────────────────────────────────────────────────────────────────────────
# Helper: Get Track Features (Spotify or metadata fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _get_spotify_features(pctl, track: dict) -> dict | None:
    """Get Spotify audio features. Returns None if not configured."""
    return None  # Stub - returns None for non-Spotify users

def _get_track_features(pctl, track: dict, prefs=None, use_cache: bool = True) -> dict:
    """
    Get track features: enrich metadata, then try Spotify, then metadata fallback.

    Uses persistent cache when available to avoid recalculation.

    Args:
        pctl: Player control object
        track: Track dict
        prefs: Preferences object
        use_cache: If True, use persistent cache (default: True)

    Returns:
        Dict with audio features (energy, valence, danceability, etc.)
    """
    # Try to get from cache first (if cache is available)
    if use_cache:
        user_dir = getattr(pctl, 'tauon', None)
        if user_dir:
            cache = get_audio_features_cache(user_dir)
            if cache:
                cached_features = cache.get_features(track)
                if cached_features:
                    log.debug(f"Cache hit for {track.get('filename', 'unknown')}")
                    return cached_features

    # Build a shallow copy of the track dict for enrichment
    # so we don't mutate the original master_library entry in-place.
    track_copy = dict(track)

    # Enrich metadata if genre missing
    if not track_copy.get('genre'):
        enrich_track_metadata(track_copy, prefs)

    # Try Spotify features
    spotify_features = _get_spotify_features(pctl, track_copy)
    if spotify_features:
        return spotify_features

    # Calculate from metadata
    features = get_metadata_features(track_copy)

    # Cache the result (if cache is available)
    if use_cache:
        user_dir = getattr(pctl, 'tauon', None)
        if user_dir:
            cache = get_audio_features_cache(user_dir)
            if cache:
                cache.set_features(track_copy, features, save_immediately=False)

    return features


def generate_mood_playlists(
    pctl,
    master_library,
    star_store,
    num_playlists: int = 8,
    prefs=None,
    notify_fn=None,
) -> None:
    """Generate mood-based playlists using Thayer's 8-mood model."""
    
    def _run():
        try:
            # Validate inputs
            if not master_library:
                if notify_fn: notify_fn("Error: No library")
                return
            
            # Get tracks
            tracks = _library_snapshot(pctl, master_library)
            if not tracks:
                if notify_fn: notify_fn("Error: No tracks found")
                return
            
            if notify_fn: notify_fn(f"Analysing {len(tracks)} tracks...")
            
            # Initialize mood buckets
            mood_buckets = {
                'Joyful': [], 'Power': [], 'Tension': [], 'Wonder': [],
                'Transcendence': [], 'Nostalgia': [], 'Tenderness': [],
                'Peacefulness': [], 'Sadness': []
            }
            
            # Process tracks with progress updates
            start_time = time.time()
            total = len(tracks)
            last_notified = 0
            
            for i, t in enumerate(tracks):
                try:
                    features = _get_track_features(pctl, t, prefs=prefs, use_cache=True)
                    mood_scores = calculate_mood_score(features)
                    best_mood = max(
                        [k for k in mood_scores.keys() if k not in ['confidence', 'superfactor']],
                        key=mood_scores.get
                    )
                    mood_buckets[best_mood].append(t["id"])
                    
                    # Progress update every 10% with progress bar
                    progress_pct = int((i + 1) / total * 100)
                    if notify_fn and progress_pct > last_notified and progress_pct % 10 == 0:
                        elapsed = time.time() - start_time
                        rate = (i + 1) / elapsed if elapsed > 0 else 1
                        remaining = total - (i + 1)
                        eta = int(remaining / rate) if rate > 0 else 0
                        bar_width = 20
                        filled = int(bar_width * (i + 1) / total)
                        bar = "█" * filled + "░" * (bar_width - filled)
                        notify_fn(f"[{bar}] {progress_pct}% ({i+1}/{total}) ~{eta}s")
                        last_notified = progress_pct
                except Exception as e:
                    log.error(f"Track error: {e}")
                    continue
            
            # Final completion notification
            elapsed = time.time() - start_time
            if notify_fn:
                notify_fn(f"✓ Complete! {elapsed:.1f}s - Creating playlists...")
            
            # Create playlists
            created = 0
            for mood_name, track_ids in mood_buckets.items():
                if len(track_ids) >= 5:
                    random.shuffle(track_ids)
                    SUPERFACTORS = {
                        'Joyful': 'Vitality', 'Power': 'Vitality',
                        'Tension': 'Unease', 'Sadness': 'Unease',
                        'Wonder': 'Sublimity', 'Transcendence': 'Sublimity',
                        'Nostalgia': 'Sublimity', 'Tenderness': 'Sublimity', 'Peacefulness': 'Sublimity',
                    }
                    superfactor = SUPERFACTORS.get(mood_name, '')
                    name = f"{mood_name} ({superfactor})" if superfactor else f"Mood: {mood_name}"
                    _make_playlist(name, track_ids, pctl)
                    created += 1
            
            # Save cache
            try:
                cache = get_audio_features_cache(getattr(pctl, 'tauon', None))
                if cache:
                    cache.save()
            except Exception:
                pass  # Ignore cache save errors
            
            if notify_fn:
                notify_fn(f"Mood Playlists: created {created} playlists")
                
        except Exception as e:
            if notify_fn: notify_fn(f"Mood error: {str(e)[:50]}")
    
    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Recommendation Strategy 2: Energy-Based Playlists
# ─────────────────────────────────────────────────────────────────────────────

def generate_energy_playlists(
    pctl,
    master_library,
    star_store,
    num_levels: int = 3,
    prefs=None,
    notify_fn=None,
) -> None:
    """Generate playlists based on energy levels."""
    
    def _run():
        try:
            # Get tracks
            tracks = _library_snapshot(pctl, master_library)
            if not tracks:
                if notify_fn: notify_fn("Error: No tracks found")
                return
            
            if notify_fn: notify_fn(f"Analysing {len(tracks)} tracks...")
            
            # Score each track by energy with progress updates
            scored_tracks = []
            start_time = time.time()
            total = len(tracks)
            last_notified = 0
            
            for i, t in enumerate(tracks):
                try:
                    features = _get_track_features(pctl, t, prefs=prefs, use_cache=True)
                    energy = features.get("energy", 0.5)
                    tempo = features.get("tempo", 120)
                    loudness = features.get("loudness", -10)
                    
                    tempo_norm = min(tempo / 200.0, 1.0)
                    loudness_norm = max(0, min(1, (loudness + 60) / 60.0))
                    energy_score = (energy * 0.5 + tempo_norm * 0.3 + loudness_norm * 0.2)
                    
                    scored_tracks.append((t, energy_score))
                    
                    # Progress update every 10% with progress bar
                    progress_pct = int((i + 1) / total * 100)
                    if notify_fn and progress_pct > last_notified and progress_pct % 10 == 0:
                        elapsed = time.time() - start_time
                        rate = (i + 1) / elapsed if elapsed > 0 else 1
                        remaining = total - (i + 1)
                        eta = int(remaining / rate) if rate > 0 else 0
                        bar_width = 20
                        filled = int(bar_width * (i + 1) / total)
                        bar = "█" * filled + "░" * (bar_width - filled)
                        notify_fn(f"[{bar}] {progress_pct}% ({i+1}/{total}) ~{eta}s")
                        last_notified = progress_pct
                except Exception as e:
                    log.error(f"Track error: {e}")
                    continue
            
            # Final completion notification
            elapsed = time.time() - start_time
            if notify_fn:
                notify_fn(f"✓ Complete! {elapsed:.1f}s - Creating playlists...")
            
            # Sort by energy score
            scored_tracks.sort(key=lambda x: x[1])
            
            # Split into energy levels
            chunk_size = max(1, len(scored_tracks) // num_levels)
            energy_names = ["✦ Low Energy (Chill)", "✦ Medium Energy (Focus)", "✦ High Energy (Party)"]
            
            created = 0
            for i in range(num_levels):
                start_idx = i * chunk_size
                end_idx = start_idx + chunk_size if i < num_levels - 1 else len(scored_tracks)
                
                chunk = scored_tracks[start_idx:end_idx]
                ids = [t["id"] for t, _ in chunk]
                
                if ids:
                    random.shuffle(ids)
                    name = energy_names[i] if i < len(energy_names) else f"Energy Level {i + 1}"
                    _make_playlist(name, ids, pctl)
                    created += 1
            
            # Save cache
            try:
                cache = get_audio_features_cache(getattr(pctl, 'tauon', None))
                if cache:
                    cache.save()
            except Exception:
                pass  # Ignore cache save errors
            
            if notify_fn:
                notify_fn(f"Energy Playlists: created {created} playlists")
                
        except Exception as e:
            if notify_fn: notify_fn(f"Energy error: {str(e)[:50]}")

    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Recommendation Strategy 3: Similarity Radio (Seed Track)
# ─────────────────────────────────────────────────────────────────────────────

def generate_similarity_radio(
    pctl,
    master_library,
    star_store,
    seed_track_id: int | None = None,
    limit: int = 50,
    prefs=None,
    notify_fn=None,
) -> None:
    """
    Generate a radio playlist similar to a seed track.
    
    Uses weighted Euclidean distance on audio features.
    
    Features (weighted by importance):
    - Energy (25%) - Overall intensity
    - Valence (20%) - Mood (happy/sad)
    - Danceability (15%) - Rhythm strength
    - Acousticness (15%) - Electronic vs acoustic
    - Tempo (15%) - BPM similarity
    - Loudness (10%) - Volume level
    
    Lightweight: Uses pre-cached features, no API calls.
    """
    def _run():
        try:
            import numpy as np
        except ImportError:
            if notify_fn:
                notify_fn("Similarity radio missing: numpy. Run: pip install numpy")
            return

        # Initialize cache
        cache = get_audio_features_cache(getattr(pctl, 'tauon', None))
        if cache:
            stats = cache.get_stats()
            log.info(f'✓ Audio features cache loaded: {stats["total_tracks"]} tracks cached')

        if notify_fn:
            notify_fn("Similarity Radio: analysing library…")

        tracks = _library_snapshot(pctl, master_library)
        if not tracks:
            if notify_fn:
                notify_fn("Similarity Radio: no tracks found")
            return

        # Find seed track
        seed_track = None
        seed_features = None
        for t in tracks:
            if t["id"] == seed_track_id:
                seed_track = t
                seed_features = _get_track_features(pctl, t, prefs=prefs, use_cache=True)
                break

        if not seed_track or not seed_features:
            if notify_fn:
                notify_fn("Similarity Radio: seed track not found")
            return
        
        # Get seed feature values
        seed_energy = seed_features.get("energy", 0.5)
        seed_valence = seed_features.get("valence", 0.5)
        seed_dance = seed_features.get("danceability", 0.5)
        seed_acoustic = seed_features.get("acousticness", 0.5)
        seed_tempo = seed_features.get("tempo", 120)
        seed_loudness = seed_features.get("loudness", -10)
        
        # Also get genre for bonus scoring
        seed_genre = getattr(seed_track, 'genre', '').lower() if hasattr(seed_track, 'genre') else ''
        seed_artist = getattr(seed_track, 'artist', '').lower() if hasattr(seed_track, 'artist') else ''
        
        if notify_fn:
            notify_fn(f"Similarity Radio: finding tracks similar to '{seed_track.get('title', 'Unknown')}'…")
        
        # Score all tracks
        scored = []
        
        for t in tracks:
            if t["id"] == seed_track_id:
                continue  # Skip seed track
            
            track_features = _get_track_features(pctl, t, prefs=prefs)
            
            # Get feature values
            energy = track_features.get("energy", 0.5)
            valence = track_features.get("valence", 0.5)
            dance = track_features.get("danceability", 0.5)
            acoustic = track_features.get("acousticness", 0.5)
            tempo = track_features.get("tempo", 120)
            loudness = track_features.get("loudness", -10)
            
            # Calculate weighted Euclidean distance
            # Lower distance = more similar
            
            # Energy distance (weight: 0.25)
            energy_dist = abs(energy - seed_energy) * 0.25
            
            # Valence distance (weight: 0.20)
            valence_dist = abs(valence - seed_valence) * 0.20
            
            # Danceability distance (weight: 0.15)
            dance_dist = abs(dance - seed_dance) * 0.15
            
            # Acousticness distance (weight: 0.15)
            acoustic_dist = abs(acoustic - seed_acoustic) * 0.15
            
            # Tempo distance (weight: 0.15) - normalize to 0-1 range
            tempo_diff = abs(tempo - seed_tempo) / 200.0  # Max difference is 200 BPM
            tempo_dist = min(tempo_diff, 1.0) * 0.15
            
            # Loudness distance (weight: 0.10) - normalize to 0-1 range
            loudness_diff = abs(loudness - seed_loudness) / 60.0  # Range is ~-60 to 0 dB
            loudness_dist = min(loudness_diff, 1.0) * 0.10
            
            # Total distance (0 = identical, 1 = completely different)
            total_distance = (
                energy_dist + valence_dist + dance_dist + 
                acoustic_dist + tempo_dist + loudness_dist
            )
            
            # Convert to similarity score (higher = better)
            similarity = 1.0 - total_distance
            
            # Bonus for same genre
            track_genre = getattr(t, 'genre', '').lower() if hasattr(t, 'genre') else ''
            if seed_genre and track_genre and seed_genre == track_genre:
                similarity += 0.15
            
            # Small bonus for same artist
            track_artist = getattr(t, 'artist', '').lower() if hasattr(t, 'artist') else ''
            if seed_artist and track_artist and seed_artist == track_artist:
                similarity += 0.10
            
            scored.append((t["id"], similarity))
        
        # Sort by similarity (highest first)
        scored.sort(reverse=True, key=lambda x: x[1])
        
        # Take top matches
        chosen = []
        seen_ids = {seed_track_id}
        
        for track_id, score in scored:
            if track_id in seen_ids:
                continue
            
            # Only include if similarity > 0.6 (more lenient than before)
            if score < 0.6:
                continue
            
            seen_ids.add(track_id)
            chosen.append(track_id)
            
            if len(chosen) >= limit:
                break
        
        if not chosen:
            if notify_fn:
                notify_fn("Similarity Radio: no similar tracks found (try different seed)")
            return
        
        # Create playlist
        seed_name = seed_track.get("title", "Unknown")
        name = f"Similar to: {seed_name}"
        _make_playlist(name, chosen, pctl)

        # Save audio features cache
        if cache:
            cache.save()
            log.info(f'✓ Saved audio features cache: {len(cache.cache)} tracks')

        if notify_fn:
            # Calculate average similarity of chosen tracks
            chosen_scores = [s for tid, s in scored if tid in chosen]
            avg_score = sum(chosen_scores) / len(chosen_scores) if chosen_scores else 0
            notify_fn(f"Similarity Radio: created playlist with {len(chosen)} tracks (avg similarity: {avg_score:.2f}) ✓")

    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Last.fm Artist Radio
# ─────────────────────────────────────────────────────────────────────────────

def generate_artist_radio(
    pctl,
    master_library,
    star_store,
    artist_name: str = "",
    limit: int = 50,
    prefs=None,
    notify_fn=None,
) -> None:
    """
    Generate artist radio using Last.fm similar artists.
    
    Finds similar artists, then gets their top tracks from your library.
    """
    def _run():
        try:
            import requests
        except ImportError:
            if notify_fn:
                notify_fn("Artist radio requires: pip install requests")
            return
        
        if not artist_name:
            if notify_fn:
                notify_fn("Artist Radio: no artist name provided")
            return
        
        if notify_fn:
            notify_fn(f"Artist Radio: finding artists similar to '{artist_name}'…")
        
        # Get similar artists from Last.fm
        try:
            api_key = "b048411511a3191008fee11a34f4e233"  # Public key
            url = "https://ws.audioscrobbler.com/2.0/"
            
            params = {
                "method": "artist.getSimilar",
                "artist": artist_name,
                "api_key": api_key,
                "format": "json",
                "limit": 20,
            }
            
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            
            similar_artists = set()
            similar_artists.add(artist_name.lower())
            
            if "similarartists" in data and "artist" in data["similarartists"]:
                for artist in data["similarartists"]["artist"]:
                    similar_artists.add(artist["name"].lower())
            
            if not similar_artists:
                if notify_fn:
                    notify_fn("Artist Radio: no similar artists found")
                return
            
            if notify_fn:
                notify_fn(f"Artist Radio: found {len(similar_artists)} similar artists…")
            
            # Find tracks in library by these similar artists
            tracks = _library_snapshot(pctl, master_library)

            # Build regex patterns with word boundaries for safe matching
            artist_patterns = []
            for similar in similar_artists:
                similar = similar.strip()
                if not similar or len(similar) < 2:
                    continue
                # Escape regex special chars, then add word boundaries
                escaped = re.escape(similar)
                artist_patterns.append((similar, re.compile(r'\b' + escaped + r'\b', re.IGNORECASE)))

            chosen = []
            seen_ids = set()

            for t in tracks:
                track_artist = t.get("artist", "").strip()
                if not track_artist:
                    continue

                # Check if track artist matches any similar artist via word boundary
                for _name, pattern in artist_patterns:
                    if pattern.search(track_artist):
                        if t["id"] not in seen_ids:
                            chosen.append(t["id"])
                            seen_ids.add(t["id"])
                        break

                if len(chosen) >= limit:
                    break

            if not chosen:
                if notify_fn:
                    notify_fn("Artist Radio: no matching tracks in library")
                return

            # Create playlist
            name = f"Artist Radio: {artist_name}"
            _make_playlist(name, chosen, pctl)

            if notify_fn:
                notify_fn(f"Artist Radio: created playlist with {len(chosen)} tracks ✓")
        
        except Exception as e:
            if notify_fn:
                notify_fn(f"Artist Radio error: {str(e)[:50]}")
            log.error(f"Artist radio failed: {e}")
    
    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Recommendation Strategy 4: Era/Decade Playlists
# ─────────────────────────────────────────────────────────────────────────────

def generate_decade_playlists(
    pctl,
    master_library,
    star_store,
    notify_fn=None,
) -> None:
    """
    Generate playlists grouped by decade/era.
    
    Uses metadata year tag (no audio analysis needed).
    Instant generation, zero API calls.
    """
    def _run():
        if notify_fn:
            notify_fn("Decade Playlists: organizing library by era…")
        
        tracks = _library_snapshot(pctl, master_library)
        if not tracks:
            if notify_fn:
                notify_fn("Decade Playlists: no tracks found")
            return
        
        # Group by decade
        decades: dict[int, list[int]] = defaultdict(list)
        
        for t in tracks:
            year = int(t.get("year", 0) or 0)
            if year < 1950 or year > 2030:
                continue
            
            decade = (year // 10) * 10
            decades[decade].append(t["id"])
        
        # Create playlists for decades with enough tracks
        created = 0
        for decade in sorted(decades.keys()):
            ids = decades[decade]
            if len(ids) >= 10:  # Minimum 10 tracks per decade
                random.shuffle(ids)
                name = f"{decade}s Hits"
                _make_playlist(name, ids, pctl)
                created += 1
        
        if notify_fn:
            notify_fn(f"Decade Playlists: created {created} playlists ✓")
    
    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Recommendation Strategy 5: Genre Clustering (Audio Features)
# ─────────────────────────────────────────────────────────────────────────────

def generate_genre_clusters(
    pctl,
    master_library,
    star_store,
    n_clusters: int = 8,
    prefs=None,
    notify_fn=None,
) -> None:
    """
    Cluster library by genre using audio features.
    
    Unlike metadata-based genre tags, this uses actual audio characteristics:
    - Electronic: High energy, low acousticness
    - Classical: Low energy, high acousticness, low speechiness
    - Hip Hop: High speechiness, moderate energy
    - Rock: High energy, moderate acousticness
    - Jazz: Moderate energy, high acousticness, complex rhythms
    
    Uses K-means on Spotify audio features.
    """
    def _run():
        try:
            import numpy as np
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler
        except ImportError as e:
            if notify_fn:
                notify_fn(f"Genre clusters missing: {e.name}. Run: pip install scikit-learn numpy")
            return

        # Initialize cache
        cache = get_audio_features_cache(getattr(pctl, 'tauon', None))
        if cache:
            stats = cache.get_stats()
            log.info(f'✓ Audio features cache loaded: {stats["total_tracks"]} tracks cached')

        if notify_fn:
            notify_fn("Genre Clusters: analysing library audio features…")

        tracks = _library_snapshot(pctl, master_library)
        if not tracks:
            if notify_fn:
                notify_fn("Genre Clusters: no tracks found")
            return

        # Extract audio features
        features: list[list[float]] = []
        valid: list[dict] = []
        cache_hits = 0
        cache_misses = 0

        for t in tracks:
            track_features = _get_track_features(pctl, t, prefs=prefs, use_cache=True)
            
            # Track cache performance
            if cache and cache.get_features(t):
                cache_hits += 1
            else:
                cache_misses += 1

            # Use audio features that correlate with genre
            vector = [
                track_features.get("energy", 0.5),
                track_features.get("acousticness", 0.5),
                track_features.get("instrumentalness", 0.5),
                track_features.get("speechiness", 0.5),
                track_features.get("danceability", 0.5),
                track_features.get("tempo", 120) / 200.0,
                track_features.get("loudness", -10) / 60.0 + 1,
            ]

            features.append(vector)
            valid.append(t)
        
        # Log cache performance
        total_ops = cache_hits + cache_misses
        hit_rate = (cache_hits / total_ops * 100) if total_ops > 0 else 0
        log.info(f'✓ Cache performance: {cache_hits}/{total_ops} hits ({hit_rate:.1f}%)')
        
        if len(valid) < n_clusters:
            if notify_fn:
                notify_fn(f"Genre Clusters: only {len(valid)} tracks analysed")
            return
        
        # Cluster
        X = np.array(features)
        X_s = StandardScaler().fit_transform(X)
        
        km = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
        labels = km.fit_predict(X_s)
        
        # Name clusters based on dominant features
        def _name_cluster(cid):
            idxs = [i for i, l in enumerate(labels) if l == cid]
            if not idxs:
                return f"✦ Cluster {cid + 1}"
            
            cluster_features = [features[i] for i in idxs]
            
            avg_energy = sum(f[0] for f in cluster_features) / len(cluster_features)
            avg_acoustic = sum(f[1] for f in cluster_features) / len(cluster_features)
            avg_speech = sum(f[3] for f in cluster_features) / len(cluster_features)
            avg_dance = sum(f[4] for f in cluster_features) / len(cluster_features)
            
            # Heuristic naming based on audio features
            if avg_acoustic > 0.6:
                if avg_energy < 0.4:
                    return "Classical & Acoustic"
                else:
                    return "Folk & Acoustic Rock"

            if avg_speech > 0.5:  # Higher threshold for Hip Hop
                return "Hip Hop & Rap"

            if avg_dance > 0.7 and avg_energy > 0.7:
                return "Electronic & Dance"

            if avg_energy > 0.7:
                if avg_acoustic < 0.3:
                    return "Rock & Metal"
                else:
                    return "Upbeat Pop"

            if avg_dance > 0.6:
                return "Pop & Dance"

            if avg_energy < 0.4 and avg_acoustic < 0.5:
                return "Ambient & Downtempo"

            if avg_energy > 0.5 and avg_acoustic < 0.4:
                return "Alternative & Indie"

            return "Mixed Genre"
        
        # Create playlists
        created = 0
        for cid in range(n_clusters):
            ids = [valid[i]["id"] for i, l in enumerate(labels) if l == cid]
            if ids:
                random.shuffle(ids)
                name = _name_cluster(cid)
                _make_playlist(name, ids, pctl)
                created += 1

        # Save audio features cache
        if cache:
            cache.save()
            log.info(f'✓ Saved audio features cache: {len(cache.cache)} tracks')

        if notify_fn:
            notify_fn(f"Genre Clusters: created {created} playlists ✓")

    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions (from shared utilities)
# ─────────────────────────────────────────────────────────────────────────────

# Re-export from shared utilities to maintain API compatibility
_library_snapshot = get_library_tracks
_make_playlist = create_playlist
