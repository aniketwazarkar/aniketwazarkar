#!/usr/bin/env python3
"""Draws a self-rated skill radar and a live language-mix radar, side by side, into one SVG.

Usage:
  python scripts/radar.py --skills assets/skills.json --github USERNAME -o assets/radar \
      --limit 7 --curve 0.4 --values --exclude "html,css,shell,dockerfile,makefile,jupyter notebook"
"""
import argparse
import json
import math
import os
import sys
import urllib.request

PANEL_W = 460
PANEL_H = 440
RADIUS = 150
RINGS = (25, 50, 75, 100)
ACCENT = "#0969DA"


def fetch_json(url, token=None):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def language_axes(username, token, limit, curve, exclude):
    exclude = {e.strip().lower() for e in (exclude or "").split(",") if e.strip()}
    totals = {}
    page = 1
    while True:
        repos = fetch_json(
            f"https://api.github.com/users/{username}/repos?per_page=100&page={page}&type=owner",
            token,
        )
        if not repos:
            break
        for repo in repos:
            if repo.get("fork"):
                continue
            langs = fetch_json(repo["languages_url"], token)
            for lang, count in langs.items():
                if lang.lower() in exclude:
                    continue
                totals[lang] = totals.get(lang, 0) + count
        page += 1
        if len(repos) < 100:
            break

    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    if not ranked:
        return []
    max_bytes = ranked[0][1]
    axes = []
    for lang, count in ranked:
        pct = 100.0 * (count / max_bytes) ** curve
        axes.append({"label": lang, "value": round(pct, 1), "raw": count})
    return axes


def polygon_points(axes, cx, cy):
    n = len(axes)
    pts = []
    for i, axis in enumerate(axes):
        angle = -math.pi / 2 + i * (2 * math.pi / n)
        r = RADIUS * max(0, min(100, axis["value"])) / 100
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        pts.append((x, y))
    return pts


def render_panel(title, axes, offset_x, show_values):
    cx = offset_x + PANEL_W / 2
    cy = PANEL_H / 2 + 10
    n = max(len(axes), 3)
    parts = []

    parts.append(
        f'<text x="{cx}" y="30" text-anchor="middle" class="title">{title}</text>'
    )

    for ring in RINGS:
        r = RADIUS * ring / 100
        ring_pts = []
        for i in range(n):
            angle = -math.pi / 2 + i * (2 * math.pi / n)
            ring_pts.append(f"{cx + r*math.cos(angle):.1f},{cy + r*math.sin(angle):.1f}")
        parts.append(f'<polygon points="{" ".join(ring_pts)}" class="grid" />')

    for i in range(n):
        angle = -math.pi / 2 + i * (2 * math.pi / n)
        x = cx + RADIUS * math.cos(angle)
        y = cy + RADIUS * math.sin(angle)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" class="grid" />')

    if axes:
        pts = polygon_points(axes, cx, cy)
        pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(f'<polygon points="{pts_str}" class="fill-area" />')
        for x, y in pts:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" class="dot" />')

    for i, axis in enumerate(axes):
        angle = -math.pi / 2 + i * (2 * math.pi / n)
        lx = cx + (RADIUS + 34) * math.cos(angle)
        ly = cy + (RADIUS + 34) * math.sin(angle)
        anchor = "middle"
        if math.cos(angle) > 0.3:
            anchor = "start"
        elif math.cos(angle) < -0.3:
            anchor = "end"
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" class="label">{axis["label"]}</text>'
        )
        if show_values:
            shown = axis.get("raw", axis["value"])
            if isinstance(shown, (int, float)) and "raw" in axis:
                shown = f'{axis["value"]:.0f}'
            parts.append(
                f'<text x="{lx:.1f}" y="{ly+14:.1f}" text-anchor="{anchor}" class="value">{shown}</text>'
            )

    return "\n".join(parts)


def build_svg(left_title, left_axes, right_title, right_axes, show_values):
    width = PANEL_W * 2
    height = PANEL_H
    style = f"""
    <style>
      text {{ font-family: 'Segoe UI', Helvetica, Arial, sans-serif; }}
      .title {{ font-size: 15px; font-weight: 700; fill: #1f2328; }}
      .label {{ font-size: 11px; font-weight: 600; fill: #1f2328; }}
      .value {{ font-size: 10px; fill: #57606a; }}
      .grid {{ fill: none; stroke: #d0d7de; stroke-width: 1; }}
      .fill-area {{ fill: {ACCENT}; fill-opacity: 0.28; stroke: {ACCENT}; stroke-width: 2; }}
      .dot {{ fill: {ACCENT}; }}
      @media (prefers-color-scheme: dark) {{
        .title {{ fill: #e6edf3; }}
        .label {{ fill: #e6edf3; }}
        .value {{ fill: #8b949e; }}
        .grid {{ stroke: #30363d; }}
      }}
    </style>
    """
    left = render_panel(left_title, left_axes, 0, show_values)
    right = render_panel(right_title, right_axes, PANEL_W, show_values)
    divider = f'<line x1="{PANEL_W}" y1="10" x2="{PANEL_W}" y2="{PANEL_H-10}" class="grid" />'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
{style}
{left}
{divider}
{right}
</svg>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills", default="assets/skills.json")
    ap.add_argument("--github", required=True)
    ap.add_argument("-o", "--out", default="assets/radar")
    ap.add_argument("--limit", type=int, default=7)
    ap.add_argument("--curve", type=float, default=0.4)
    ap.add_argument("--exclude", default="")
    ap.add_argument("--values", action="store_true")
    args = ap.parse_args()

    with open(args.skills, "r", encoding="utf-8") as f:
        skills_doc = json.load(f)
    left_title = skills_doc.get("title", "Skill Radar")
    left_axes = skills_doc["axes"]

    token = os.environ.get("GITHUB_TOKEN")
    right_axes = language_axes(args.github, token, args.limit, args.curve, args.exclude)
    right_title = f"{args.github} · language mix"

    svg = build_svg(left_title, left_axes, right_title, right_axes, args.values)

    out_path = args.out if args.out.endswith(".svg") else args.out + ".svg"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
