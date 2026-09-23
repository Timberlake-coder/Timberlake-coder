"""Design tokens shared by every generated graphic (spec §3)."""
from pathlib import Path

THEMES: dict[str, dict[str, str]] = {
    "dark": {"bg": "#0B1020", "surface": "#111831", "border": "#1F2A44", "text": "#E6EDF7",
             "muted": "#8B98B5", "primary": "#3B82F6", "accent": "#22D3EE", "ok": "#34D399"},
    "light": {"bg": "#FFFFFF", "surface": "#F6F8FC", "border": "#DCE3EE", "text": "#0B1020",
              "muted": "#55627A", "primary": "#1D4ED8", "accent": "#0891B2", "ok": "#059669"},
}
FONT_DIR = Path(__file__).parent / "fonts"
SVG_MAX_BYTES = 120_000
