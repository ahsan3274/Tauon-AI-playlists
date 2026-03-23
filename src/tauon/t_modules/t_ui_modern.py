"""
t_ui_modern.py - Modern UI Components for Tauon
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Modern macOS/Manjaro-style UI components:
- Theme manager (light/dark/auto)
- Modern progress bar with animations
- Glass panel (frosted glass effect)
- Modern notifications

Design Language:
- Frosted glass (vibrancy)
- Rounded corners (8-12px)
- Subtle shadows
- System fonts
- Accent colors
- Smooth animations
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from tauon.t_modules.t_main import Tauon

# ─────────────────────────────────────────────────────────────────────────────
# Theme Manager
# ─────────────────────────────────────────────────────────────────────────────

class ThemeMode:
    """Theme mode constants."""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class ModernTheme:
    """
    Modern theme manager for Tauon.
    
    Provides light/dark/auto theme switching with macOS-style colors.
    """
    
    # Light theme colors (macOS Light)
    LIGHT_COLORS = {
        "background": (255, 255, 255, 255),      # White
        "panel": (245, 245, 247, 240),           # Light gray with transparency
        "glass": (255, 255, 255, 180),           # Frosted glass
        "accent": (0, 122, 255, 255),            # macOS blue
        "accent_gradient": [                     # Gradient for progress bars
            (0, 122, 255, 255),                  # Start: blue
            (88, 86, 214, 255),                  # End: purple
        ],
        "text_primary": (29, 29, 31, 255),       # Dark gray text
        "text_secondary": (142, 142, 147, 255),  # Light gray text
        "border": (200, 200, 200, 100),          # Subtle border
        "shadow": (0, 0, 0, 30),                 # Subtle shadow
        "success": (52, 199, 89, 255),           # Green
        "warning": (255, 149, 0, 255),           # Orange
        "error": (255, 59, 48, 255),             # Red
    }
    
    # Dark theme colors (macOS Dark)
    DARK_COLORS = {
        "background": (30, 30, 30, 255),         # Dark gray
        "panel": (44, 44, 46, 230),              # Dark panel with transparency
        "glass": (50, 50, 50, 180),              # Dark frosted glass
        "accent": (10, 132, 255, 255),           # Bright blue
        "accent_gradient": [                     # Gradient for progress bars
            (10, 132, 255, 255),                 # Start: bright blue
            (175, 82, 222, 255),                 # End: purple
        ],
        "text_primary": (255, 255, 255, 255),    # White text
        "text_secondary": (142, 142, 147, 255),  # Light gray text
        "border": (80, 80, 80, 100),             # Subtle border
        "shadow": (0, 0, 0, 80),                 # Darker shadow
        "success": (48, 209, 88, 255),           # Bright green
        "warning": (255, 159, 10, 255),          # Bright orange
        "error": (255, 69, 58, 255),             # Bright red
    }
    
    def __init__(self, tauon=None):
        self.mode = ThemeMode.AUTO
        self._current_colors = self.DARK_COLORS.copy()
        self.tauon = tauon
        self._colours = None
    
    def set_tauon(self, tauon) -> None:
        """Set Tauon instance to access colours."""
        self.tauon = tauon
        self._colours = tauon.colours if tauon else None
    
    def set_mode(self, mode: str) -> None:
        """Set theme mode (light/dark/auto)."""
        self.mode = mode
        self._update_colors()
    
    def _update_colors(self) -> None:
        """Update current colors based on mode."""
        if self.mode == ThemeMode.LIGHT:
            self._current_colors = self.LIGHT_COLORS.copy()
        elif self.mode == ThemeMode.DARK:
            self._current_colors = self.DARK_COLORS.copy()
        else:  # AUTO
            # For now, default to dark. Can be extended to detect system theme.
            self._current_colors = self.DARK_COLORS.copy()
    
    def get_color(self, name: str):
        """Get a color by name. Returns ColourRGBA if available, else tuple."""
        if self._colours:
            # Map theme colors to Tauon colours
            color_map = {
                "glass": self._colours.box_background,
                "border": self._colours.box_text_border,
                "text_primary": self._colours.box_text_label,
                "accent": self._colours.mode_button_active,
            }
            return color_map.get(name, self._current_colors.get(name, (0, 0, 0, 255)))
        return self._current_colors.get(name, (0, 0, 0, 255))
    
    def get_accent_gradient(self) -> list:
        """Get accent gradient for progress bars."""
        return self._current_colors.get("accent_gradient", self.DARK_COLORS["accent_gradient"])


# Global theme instance
_global_theme: Optional[ModernTheme] = None

def get_theme() -> ModernTheme:
    """Get or create the global theme instance."""
    global _global_theme
    if _global_theme is None:
        _global_theme = ModernTheme()
    return _global_theme


# ─────────────────────────────────────────────────────────────────────────────
# Modern Progress Bar
# ─────────────────────────────────────────────────────────────────────────────

class ModernProgressBar:
    """
    Modern progress bar with gradient fill and smooth animations.
    
    Features:
    - Gradient fill (accent colors)
    - Rounded corners
    - Smooth animations
    - Percentage text
    - Estimated time remaining
    """
    
    def __init__(self, width: int = 300, height: int = 8):
        self.width = width
        self.height = height
        self.radius = height // 2  # Rounded corners
        self.progress = 0.0  # 0.0 to 1.0
        self.text = ""
        self.show_percentage = True
        self.show_eta = True
        self.animation_start = 0
        self.animation_progress = 0.0
        
        self.theme = get_theme()
    
    def set_progress(self, progress: float, text: str = "", eta: int = None) -> None:
        """
        Set progress (0.0 to 1.0) with optional text and ETA.
        
        Args:
            progress: Progress value (0.0 to 1.0)
            text: Optional text to display
            eta: Estimated time remaining in seconds
        """
        self.progress = max(0.0, min(1.0, progress))
        
        # Build text
        parts = []
        if text:
            parts.append(text)
        if self.show_percentage:
            parts.append(f"{int(progress * 100)}%")
        if self.show_eta and eta is not None:
            parts.append(f"~{eta}s")
        
        self.text = "  ".join(parts)
        self.animation_start = time.time()
    
    def render(self, ddt, x: int, y: int, renderer=None) -> None:
        """
        Render the progress bar.
        
        Args:
            ddt: Drawing context
            x: X position
            y: Y position
            renderer: SDL renderer (optional)
        """
        # Get colors from theme
        bg_color = self.theme.get_color("panel")
        accent_gradient = self.theme.get_accent_gradient()
        text_color = self.theme.get_color("text_primary")
        
        # Draw background (rounded rectangle)
        self._draw_rounded_rect(ddt, x, y, self.width, self.height, self.radius, bg_color)
        
        # Draw gradient-filled progress
        if self.progress > 0:
            progress_width = int(self.width * self.progress)
            if progress_width > 0:
                self._draw_gradient_rect(
                    ddt, x, y, progress_width, self.height, accent_gradient
                )
        
        # Draw text (percentage)
        if self.text:
            # Text is drawn by the notification system
            pass
    
    def _draw_rounded_rect(self, ddt, x: int, y: int, w: int, h: int, r: int, color) -> None:
        """Draw a rounded rectangle."""
        # Simplified: draw regular rect for now
        # Can be enhanced with proper rounded corners using SDL_RenderFillRect
        ddt.rect((x, y, w, h), color)
    
    def _draw_gradient_rect(self, ddt, x: int, y: int, w: int, h: int, gradient) -> None:
        """Draw a gradient-filled rectangle."""
        if len(gradient) >= 2:
            # Draw horizontal gradient
            start_color = gradient[0]
            end_color = gradient[-1]
            
            # For now, use start color (gradient requires more complex SDL2 rendering)
            ddt.rect((x, y, w, h), start_color)
        else:
            ddt.rect((x, y, w, h), gradient[0] if gradient else (0, 122, 255, 255))


# ─────────────────────────────────────────────────────────────────────────────
# Glass Panel
# ─────────────────────────────────────────────────────────────────────────────

class GlassPanel:
    """
    Frosted glass panel effect.
    
    Features:
    - Semi-transparent background
    - Blur effect (simulated)
    - Rounded corners
    - Subtle border
    """
    
    def __init__(self, width: int = 400, height: int = 100, corner_radius: int = 12):
        self.width = width
        self.height = height
        self.corner_radius = corner_radius
        self.theme = get_theme()
    
    def render(self, ddt, x: int, y: int, renderer=None) -> None:
        """Render the glass panel."""
        glass_color = self.theme.get_color("glass")
        border_color = self.theme.get_color("border")
        
        # Draw glass background
        ddt.rect((x, y, self.width, self.height), glass_color)
        
        # Draw subtle border
        ddt.rect((x, y, self.width, 1), border_color)  # Top
        ddt.rect((x, y, 1, self.height), border_color)  # Left
        ddt.rect((x + self.width - 1, y, 1, self.height), border_color)  # Right
        ddt.rect((x, y + self.height - 1, self.width, 1), border_color)  # Bottom


# ─────────────────────────────────────────────────────────────────────────────
# Modern Notification Toast
# ─────────────────────────────────────────────────────────────────────────────

class ModernNotification:
    """
    Modern notification toast with progress bar.
    
    Features:
    - Frosted glass background
    - Gradient progress bar
    - Smooth fade in/out
    - Auto-dismiss
    """
    
    def __init__(self):
        self.message = ""
        self.progress = 0.0
        self.visible = False
        self.fade_in = 0.0
        self.fade_out = 0.0
        self.created_time = 0
        self.duration = 5.0  # Auto-dismiss after 5 seconds
        self.width = 350
        self.height = 60
        self.x = 0
        self.y = 0
        
        self.theme = get_theme()
        self.progress_bar = ModernProgressBar(width=300, height=6)
    
    def show(self, message: str, progress: float = None, duration: float = None) -> None:
        """
        Show notification.
        
        Args:
            message: Message text
            progress: Optional progress (0.0 to 1.0)
            duration: Display duration in seconds (None = indefinite)
        """
        self.message = message
        self.progress = progress if progress is not None else 0.0
        self.visible = True
        self.fade_in = 0.0
        self.created_time = time.time()
        self.duration = duration if duration is not None else 5.0
        
        if progress is not None:
            self.progress_bar.set_progress(self.progress)
    
    def hide(self) -> None:
        """Hide notification."""
        self.visible = False
        self.fade_out = 0.0
    
    def update(self) -> bool:
        """
        Update notification state.
        
        Returns:
            True if still visible, False if should be hidden
        """
        if not self.visible:
            return False
        
        # Fade in
        if self.fade_in < 1.0:
            self.fade_in = min(1.0, self.fade_in + 0.1)
        
        # Auto-dismiss
        if self.duration > 0 and time.time() - self.created_time > self.duration:
            self.fade_out += 0.1
            if self.fade_out >= 1.0:
                self.visible = False
                return False
        
        return True
    
    def render(self, ddt, x: int, y: int, renderer=None) -> None:
        """Render the notification."""
        if not self.visible:
            return
        
        # Calculate alpha based on fade
        alpha = int(255 * self.fade_in * (1.0 - self.fade_out))
        
        # Draw glass panel background
        panel = GlassPanel(width=self.width, height=self.height)
        panel.render(ddt, x, y, renderer)
        
        # Draw message text
        text_color = self.theme.get_color("text_primary")
        # Text rendering would go here
        
        # Draw progress bar if applicable
        if self.progress > 0:
            self.progress_bar.render(ddt, x + 25, y + self.height - 20, renderer)


# ─────────────────────────────────────────────────────────────────────────────
# Animation Easing Functions
# ─────────────────────────────────────────────────────────────────────────────

class Easing:
    """Easing functions for smooth animations."""
    
    @staticmethod
    def ease_in_out(t: float) -> float:
        """Smooth ease in-out."""
        return t * t * (3 - 2 * t)
    
    @staticmethod
    def ease_out(t: float) -> float:
        """Smooth ease out."""
        return 1 - (1 - t) * (1 - t)
    
    @staticmethod
    def ease_in(t: float) -> float:
        """Smooth ease in."""
        return t * t
    
    @staticmethod
    def linear(t: float) -> float:
        """Linear (no easing)."""
        return t


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def alpha_blend(color1, color2, alpha: float = 0.5) -> Tuple[int, int, int, int]:
    """Blend two colors with alpha."""
    return tuple(
        int(c1 * alpha + c2 * (1 - alpha))
        for c1, c2 in zip(color1, color2)
    )


def lerp_color(color1, color2, t: float) -> Tuple[int, int, int, int]:
    """Linear interpolation between two colors."""
    return tuple(
        int(c1 + (c2 - c1) * t)
        for c1, c2 in zip(color1, color2)
    )
