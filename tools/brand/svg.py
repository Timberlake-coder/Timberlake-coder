"""SVG building blocks and a linter for GitHub-safe, self-contained graphics."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html import escape

from .text import font, glyph_defs, text_path
from .tokens import SVG_MAX_BYTES

REDUCED_MOTION = ("@media (prefers-reduced-motion: reduce)"
                  "{*{animation:none!important;transition:none!important}}")
_GLYPH_REF = re.compile(r'href="#(g\d+_\d+)"')
_EXTERNAL = re.compile(r'(?:href|src)\s*=\s*"(?:https?:)?//|url\(\s*[\'"]?(?:https?:)?//|@import', re.I)


def esc(s: str) -> str:
    return escape(s, quote=True)


def document(width: int, height: int, body: str, title: str, desc: str = "",
             style: str = "", defs: str = "") -> str:
    css = style + REDUCED_MOTION if style else ""
    defs += glyph_defs(sorted(set(_GLYPH_REF.findall(body))))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{esc(title)}</title><desc id="desc">{esc(desc or title)}</desc>'
        + (f"<style>{css}</style>" if css else "")
        + (f"<defs>{defs}</defs>" if defs else "")
        + body + "</svg>"
    )


def panel(width: float, height: float, t: dict, radius: float = 16) -> str:
    """Opaque themed background so the graphic reads on any page colour."""
    return (f'<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="{radius}" '
            f'fill="{t["surface"]}" stroke="{t["border"]}"/>')


def brackets(x: float, y: float, w: float, h: float, arm: float, color: str,
             stroke: float = 2.5, cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    d = (f"M{x},{y + arm}V{y}H{x + arm} M{x + w - arm},{y}H{x + w}V{y + arm} "
         f"M{x + w},{y + h - arm}V{y + h}H{x + w - arm} M{x + arm},{y + h}H{x}V{y + h - arm}")
    return (f'<path{c} d="{d}" fill="none" stroke="{color}" stroke-width="{stroke}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def dot_grid(pid: str, color: str, gap: float = 22, r: float = 1.1) -> str:
    return (f'<pattern id="{pid}" width="{gap}" height="{gap}" patternUnits="userSpaceOnUse">'
            f'<circle cx="{gap / 2}" cy="{gap / 2}" r="{r}" fill="{color}"/></pattern>')


def chip(x: float, y: float, label: str, t: dict, size: float = 13, weight: int = 500,
         pad_x: float = 10, height: float = 26, fill: str | None = None,
         stroke: str | None = None, color: str | None = None) -> tuple[str, float]:
    w = font(weight).measure(label, size) + 2 * pad_x
    baseline = y + height / 2 + size * 0.36
    rect = (f'<rect x="{x:.2f}" y="{y}" width="{w:.2f}" height="{height}" rx="{height / 2}" '
            f'fill="{fill or t["bg"]}" stroke="{stroke or t["border"]}"/>')
    path, _ = text_path(label, size, x + pad_x, baseline, weight, fill=color or t["text"])
    return rect + path, w


def chip_row(x: float, y: float, labels: list[str], t: dict, max_width: float,
             gap: float = 8, row_gap: float = 8, **chip_kw) -> tuple[str, float]:
    """Chips left-to-right, wrapping at max_width. Returns (svg, height used)."""
    size, weight = chip_kw.get("size", 13), chip_kw.get("weight", 500)
    pad_x, height = chip_kw.get("pad_x", 10), chip_kw.get("height", 26)
    parts, cx, cy = [], x, y
    for label in labels:
        w = font(weight).measure(label, size) + 2 * pad_x
        if cx > x and cx + w > x + max_width:
            cx, cy = x, cy + height + row_gap
        svg, w = chip(cx, cy, label, t, **chip_kw)
        parts.append(svg)
        cx += w + gap
    return "".join(parts), (cy - y) + height


def picture(dark: str, light: str, alt: str, width: str | None = None,
            href: str | None = None) -> str:
    w = f' width="{width}"' if width else ""
    pic = (f'<picture><source media="(prefers-color-scheme: dark)" srcset="{dark}">'
           f'<img alt="{esc(alt)}" src="{light}"{w}></picture>')
    return f'<a href="{href}">{pic}</a>' if href else pic


def lint(svg: str) -> list[str]:
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as e:
        return [f"not well-formed XML: {e}"]
    problems = []
    size = len(svg.encode())
    if size > SVG_MAX_BYTES:
        problems.append(f"{size} bytes > {SVG_MAX_BYTES}")
    lowered = svg.lower()
    for bad in ("<script", "<foreignobject", "javascript:"):
        if bad in lowered:
            problems.append(f"contains {bad}")
    if _EXTERNAL.search(svg):
        problems.append("references an external resource")
    if root.find("{http://www.w3.org/2000/svg}title") is None:
        problems.append("missing <title>")
    return problems
