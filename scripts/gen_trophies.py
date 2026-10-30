#!/usr/bin/env python3
"""Generate self-hosted GitHub trophy SVGs for a profile.

Usage:
    python3 scripts/gen_trophies.py                # writes trophies.svg + top-languages.svg
    python3 scripts/gen_trophies.py --user mb-xrl  # explicit user

Needs an authenticated `gh` CLI (it reads stats straight from the GitHub API).
No third-party images, no rate-limited badge services.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- rank thresholds: (metric, [(rank, min_value), ...]) low -> high -------------
RANKS = ["C", "B", "A", "AA", "AAA", "S", "SS", "SSS"]
COLORS = {
    "C": "#6e7681", "B": "#4ac26b", "A": "#58a6ff", "AA": "#a371f7",
    "AAA": "#f778ba", "S": "#ffb020", "SS": "#ff7b1c", "SSS": "#ffd700",
}
THRESHOLDS = {
    "followers": [0, 10, 25, 50, 100, 250, 500, 1000],
    "repos":     [0, 3, 6, 10, 20, 40, 80, 150],
    "stars":     [0, 5, 15, 35, 75, 150, 400, 1000],
    "commits":   [0, 10, 50, 150, 400, 1000, 2500, 5000],
    "prs":       [0, 2, 5, 10, 25, 50, 100, 250],
    "issues":    [0, 2, 5, 10, 25, 50, 100, 250],
}
LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "Go": "#00ADD8", "Rust": "#dea584", "C": "#555555", "C++": "#f34b7d",
    "Java": "#b07219", "Shell": "#89e051", "HTML": "#e34c26",
    "CSS": "#563d7c", "Ruby": "#701516", "PHP": "#4F5D95", "Kotlin": "#A97BFF",
    "Swift": "#F05138", "Dart": "#00B4AB", "Lua": "#000080", "C#": "#178600",
}


def gh(path: str):
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"gh api {path} failed: {out.stderr.strip()}")
    return json.loads(out.stdout or "null")


def collect(user: str) -> dict:
    profile = gh(f"users/{user}")
    repos = gh(f"users/{user}/repos?per_page=100&type=owner") or []
    languages: dict[str, int] = {}
    for repo in repos:
        for name, size in (gh(f"repos/{user}/{repo['name']}/languages") or {}).items():
            languages[name] = languages.get(name, 0) + int(size)

    def search(q: str) -> int:
        return int((gh(f"search/{q}") or {}).get("total_count", 0))

    return {
        "followers": profile.get("followers", 0),
        "repos": profile.get("public_repos", len(repos)),
        "stars": sum(r.get("stargazers_count", 0) for r in repos if not r.get("fork")),
        "commits": search(f"commits?q=author:{user}"),
        "prs": search(f"issues?q=author:{user}+type:pr"),
        "issues": search(f"issues?q=author:{user}+type:issue"),
        "languages": dict(sorted(languages.items(), key=lambda kv: -kv[1])),
    }


def rank(metric: str, value: int) -> str:
    steps = THRESHOLDS[metric]
    tier = "C"
    for label, floor in zip(RANKS, steps):
        if value >= floor:
            tier = label
    return tier


def fmt(value: int) -> str:
    if value >= 1000:
        return f"{value / 1000:.1f}k".replace(".0k", "k")
    return str(value)


# --- SVG helpers ---------------------------------------------------------------
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
CARD_W, CARD_H, GAP, PAD = 200, 132, 14, 16


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def trophy_glyph(cx: float, cy: float, color: str, size: float = 1.15) -> str:
    return (
        f'<g transform="translate({cx},{cy}) scale({size})" fill="{color}" opacity="0.9">'
        f'<path d="M-8,-13 H8 V-6 A8,8 0 0 1 -8,-6 Z"/>'
        f'<path d="M-8,-11 A5,5 0 0 0 -8,-4" fill="none" stroke="{color}" stroke-width="1.6"/>'
        f'<path d="M8,-11 A5,5 0 0 1 8,-4" fill="none" stroke="{color}" stroke-width="1.6"/>'
        f'<rect x="-2" y="-1" width="4" height="7" rx="1"/>'
        f'<rect x="-7.5" y="5.5" width="15" height="3.5" rx="1.75"/>'
        f'</g>'
    )


def card(x: float, y: float, title: str, value: str, tier: str) -> str:
    color = COLORS[tier]
    return f"""  <g>
    <rect x="{x}" y="{y}" width="{CARD_W}" height="{CARD_H}" rx="12" fill="#0d1117" stroke="#30363d"/>
    <rect x="{x}" y="{y}" width="4" height="{CARD_H}" rx="2" fill="{color}" opacity="0.85"/>
    <rect x="{x + 18}" y="{y + 16}" width="46" height="26" rx="7" fill="{color}" opacity="0.15"/>
    <text x="{x + 41}" y="{y + 34}" font-family="{FONT}" font-size="14" font-weight="700"
          fill="{color}" text-anchor="middle">{tier}</text>
    {trophy_glyph(x + CARD_W - 40, y + 42, color)}
    <text x="{x + 18}" y="{y + 74}" font-family="{FONT}" font-size="11.5" letter-spacing="1.2"
          fill="#8b949e">{esc(title.upper())}</text>
    <text x="{x + 18}" y="{y + 108}" font-family="{FONT}" font-size="27" font-weight="700"
          fill="#e6edf3">{esc(value)}</text>
  </g>"""


def trophies_svg(stats: dict) -> str:
    cards = [
        ("Followers", fmt(stats["followers"]), rank("followers", stats["followers"])),
        ("Stars", fmt(stats["stars"]), rank("stars", stats["stars"])),
        ("Commits", fmt(stats["commits"]), rank("commits", stats["commits"])),
        ("Repositories", fmt(stats["repos"]), rank("repos", stats["repos"])),
        ("Pull requests", fmt(stats["prs"]), rank("prs", stats["prs"])),
        ("Issues", fmt(stats["issues"]), rank("issues", stats["issues"])),
    ]
    width = PAD * 2 + 3 * CARD_W + 2 * GAP
    height = PAD * 2 + 2 * CARD_H + GAP
    body = []
    for i, (title, value, tier) in enumerate(cards):
        cx = PAD + (i % 3) * (CARD_W + GAP)
        cy = PAD + (i // 3) * (CARD_H + GAP)
        body.append(card(cx, cy, title, value, tier))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" role="img" aria-label="GitHub trophies">
  <defs>
    <style>
      @media (prefers-color-scheme: light) {{
        rect[fill="#0d1117"] {{ fill: #ffffff; }}
        rect[stroke="#30363d"] {{ stroke: #d0d7de; }}
        text[fill="#e6edf3"] {{ fill: #1f2328; }}
        text[fill="#8b949e"] {{ fill: #59636e; }}
      }}
    </style>
  </defs>
  <rect width="{width}" height="{height}" fill="none"/>
{chr(10).join(body)}
</svg>
"""


