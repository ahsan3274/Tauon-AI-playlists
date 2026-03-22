"""
t_mood_visualizer.py - Mood Visualization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Visual representation of music mood distribution using Thayer's 8-mood model.

Features:
- Thayer's Mood Wheel (8 moods in 2D space)
- Library mood distribution chart
- Color-coded mood badges
- Interactive mood filtering

Based on IEEE paper: "An Efficient Classification Algorithm for Music Mood Detection"
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

log = logging.getLogger("t_mood_visualizer")


# ─────────────────────────────────────────────────────────────────────────────
# Thayer's 8-Mood Model - Color Coding
# ─────────────────────────────────────────────────────────────────────────────

# Mood colors (RGB) based on psychological color associations
MOOD_COLORS = {
    'Exuberant':   (255, 215, 0),    # Gold - excited, energetic
    'Energetic':   (255, 69, 0),     # Red-orange - high energy
    'Frantic':     (139, 0, 0),      # Dark red - intense, chaotic
    'Happy':       (255, 182, 193),  # Light pink - cheerful
    'Contentment': (144, 238, 144),  # Light green - peaceful, satisfied
    'Calm':        (135, 206, 235),  # Sky blue - serene, tranquil
    'Sad':         (119, 136, 153),  # Light slate gray - melancholic
    'Depression':  (75, 75, 75),     # Dark gray - very low mood
}

# Mood positions on Thayer's 2D plane (Energy vs Valence)
# Energy: 0 (low) to 1 (high)
# Valence: 0 (negative/sad) to 1 (positive/happy)
MOOD_POSITIONS = {
    'Exuberant':   {'energy': 0.8, 'valence': 0.9},  # High energy, very happy
    'Energetic':   {'energy': 0.9, 'valence': 0.5},  # Very high energy, neutral
    'Frantic':     {'energy': 0.9, 'valence': 0.2},  # High energy, tense
    'Happy':       {'energy': 0.6, 'valence': 0.9},  # Medium-high energy, very happy
    'Contentment': {'energy': 0.3, 'valence': 0.8},  # Low energy, happy
    'Calm':        {'energy': 0.1, 'valence': 0.5},  # Very low energy, neutral
    'Sad':         {'energy': 0.3, 'valence': 0.2},  # Low energy, sad
    'Depression':  {'energy': 0.1, 'valence': 0.1},  # Very low energy, very sad
}


def get_mood_color(mood_name: str) -> tuple[int, int, int]:
    """Get RGB color for a mood."""
    return MOOD_COLORS.get(mood_name, (128, 128, 128))  # Gray fallback


def get_mood_position(mood_name: str) -> dict[str, float]:
    """Get 2D position (energy, valence) for a mood."""
    return MOOD_POSITIONS.get(mood_name, {'energy': 0.5, 'valence': 0.5})


# ─────────────────────────────────────────────────────────────────────────────
# Mood Distribution Analysis
# ─────────────────────────────────────────────────────────────────────────────

def analyze_library_moods(pctl, master_library, star_store) -> dict[str, list[int]]:
    """
    Analyze mood distribution of entire library.

    Returns dict mapping mood names to lists of track IDs.
    """
    from tauon.t_modules.t_playlist_gen_v2 import calculate_mood_score, _get_track_features

    mood_buckets = {
        'Exuberant': [],
        'Energetic': [],
        'Frantic': [],
        'Happy': [],
        'Contentment': [],
        'Calm': [],
        'Sad': [],
        'Depression': []
    }

    tracks = []
    # Collect all track IDs that appear in any playlist
    referenced: set[int] = set()
    for pl in pctl.multi_playlist:
        if hasattr(pl, 'playlist_ids'):
            referenced.update(pl.playlist_ids)
        elif hasattr(pl, 'playlist'):
            referenced.update(pl.playlist)

    for tid, tr in master_library.items():
        if tid not in referenced:
            continue

        tracks.append({
            "id": tid,
            "track": tr,
        })

    # Analyze each track
    for t in tracks:
        # Get actual track features using the same function as playlist generation
        track_features = _get_track_features(pctl, t["track"])

        # Calculate mood scores
        mood_scores = calculate_mood_score(track_features)

        # Assign to best mood
        best_mood = max(mood_scores, key=mood_scores.get)
        mood_buckets[best_mood].append(t["id"])

    return mood_buckets


def get_mood_statistics(mood_buckets: dict[str, list[int]]) -> dict[str, dict]:
    """
    Calculate statistics for mood distribution.
    
    Returns dict with:
    - count: number of tracks
    - percentage: percentage of total
    - color: RGB color tuple
    - position: 2D position (energy, valence)
    """
    total = sum(len(tracks) for tracks in mood_buckets.values())
    
    stats = {}
    for mood_name, track_ids in mood_buckets.items():
        count = len(track_ids)
        percentage = (count / total * 100) if total > 0 else 0
        
        stats[mood_name] = {
            'count': count,
            'percentage': round(percentage, 1),
            'color': get_mood_color(mood_name),
            'position': get_mood_position(mood_name),
        }
    
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Text-Based Mood Wheel (for console/notifications)
# ─────────────────────────────────────────────────────────────────────────────

def generate_mood_wheel_text(stats: dict[str, dict]) -> str:
    """
    Generate ASCII art mood wheel for console display.
    
    Shows mood distribution in a circular layout.
    """
    wheel = []
    wheel.append("╔══════════════════════════════════════════╗")
    wheel.append("║       🎵  Thayer's Mood Wheel  🎵        ║")
    wheel.append("╠══════════════════════════════════════════╣")
    wheel.append("║                                          ║")
    
    # Top row (high energy moods)
    top_moods = ['Frantic', 'Energetic', 'Exuberant', 'Happy']
    top_line = "║  "
    for mood in top_moods:
        if mood in stats:
            count = stats[mood]['count']
            pct = stats[mood]['percentage']
            if count > 0:
                top_line += f"{mood[:8]:<9} {pct:>5.1f}%  "
            else:
                top_line += f"{'':<15}"
    top_line += " ║"
    wheel.append(top_line)
    
    wheel.append("║                                          ║")
    
    # Middle row (medium energy)
    wheel.append("║          Energy →                          ║")
    
    wheel.append("║                                          ║")
    
    # Bottom row (low energy moods)
    bottom_moods = ['Depression', 'Sad', 'Calm', 'Contentment']
    bottom_line = "║  "
    for mood in bottom_moods:
        if mood in stats:
            count = stats[mood]['count']
            pct = stats[mood]['percentage']
            if count > 0:
                bottom_line += f"{mood[:8]:<9} {pct:>5.1f}%  "
            else:
                bottom_line += f"{'':<15}"
    bottom_line += " ║"
    wheel.append(bottom_line)
    
    wheel.append("║                                          ║")
    wheel.append("╠══════════════════════════════════════════╣")
    
    # Summary
    total = sum(s['count'] for s in stats.values())
    wheel.append(f"║  Total Tracks: {total:<26} ║")
    wheel.append("╚══════════════════════════════════════════╝")
    
    return '\n'.join(wheel)


# ─────────────────────────────────────────────────────────────────────────────
# Mood Badge Generator (for UI)
# ─────────────────────────────────────────────────────────────────────────────

def create_mood_badge(mood_name: str, count: int = None) -> str:
    """
    Create a color-coded mood badge for UI display.
    
    Returns formatted string with mood emoji and color indicator.
    """
    emojis = {
        'Exuberant': '🌟',
        'Energetic': '⚡',
        'Frantic': '🔥',
        'Happy': '😊',
        'Contentment': '😌',
        'Calm': '🧘',
        'Sad': '😢',
        'Depression': '🌑',
    }
    
    emoji = emojis.get(mood_name, '🎵')
    
    if count is not None:
        return f"{emoji} {mood_name} ({count})"
    else:
        return f"{emoji} {mood_name}"


# ─────────────────────────────────────────────────────────────────────────────
# Main Visualization Function
# ─────────────────────────────────────────────────────────────────────────────

def show_mood_distribution(pctl, master_library, star_store, notify_fn=None, tauon=None) -> None:
    """
    Analyze library and show mood distribution.

    Displays:
    1. Text-based mood wheel
    2. Statistics for each mood
    3. Dominant mood identification
    
    Args:
        pctl: Playlist controller
        master_library: Master library dict
        star_store: Star/rating store
        notify_fn: Optional notification function for progress
        tauon: Optional Tauon instance for showing message boxes
    """
    import threading

    def _run():
        if notify_fn:
            notify_fn("Analyzing library moods…")

        # Analyze moods
        mood_buckets = analyze_library_moods(pctl, master_library, star_store)
        stats = get_mood_statistics(mood_buckets)

        # Generate text visualization
        wheel_text = generate_mood_wheel_text(stats)

        # Find dominant mood
        dominant_mood = max(stats.items(), key=lambda x: x[1]['count'])
        dominant_name = dominant_mood[0]
        dominant_count = dominant_mood[1]['count']
        dominant_pct = dominant_mood[1]['percentage']

        # Create summary
        summary = (
            f"{wheel_text}\n\n"
            f"🎯 Dominant Mood: {create_mood_badge(dominant_name, dominant_count)}\n"
            f"   ({dominant_pct:.1f}% of your library)\n\n"
            f"💡 Tip: Right-click playlist tab → Audio Recommendations →\n"
            f"   Mood Playlists to create playlists for each mood!"
        )

        if notify_fn:
            notify_fn(f"Mood analysis complete! Dominant: {dominant_name}")
        
        # Show full results in a message box if tauon instance provided
        if tauon:
            tauon.show_message(
                "📊 Mood Distribution Analysis",
                f"Dominant: {dominant_name} ({dominant_pct:.1f}%)\n\n"
                f"Full results logged to console.",
                mode="info"
            )
        
        # Always log full summary to console
        log.info(summary)
        
        # Also print to stdout for debugging
        print(summary)

    threading.Thread(target=_run, daemon=True).start()
