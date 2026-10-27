"""Render the last-12-months activity card as light/dark SVGs.

Usage: GITHUB_TOKEN=... python scripts/activity_card.py <login> <out_dir>
"""

import json
import os
import sys
import urllib.request
from html import escape

# contributionsCollection has no from/to, so GitHub returns the past year;
# the "Last 12 Months" card title depends on that default.
QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      startedAt
      endedAt
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
    }
  }
}
"""

# Same colours as the github-readme-stats "default" and "github_dark" themes,
# so this card sits next to the generated stats cards without clashing.
THEMES = {
    "light": {"bg": "#fffefe", "title": "#2f80ed", "text": "#434d58", "muted": "#7a8592", "accent": "#4c71f2"},
    "dark": {"bg": "#0d1117", "title": "#58a6ff", "text": "#c3d1d9", "muted": "#8b949e", "accent": "#1f6feb"},
}
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"


def fetch(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        sys.exit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]["contributionsCollection"]


def activity_svg(contributions, theme):
    c = THEMES[theme]
    stats = [
        ("Commits", contributions["totalCommitContributions"]),
        ("PRs opened", contributions["totalPullRequestContributions"]),
        ("PRs reviewed", contributions["totalPullRequestReviewContributions"]),
        ("Issues", contributions["totalIssueContributions"]),
    ]
    span = f"{contributions['startedAt'][:10]} → {contributions['endedAt'][:10]}"
    parts = []
    for i, (label, value) in enumerate(stats):
        x = 25 + i * 110
        parts.append(f'<text x="{x}" y="105" class="num">{value:,}</text>')
        parts.append(f'<text x="{x}" y="128" class="label">{label}</text>')
    # 467 is the github-readme-stats card width, so this lines up with the stats card above it.
    width, height = 467, 150
    title = "Last 12 Months"
    body = "\n".join(parts)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">
<style>
  text {{ font-family: {FONT}; fill: {c['text']}; }}
  .title {{ font-size: 18px; font-weight: 600; fill: {c['title']}; }}
  .muted {{ font-size: 12px; fill: {c['muted']}; }}
  .num {{ font-size: 26px; font-weight: 700; fill: {c['accent']}; }}
  .label {{ font-size: 13px; }}
</style>
<rect x="0.5" y="0.5" rx="4.5" width="{width - 1}" height="{height - 1}" fill="{c['bg']}"/>
<text x="25" y="35" class="title">{escape(title)}</text>
<text x="25" y="56" class="muted">{span}</text>
{body}
</svg>
"""


def main():
    login, out_dir = sys.argv[1], sys.argv[2]
    contributions = fetch(login, os.environ["GITHUB_TOKEN"])
    os.makedirs(out_dir, exist_ok=True)
    for theme in THEMES:
        with open(os.path.join(out_dir, f"activity-{theme}.svg"), "w") as f:
            f.write(activity_svg(contributions, theme))


if __name__ == "__main__":
    main()
