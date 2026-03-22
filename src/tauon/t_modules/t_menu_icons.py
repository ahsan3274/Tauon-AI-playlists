"""
t_menu_icons.py - Menu Icon Definitions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Centralized icon definitions for menu items.
Uses SVG-based icons from the assets/svg directory for proper UI integration.

Icon sources:
- Existing Tauon SVG icons in assets/svg/
- Feather Icons (MIT) - https://feathericons.com/
- Material Design Icons (Apache 2.0) - https://github.com/Templarian/MaterialDesign
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Menu Icon Mappings (icon name -> SVG filename in assets/svg/)
# ─────────────────────────────────────────────────────────────────────────────

# Playlist generation icons
MENU_ICON_MAP = {
    'similarity_radio': 'radio',         # Radio tower icon
    'artist_radio': 'artist',             # Artist silhouette
    'mood_playlists': 'heart-menu',       # Heart icon
    'energy_playlists': 'power',          # Lightning/power icon
    'genre_clusters': 'shard',            # Grid/cluster icon
    'decade_playlists': 'calendar',       # Calendar icon (need to create)
    'audio_clusters': 'col',              # Bar chart icon
    'mood_distribution': 'pie-chart',     # Pie chart icon (need to create)
    'top_played': 'star',                 # Star icon
    'top_rated': 'star-half',             # Half star icon
    'file_modified': 'info',              # Info icon
    'longest': 'sort-down',               # Sort/length icon
    'shuffle': 'tauon_shuffle',           # Shuffle icon
    'lucky': 'star',                      # Star icon
    'reverse': 'return',                  # Return/reverse icon
    'duplicate': 'playlist',              # Playlist copy icon
    'loved': 'heart-track',               # Heart icon
    'comment': 'lyrics',                  # Text/comment icon
    'lyrics': 'lyrics',                   # Lyrics icon
    'legacy': 'lock',                     # Clock/legacy icon
    'create': 'new',                      # Plus/new icon
    'info': 'info',                       # Info icon
    'settings': 'settings2',              # Settings icon
    'analyze': 'filter',                  # Search/filter icon
}


def get_icon_filename(icon_name: str) -> str:
    """Get SVG filename for an icon name."""
    return MENU_ICON_MAP.get(icon_name, 'info')


# ─────────────────────────────────────────────────────────────────────────────
# Icon Color Suggestions (RGB) for dynamic coloring
# ─────────────────────────────────────────────────────────────────────────────

ICON_COLORS = {
    'default': (134, 134, 139),      # Gray #86868B
    'accent': (0, 122, 255),          # Blue #007AFF
    'success': (52, 199, 89),         # Green #34C759
    'warning': (255, 149, 0),         # Orange #FF9500
    'error': (255, 59, 48),           # Red #FF3B30
    'mood_exuberant': (255, 215, 0),  # Gold
    'mood_energetic': (255, 69, 0),   # Red-orange
    'mood_frantic': (139, 0, 0),      # Dark red
    'mood_happy': (255, 182, 193),    # Light pink
    'mood_contentment': (144, 238, 144), # Light green
    'mood_calm': (135, 206, 235),     # Sky blue
    'mood_sad': (119, 136, 153),      # Light slate gray
    'mood_depression': (75, 75, 75),  # Dark gray
}


# ─────────────────────────────────────────────────────────────────────────────
# Mood-specific Icon Mappings
# ─────────────────────────────────────────────────────────────────────────────

MOOD_ICON_MAP = {
    'Exuberant': 'star',
    'Energetic': 'power',
    'Frantic': 'ex',              # Exclamation/intense
    'Happy': 'heart-track',
    'Contentment': 'coffee',      # Need to create
    'Calm': 'moon',               # Need to create
    'Sad': 'cloud',               # Need to create
    'Depression': 'warning',
}


def get_mood_icon_filename(mood_name: str) -> str:
    """Get icon filename for a specific mood."""
    return MOOD_ICON_MAP.get(mood_name, 'music')
