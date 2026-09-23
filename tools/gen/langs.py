"""Languages card aggregated across all owned repos, private included; no repo names shown.

Vendored into the public profile repo (tools/) and refreshed by a daily workflow when the
STATS_TOKEN secret exists. Imports only brand.* so it runs standalone there.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

from brand.svg import document, panel
from brand.text import text_path
from brand.tokens import THEMES

COLORS = {"TypeScript": "#3178C6", "Python": "#3572A5", "Jupyter Notebook": "#DA5B0B",
          "Go": "#00ADD8", "JavaScript": "#F1E05A", "CSS": "#663399", "HTML": "#E34C26",
          "Shell": "#89E051", "Dockerfile": "#384D54", "Swift": "#F05138", "Kotlin": "#A97BFF",
          "Dart": "#00B4AB", "PLpgSQL": "#336790"}
OTHER = "#8B98B5"
CW, CH = 580, 300
START = "https://api.github.com/user/repos?affiliation=owner&per_page=100"


def _get(url: str, token: str) -> tuple[object, str | None]:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "profile-langs"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        nxt = re.search(r'<([^>]+)>;\s*rel="next"', resp.headers.get("Link", ""))
        return json.load(resp), (nxt.group(1) if nxt else None)


def fetch_languages(token: str, exclude: set[str], get=_get) -> dict[str, int]:
    totals: Counter[str] = Counter()
    url: str | None = START
    while url:
        repos, url = get(url, token)
        for repo in repos:
            if repo["fork"] or repo["name"] in exclude:
                continue
            langs, _ = get(repo["languages_url"], token)
            totals.update(langs)
    return dict(totals)


def summarize(langs: dict[str, int], top: int = 6) -> list[tuple[str, float, str]]:
    total = sum(langs.values())
    if not total:
        return []
    ranked = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)
    rows = [(n, b / total * 100, COLORS.get(n, OTHER)) for n, b in ranked[:top]]
    rest = sum(b for _, b in ranked[top:])
    if rest:
        rows.append(("Other", rest / total * 100, OTHER))
    return rows


def render_langs(theme: str, langs: dict[str, int]) -> str:
    t = THEMES[theme]
    rows = summarize(langs)
    bx, by, bw = 32, 96, CW - 64
    parts = [panel(CW, CH, t, 16),
             text_path("Languages", 20, 32, 50, 700, fill=t["text"])[0],
             text_path("across all my repositories · by code size", 13, 32, 72, 400, fill=t["muted"])[0]]
    x, segs = float(bx), []
    for _, pct, color in rows:
        w = bw * pct / 100
        segs.append(f'<rect x="{x:.2f}" y="{by}" width="{w + 0.5:.2f}" height="12" fill="{color}"/>')
        x += w
    parts.append(f'<g clip-path="url(#bar)">{"".join(segs)}</g>')
    for i, (name, pct, color) in enumerate(rows):
        col, row = divmod(i, 4)
        lx, ly = 32 + col * 262, 146 + row * 34
        parts += [f'<circle cx="{lx + 6}" cy="{ly - 5}" r="6" fill="{color}"/>',
                  text_path(name, 15, lx + 20, ly, 600, fill=t["text"])[0],
                  text_path(f"{pct:.1f}%", 14, lx + 240, ly, 500, fill=t["muted"], anchor="end")[0]]
    if not rows:
        parts.append(text_path("No data yet", 15, 32, 146, 500, fill=t["muted"])[0])
    clip = f'<clipPath id="bar"><rect x="{bx}" y="{by}" width="{bw}" height="12" rx="6"/></clipPath>'
    desc = ", ".join(f"{n} {p:.1f}%" for n, p, _ in rows) or "No data yet"
    return document(CW, CH, "".join(parts), "Languages", desc, defs=clip)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render the languages card")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--exclude", default="")
    ap.add_argument("--token-env", default="STATS_TOKEN")
    a = ap.parse_args(argv)
    token = os.environ.get(a.token_env, "")
    if not token:
        print(f"{a.token_env} not set; keeping existing cards", file=sys.stderr)
        return 0
    langs = fetch_languages(token, {s for s in a.exclude.split(",") if s})
    a.out.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (a.out / f"langs-{theme}.svg").write_text(render_langs(theme, langs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
