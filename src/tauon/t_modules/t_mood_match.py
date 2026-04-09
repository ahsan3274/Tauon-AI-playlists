"""
t_mood_match.py — Smart Mood-Based Discovery
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Replaces the old "analyze entire library into 8 moods" approach.

Three modes:
  1. Mood Match      — Extend your current listening vibe
  2. Mood Transition — Gradually shift from current mood to target mood
  3. Discover Moods  — Find moods in your library you've been missing

Plus a mood word generator for unique, evocative playlist names.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

log = logging.getLogger("t_mood_match")

# ─────────────────────────────────────────────────────────────────────────────
# Mood Word Generator — Evocative playlist names
# ─────────────────────────────────────────────────────────────────────────────

# Each mood anchor gets multiple evocative names, combined with modifiers
_MOOD_NAMES: dict[str, list[str]] = {
    "Joyful":          [
        "Sunlit", "Golden Hour", "Bright Eyes", "Morning Light",
        "Electric Smiles", "Dancing Shadows", "Neon Joy", "Radiant",
    ],
    "Power":           [
        "Drive", "Unstoppable", "Iron Pulse", "Full Throttle",
        "Concrete", "Storm Front", "Adrenaline", "Raw Force",
    ],
    "Tension":         [
        "Edge", "Dark Current", "Pressure", "Red Wire",
        "Static", "Undercurrent", "Fracture", "Breaking Point",
    ],
    "Wonder":          [
        "Starfall", "Horizons", "Luminous", "First Snow",
        "Open Sky", "Crystal", "Echoes", "Silver Lining",
    ],
    "Transcendence":   [
        "Ascend", "Above Clouds", "Orbit", "Aether",
        "Elevate", "Drift", "Afterglow", "Infinite",
    ],
    "Nostalgia":       [
        "Faded Photograph", "Old Films", "Summer '99", "Last Train Home",
        "Dusty Tapes", "Remember When", "Amber", "Yesterday",
    ],
    "Tenderness":      [
        "Soft Focus", "Whisper", "Velvet", "Warm Light",
        "Gentle Rain", "Hush", "Cotton", "Silk Road",
    ],
    "Peacefulness":    [
        "Still Water", "Quiet Hours", "Zen Garden", "Breath",
        "Open Field", "Slow Motion", "Calm Seas", "Hollow Tree",
    ],
    "Sadness":         [
        "Rainy Window", "Empty Rooms", "Blue Hour", "Fading",
        "Last Dance", "Grey Skies", "Wistful", "Half Light",
    ],
}

_MODIFIERS = [
    "Sessions", "Mix", "Collection", "Playlist", "Vibes",
    "Selections", "Chronicles", "Tapes", "Diary",
]

_TIME_MODIFIERS = {
    "night":   ["Midnight", "3AM", "Late Night", "After Dark"],
    "morning": ["Dawn", "Early", "First Light", "Waking"],
    "rain":    ["Rainy Day", "Storm Watch", "Wet Streets", "Drizzle"],
}


def generate_mood_name(mood: str, features: list[dict] | None = None,
                       context: str = "") -> str:
    """
    Generate a unique, evocative playlist name.

    Args:
        mood: Base mood anchor (e.g. "Joyful", "Nostalgia")
        features: List of track feature dicts (for energy-based modifier)
        context: Optional context hint ("night", "morning", "rain")

    Returns:
        e.g. "Sunlit Sessions", "Rainy Window Tapes", "3AM Velvet"
    """
    names = _MOOD_NAMES.get(mood, ["Untitled"])
    base = random.choice(names)

    # Add time-of-day modifier if context provided
    if context and context in _TIME_MODIFIERS:
        time_word = random.choice(_TIME_MODIFIERS[context])
        return f"{time_word} — {base}"

    # Add suffix
    suffix = random.choice(_MODIFIERS)
    return f"{base} {suffix}"


# ─────────────────────────────────────────────────────────────────────────────
# Mood Analysis
# ─────────────────────────────────────────────────────────────────────────────

def classify_track(track: dict, features: dict) -> tuple[str, dict]:
    """
    Classify a track's dominant mood from its audio features.

    Returns (mood_name, mood_scores_dict)
    """
    try:
        from tauon.t_modules.t_playlist_gen_v2 import (
            calculate_mood_score,
            get_metadata_features,
        )
    except ImportError:
        return "Unknown", {}

    # Use pre-computed features or compute from metadata
    if features and features.get("energy") is not None:
        track_features = features
    else:
        track_features = get_metadata_features(track)

    scores = calculate_mood_score(track_features)
    top_mood = max(
        (k for k in scores if k not in ("confidence", "superfactor")),
        key=scores.get,
    )
    return top_mood, scores


# ─────────────────────────────────────────────────────────────────────────────
# Mode 1: Mood Match — extend current listening vibe
# ─────────────────────────────────────────────────────────────────────────────

def mood_match(
    seed_track_id: int,
    master_library: dict,
    pctl,
    prefs=None,
    notify_fn=None,
) -> None:
    """
    Find tracks in the SAME mood as the seed track.

    Instead of analyzing the whole library into 8 buckets,
    this finds tracks that share the seed's dominant mood.
    """
    def _run():
        try:
            from tauon.t_modules.t_playlist_gen_v2 import (
                _get_track_features,
                calculate_mood_score,
                get_metadata_features,
                get_audio_features_cache,
            )
            from tauon.t_modules.t_utils_playlist import create_playlist
        except ImportError:
            if notify_fn:
                notify_fn("Mood Match requires: pip install numpy")
            return

        seed = master_library.get(seed_track_id)
        if not seed:
            if notify_fn:
                notify_fn("Seed track not found")
            return

        if notify_fn:
            notify_fn("Mood Match: analyzing…")

        # Get seed mood
        seed_features = _get_track_features(pctl, _track_to_dict(seed), prefs=prefs)
        seed_mood, seed_scores = classify_track(_track_to_dict(seed), seed_features)
        seed_score_val = seed_scores.get(seed_mood, 0)

        if notify_fn:
            notify_fn(f"Mood Match: seed is '{seed_mood}' — finding similar tracks…")

        # Score all library tracks
        matches = []
        for tid, tr in master_library.items():
            if tid == seed_track_id:
                continue
            t_dict = _track_to_dict(tr)
            t_features = _get_track_features(pctl, t_dict, prefs=prefs)
            t_scores = calculate_mood_score(t_features)
            t_mood = max(
                (k for k in t_scores if k not in ("confidence", "superfactor")),
                key=t_scores.get,
            )

            # Match if same mood OR high score overlap
            if t_mood == seed_mood:
                score = t_scores.get(seed_mood, 0)
                matches.append((score, tid))
            else:
                # Partial match: if this track has a decent score for the seed mood
                partial = t_scores.get(seed_mood, 0)
                if partial > 0.15:
                    matches.append((partial, tid))

        if not matches:
            if notify_fn:
                notify_fn(f"Mood Match: no other '{seed_mood}' tracks in library")
            return

        # Sort by mood score, shuffle ties for variety
        matches.sort(key=lambda x: -x[0])

        # Group by score tier to maintain variety
        tier_1 = [tid for s, tid in matches if s > 0.4]
        tier_2 = [tid for s, tid in matches if 0.25 < s <= 0.4]
        tier_3 = [tid for s, tid in matches if s <= 0.25]

        random.shuffle(tier_1)
        random.shuffle(tier_2)
        random.shuffle(tier_3)

        # Build playlist: mostly strong matches, some variety
        chosen = tier_1[:30] + tier_2[:15] + tier_3[:5]

        # Generate unique name
        name = generate_mood_name(seed_mood)

        idx = create_playlist(name, chosen, pctl)
        if idx >= 0:
            if notify_fn:
                notify_fn(f"Mood Match: created '{name}' — {len(chosen)} tracks in {seed_mood} mood ✓")

    import threading
    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Mode 2: Mood Transition — shift from current to target mood
# ─────────────────────────────────────────────────────────────────────────────

# Transition pairs that make musical sense (research-backed)
_TRANSITIONS = {
    "Joyful":          ["Transcendence", "Power", "Wonder"],
    "Power":           ["Joyful", "Tension", "Transcendence"],
    "Tension":         ["Power", "Sadness", "Nostalgia"],
    "Wonder":          ["Transcendence", "Joyful", "Peacefulness"],
    "Transcendence":   ["Wonder", "Peacefulness", "Joyful"],
    "Nostalgia":       ["Tenderness", "Sadness", "Peacefulness"],
    "Tenderness":      ["Peacefulness", "Nostalgia", "Wonder"],
    "Peacefulness":    ["Tenderness", "Wonder", "Nostalgia"],
    "Sadness":         ["Nostalgia", "Tenderness", "Tension"],
}


def mood_transition(
    seed_track_id: int,
    target_mood: str,
    master_library: dict,
    pctl,
    prefs=None,
    notify_fn=None,
) -> None:
    """
    Create a playlist that transitions from the seed track's mood
    to a target mood — based on emotional regulation research.
    """
    def _run():
        try:
            from tauon.t_modules.t_playlist_gen_v2 import (
                _get_track_features,
                calculate_mood_score,
                get_metadata_features,
            )
            from tauon.t_modules.t_utils_playlist import create_playlist
        except ImportError:
            if notify_fn:
                notify_fn("Mood Transition requires: pip install numpy")
            return

        seed = master_library.get(seed_track_id)
        if not seed:
            if notify_fn:
                notify_fn("Seed track not found")
            return

        if notify_fn:
            notify_fn("Mood Transition: analyzing…")

        # Get seed mood
        seed_features = _get_track_features(pctl, _track_to_dict(seed), prefs=prefs)
        seed_mood, seed_scores = classify_track(_track_to_dict(seed), seed_features)

        # Score all tracks
        mood_classified: dict[str, list[tuple[float, int]]] = {}
        for tid, tr in master_library.items():
            if tid == seed_track_id:
                continue
            t_dict = _track_to_dict(tr)
            t_features = _get_track_features(pctl, t_dict, prefs=prefs)
            t_scores = calculate_mood_score(t_features)
            t_mood = max(
                (k for k in t_scores if k not in ("confidence", "superfactor")),
                key=t_scores.get,
            )
            score = t_scores.get(t_mood, 0)
            mood_classified.setdefault(t_mood, []).append((score, tid))

        # Build transition: seed mood → intermediate → target mood
        intermediates = _TRANSITIONS.get(seed_mood, [])
        if target_mood in intermediates:
            path = [seed_mood, target_mood]
        elif intermediates:
            # Find best intermediate that connects to target
            best_mid = intermediates[0]
            for mid in intermediates:
                if target_mood in _TRANSITIONS.get(mid, []):
                    best_mid = mid
                    break
            path = [seed_mood, best_mid, target_mood]
        else:
            path = [seed_mood, target_mood]

        if notify_fn:
            notify_fn(f"Mood Transition: {' → '.join(path)}")

        # Build the playlist with tracks from each stage
        chosen = []
        for stage_mood in path:
            tracks_in_mood = mood_classified.get(stage_mood, [])
            tracks_in_mood.sort(key=lambda x: -x[0])
            random.shuffle(tracks_in_mood)
            stage_tracks = [tid for _, tid in tracks_in_mood[:12]]
            chosen.extend(stage_tracks)

        if not chosen:
            if notify_fn:
                notify_fn(f"Mood Transition: not enough tracks for this path")
            return

        name = f"{generate_mood_name(seed_mood)} → {generate_mood_name(target_mood)}"
        idx = create_playlist(name, chosen, pctl)
        if idx >= 0:
            if notify_fn:
                notify_fn(f"Mood Transition: created '{name}' — {len(chosen)} tracks ✓")

    import threading
    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Mode 3: Discover Moods — fill blind spots
# ─────────────────────────────────────────────────────────────────────────────

def discover_moods(
    master_library: dict,
    listen_history_path: str | None = None,
    pctl=None,
    prefs=None,
    notify_fn=None,
) -> None:
    """
    Analyze which moods you're missing from your library/listening,
    then create a playlist from underexplored moods.
    """
    def _run():
        try:
            from tauon.t_modules.t_playlist_gen_v2 import (
                _get_track_features,
                calculate_mood_score,
                get_metadata_features,
            )
            from tauon.t_modules.t_utils_playlist import create_playlist
        except ImportError:
            if notify_fn:
                notify_fn("Discover Moods requires: pip install numpy")
            return

        if notify_fn:
            notify_fn("Discover Moods: analyzing your library…")

        # Classify every track
        mood_counts: dict[str, int] = {}
        mood_tracks: dict[str, list[int]] = {}
        total = 0

        for tid, tr in master_library.items():
            t_dict = _track_to_dict(tr)
            t_features = _get_track_features(pctl, t_dict, prefs=prefs)
            t_scores = calculate_mood_score(t_features)
            t_mood = max(
                (k for k in t_scores if k not in ("confidence", "superfactor")),
                key=t_scores.get,
            )
            mood_counts[t_mood] = mood_counts.get(t_mood, 0) + 1
            mood_tracks.setdefault(t_mood, []).append(tid)
            total += 1

        if total == 0:
            if notify_fn:
                notify_fn("Discover Moods: no tracks in library")
            return

        # Find least-represented moods
        sorted_moods = sorted(mood_counts.items(), key=lambda x: x[1])
        rarest = sorted_moods[:2]  # Top 2 least common moods

        # Build playlists from rare moods
        created = 0
        for mood, count in rarest:
            pct = count / total * 100
            tracks = mood_tracks.get(mood, [])
            random.shuffle(tracks)

            name = generate_mood_name(mood, context="")
            idx = create_playlist(f"{name} (Rare: {count} tracks, {pct:.0f}%)", tracks[:40], pctl)
            if idx >= 0:
                created += 1

        # Summary
        mood_summary = ", ".join(f"{m}: {c}" for m, c in sorted_moods)
        if notify_fn:
            notify_fn(
                f"Discover Moods: least explored — {', '.join(m for m, _ in rarest)}. "
                f"Created {created} playlists. Full distribution: {mood_summary}"
            )

    import threading
    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _track_to_dict(track) -> dict:
    """Convert a TrackClass object to dict for feature extraction."""
    return {
        "genre": getattr(track, "genre", "") or "",
        "bpm": getattr(track, "bpm", 0) or (getattr(track, "misc", {}).get("bpm", 0) or 0),
        "mode": getattr(track, "mode", None),
        "loudness": getattr(track, "misc", {}).get("replaygain_track_gain") or getattr(track, "misc", {}).get("loudness"),
        "title": getattr(track, "title", "") or "",
        "artist": getattr(track, "artist", "") or "",
    }
