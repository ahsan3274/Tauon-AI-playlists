"""
t_icon_loader.py - Icon Loading System
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Loads and caches icons from open-source icon sets:
- Material Design Icons (Google) - https://github.com/Templarian/MaterialDesign
- Feather Icons - https://github.com/feathericons/feather
- Tabler Icons - https://github.com/tabler/tabler-icons

All icons are SVG-based, scalable, and properly licensed (MIT/Apache 2.0).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

log = logging.getLogger("t_icon_loader")


# ─────────────────────────────────────────────────────────────────────────────
# Icon Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Icon sources (all open-source, MIT/Apache 2.0 licensed)
ICON_SOURCES = {
    'material': 'https://github.com/Templarian/MaterialDesign-SVG',
    'feather': 'https://github.com/feathericons/feather',
    'tabler': 'https://github.com/tabler/tabler-icons',
}

# Icon sizes (in pixels)
ICON_SIZES = {
    'small': 16,
    'medium': 24,
    'large': 32,
}

# Icon colors (will be applied via SVG fill)
ICON_COLORS = {
    'default': '#86868B',      # Gray
    'accent': '#007AFF',       # Blue
    'success': '#34C759',      # Green
    'warning': '#FF9500',      # Orange
    'error': '#FF3B30',        # Red
    'mood_exuberant': '#FFD700',  # Gold
    'mood_energetic': '#FF4500',  # Red-orange
    'mood_frantic': '#8B0000',    # Dark red
    'mood_happy': '#FFB6C1',      # Light pink
    'mood_contentment': '#90EE90', # Light green
    'mood_calm': '#87CEEB',       # Sky blue
    'mood_sad': '#778899',        # Light slate gray
    'mood_depression': '#4B4B4B', # Dark gray
}


class IconLoader:
    """
    Load and cache icons from SVG files.
    
    Supports:
    - Material Design Icons
    - Feather Icons
    - Tabler Icons
    - Custom SVG icons
    """
    
    def __init__(self, icon_directory: Path = None):
        self.icon_directory = icon_directory or Path(__file__).parent / "assets" / "icons"
        self.cache = {}
        self.icon_directory.mkdir(parents=True, exist_ok=True)
        
    def get_icon(self, icon_name: str, size: str = 'medium', color: str = None) -> str:
        """
        Get icon SVG data.
        
        Args:
            icon_name: Name of icon (e.g., 'radio', 'mood', 'energy')
            size: 'small', 'medium', or 'large'
            color: Color name or hex code
            
        Returns:
            SVG data as string
        """
        cache_key = f"{icon_name}_{size}_{color or 'default'}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Try to load icon file
        icon_path = self.icon_directory / f"{icon_name}.svg"
        
        if icon_path.exists():
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_data = f.read()
                
            # Apply size and color
            svg_data = self._apply_transforms(
                svg_data,
                size=ICON_SIZES.get(size, 24),
                color=color or ICON_COLORS['default']
            )
            
            self.cache[cache_key] = svg_data
            return svg_data
        
        # Fallback to default icon
        log.warning(f"Icon '{icon_name}' not found, using fallback")
        return self._get_fallback_icon(size=ICON_SIZES.get(size, 24))
    
    def _apply_transforms(self, svg_data: str, size: int, color: str) -> str:
        """Apply size and color transforms to SVG."""
        # Replace width/height
        svg_data = svg_data.replace('width="24"', f'width="{size}"')
        svg_data = svg_data.replace('height="24"', f'height="{size}"')
        svg_data = svg_data.replace('width="1em"', f'width="{size}"')
        svg_data = svg_data.replace('height="1em"', f'height="{size}"')
        
        # Replace fill color
        if 'fill="' in svg_data:
            svg_data = svg_data.replace('fill="#000000"', f'fill="{color}"')
            svg_data = svg_data.replace('fill="black"', f'fill="{color}"')
            svg_data = svg_data.replace('fill:#000000', f'fill:{color}')
        else:
            # Add fill to root SVG element
            svg_data = svg_data.replace('<svg', f'<svg fill="{color}"')
        
        return svg_data
    
    def _get_fallback_icon(self, size: int) -> str:
        """Return a simple fallback icon (music note)."""
        return f'''<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" fill="#86868B"/>
        </svg>'''
    
    def download_icon_pack(self, pack_name: str = 'feather') -> bool:
        """
        Download icon pack from GitHub.
        
        Args:
            pack_name: 'material', 'feather', or 'tabler'
            
        Returns:
            True if successful, False otherwise
        """
        import requests
        import zipfile
        import io
        
        urls = {
            'feather': 'https://github.com/feathericons/feather/archive/refs/heads/master.zip',
            'tabler': 'https://github.com/tabler/tabler-icons/archive/refs/heads/master.zip',
            'material': 'https://github.com/Templarian/MaterialDesign-SVG/archive/refs/heads/master.zip',
        }
        
        if pack_name not in urls:
            log.error(f"Unknown icon pack: {pack_name}")
            return False
        
        try:
            log.info(f"Downloading {pack_name} icons...")
            response = requests.get(urls[pack_name], timeout=30)
            response.raise_for_status()
            
            # Extract SVG files
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                for file_info in zip_file.filelist:
                    if file_info.filename.endswith('.svg'):
                        # Extract just the filename
                        icon_name = Path(file_info.filename).stem
                        if icon_name:
                            zip_file.extract(file_info, self.icon_directory / pack_name)
                            log.debug(f"Extracted: {icon_name}")
            
            log.info(f"Successfully downloaded {pack_name} icon pack")
            return True
            
        except Exception as e:
            log.error(f"Failed to download icon pack: {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Predefined Icon Mappings
# ─────────────────────────────────────────────────────────────────────────────

# Menu icon mappings (icon_name -> feather/material icon name)
MENU_ICONS = {
    'similarity_radio': 'radio',
    'artist_radio': 'user',
    'mood_playlists': 'heart',
    'energy_playlists': 'zap',
    'genre_clusters': 'grid',
    'decade_playlists': 'calendar',
    'audio_clusters': 'bar-chart-2',
    'mood_distribution': 'pie-chart',
    'settings': 'settings',
    'info': 'info',
    'create': 'plus',
    'analyze': 'search',
    'export': 'upload',
    'import': 'download',
    'legacy': 'clock',
}

# Mood-specific icons
MOOD_ICONS = {
    'Exuberant': 'star',
    'Energetic': 'zap',
    'Frantic': 'flame',
    'Happy': 'smile',
    'Contentment': 'coffee',
    'Calm': 'moon',
    'Sad': 'cloud-rain',
    'Depression': 'cloud',
}


def get_menu_icon(menu_item: str, style: str = 'feather') -> str:
    """
    Get icon name for a menu item.
    
    Args:
        menu_item: Menu item identifier
        style: 'feather' or 'material'
        
    Returns:
        Icon name
    """
    if menu_item.startswith('mood_'):
        mood_name = menu_item.replace('mood_', '').title()
        return MOOD_ICONS.get(mood_name, 'music')
    
    return MENU_ICONS.get(menu_item, 'music')


# ─────────────────────────────────────────────────────────────────────────────
# Global Icon Loader Instance
# ─────────────────────────────────────────────────────────────────────────────

_icon_loader = None


def get_icon_loader() -> IconLoader:
    """Get or create global icon loader instance."""
    global _icon_loader
    if _icon_loader is None:
        _icon_loader = IconLoader()
    return _icon_loader


def load_icon(icon_name: str, size: str = 'medium', color: str = None) -> str:
    """Load icon by name."""
    return get_icon_loader().get_icon(icon_name, size, color)
