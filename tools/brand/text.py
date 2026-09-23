"""Text → SVG path conversion: Inter outlines + HarfBuzz shaping (kerning, ligatures)."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from functools import lru_cache

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from .tokens import FONT_DIR


class MissingGlyph(ValueError):
    """Text contains a character the bundled Inter latin subset cannot draw."""


@dataclass(frozen=True)
class Shaped:
    d: str
    width: float


def _num(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


class Font:
    def __init__(self, weight: int) -> None:
        woff = TTFont(FONT_DIR / f"inter-latin-{weight}-normal.woff")
        woff.flavor = None
        buf = io.BytesIO()
        woff.save(buf)
        data = buf.getvalue()
        self.tt = TTFont(io.BytesIO(data))
        self.upm = self.tt["head"].unitsPerEm
        self.glyph_set = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.cmap = self.tt.getBestCmap()
        self.hb_font = hb.Font(hb.Face(hb.Blob(data)))
        self.weight = weight
        self._outlines: dict[int, str] = {}

    def layout(self, text: str, size: float,
               tracking: float = 0.0) -> tuple[list[tuple[int, float, float]], float]:
        """Shape text; return [(glyph id, x, y) in font units] and the advance width in px."""
        for ch in text:
            if ord(ch) not in self.cmap:
                raise MissingGlyph(f"{ch!r} (U+{ord(ch):04X}) not in Inter latin: {text!r}")
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb_font, buf, {"kern": True, "liga": True})
        extra = tracking * self.upm
        cursor = 0.0
        glyphs = []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            glyphs.append((info.codepoint, cursor + pos.x_offset, float(pos.y_offset)))
            cursor += pos.x_advance + extra
        if text:
            cursor -= extra
        return glyphs, cursor * size / self.upm

    def shape(self, text: str, size: float, x: float = 0.0, y: float = 0.0,
              tracking: float = 0.0) -> Shaped:
        """Whole run as one absolute path (used where <use> reuse is not wanted)."""
        glyphs, width = self.layout(text, size, tracking)
        scale = size / self.upm
        pen = SVGPathPen(self.glyph_set, ntos=_num)
        for gid, gx, gy in glyphs:
            self.glyph_set[self.order[gid]].draw(
                TransformPen(pen, (scale, 0, 0, -scale, x + gx * scale, y - gy * scale)))
        return Shaped(pen.getCommands(), width)

    def measure(self, text: str, size: float, tracking: float = 0.0) -> float:
        return self.layout(text, size, tracking)[1]

    def glyph_id(self, gid: int) -> str:
        return f"g{self.weight}_{gid}"

    def glyph_d(self, gid: int) -> str:
        """Outline in font units, y pointing down, integer coordinates; cached."""
        if gid not in self._outlines:
            pen = SVGPathPen(self.glyph_set, ntos=lambda v: str(round(v)))
            self.glyph_set[self.order[gid]].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
            self._outlines[gid] = pen.getCommands()
        return self._outlines[gid]


@lru_cache(maxsize=None)
def font(weight: int) -> Font:
    return Font(weight)


def text_path(text: str, size: float, x: float, y: float, weight: int = 400,
              fill: str = "currentColor", anchor: str = "start", tracking: float = 0.0,
              attrs: str = "") -> tuple[str, float]:
    """Text as <use> references to shared glyph outlines; document() embeds the outlines once."""
    f = font(weight)
    glyphs, width = f.layout(text, size, tracking)
    if anchor == "middle":
        x -= width / 2
    elif anchor == "end":
        x -= width
    elif anchor != "start":
        raise ValueError(f"unknown anchor {anchor!r}")
    uses = []
    for gid, gx, gy in glyphs:
        if not f.glyph_d(gid):
            continue  # spaces have no outline
        dy = f' y="{-round(gy)}"' if gy else ""
        uses.append(f'<use href="#{f.glyph_id(gid)}" x="{round(gx)}"{dy}/>')
    extra = f" {attrs}" if attrs else ""
    return (f'<g transform="translate({_num(x)} {_num(y)}) scale({size / f.upm:.6g})" '
            f'fill="{fill}"{extra}>' + "".join(uses) + "</g>"), width


_GLYPH_ID = re.compile(r"^g(\d+)_(\d+)$")


def glyph_defs(ids: list[str]) -> str:
    out = []
    for gid_ref in ids:
        m = _GLYPH_ID.match(gid_ref)
        if not m:
            raise ValueError(f"not a glyph id: {gid_ref!r}")
        out.append(f'<path id="{gid_ref}" d="{font(int(m[1])).glyph_d(int(m[2]))}"/>')
    return "".join(out)


def wrap(text: str, size: float, weight: int, max_width: float) -> list[str]:
    f = font(weight)
    lines: list[str] = []
    line = ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if f.measure(trial, size) <= max_width:
            line = trial
            continue
        if not line or f.measure(word, size) > max_width:
            raise ValueError(f"word {word!r} wider than {max_width}px at {size}px")
        lines.append(line)
        line = word
    if line:
        lines.append(line)
    return lines