def languages_svg(stats: dict) -> str:
    langs = stats["languages"]
    total = sum(langs.values()) or 1
    width, height = 3 * CARD_W + 2 * GAP + PAD * 2, 168
    rows, seg_x = [], PAD + 18
    bar_w, bar_y = width - (PAD + 18) * 2, 52
    x = seg_x
    for name, size in langs.items():
        w = bar_w * size / total
        color = LANG_COLORS.get(name, "#8b949e")
        rows.append(f'  <rect x="{x:.2f}" y="{bar_y}" width="{w:.2f}" height="10" fill="{color}"/>')
        x += w
    legend = []
    for i, (name, size) in enumerate(langs.items()):
        color = LANG_COLORS.get(name, "#8b949e")
        lx = seg_x + (i % 3) * 200
        ly = 96 + (i // 3) * 26
        legend.append(
            f'  <circle cx="{lx + 5}" cy="{ly}" r="5" fill="{color}"/>'
            f'<text x="{lx + 18}" y="{ly + 4}" font-family="{FONT}" font-size="12.5" '
            f'fill="#e6edf3">{esc(name)}</text>'
            f'<text x="{lx + 160}" y="{ly + 4}" font-family="{FONT}" font-size="12.5" '
            f'fill="#8b949e">{size / total * 100:.0f}%</text>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" role="img" aria-label="Most used languages">
  <defs>
    <clipPath id="bar"><rect x="{seg_x}" y="{bar_y}" width="{bar_w}" height="10" rx="5"/></clipPath>
    <style>
      @media (prefers-color-scheme: light) {{
        rect[fill="#0d1117"] {{ fill: #ffffff; }}
        rect[stroke="#30363d"] {{ stroke: #d0d7de; }}
        text[fill="#e6edf3"] {{ fill: #1f2328; }}
        text[fill="#8b949e"] {{ fill: #59636e; }}
      }}
    </style>
  </defs>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" fill="#0d1117" stroke="#30363d"/>
  <text x="{seg_x}" y="32" font-family="{FONT}" font-size="11.5" letter-spacing="1.2" fill="#8b949e">MOST USED LANGUAGES</text>
  {trophy_glyph(width - seg_x - 8, 28, "#ffd700", 0.9)}
  <g clip-path="url(#bar)">
{chr(10).join(rows)}
  </g>
{chr(10).join(legend)}
</svg>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="mb-xrl")
    parser.add_argument("--out-dir", default=str(ROOT))
    args = parser.parse_args()
    if len(THRESHOLDS["followers"]) != len(RANKS):
        sys.exit("threshold table out of sync with RANKS")

    stats = collect(args.user)
    out = Path(args.out_dir)
    (out / "trophies.svg").write_text(trophies_svg(stats))
    (out / "top-languages.svg").write_text(languages_svg(stats))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
