"""Render last-year activity and open-source impact cards as light/dark SVGs.

Usage: GITHUB_TOKEN=... python scripts/impact_cards.py <login> <out_dir>
"""

import json
import os
import sys
import urllib.request
from html import escape

# Inlined rather than a fragment: the three *ByRepository connections have
# different GraphQL types, so one fragment cannot cover them all.
# contributionsCollection has no from/to, so GitHub returns the past year;
# the "last 12 months" card titles depend on that default.
BY_REPO = "repository { nameWithOwner isPrivate stargazerCount owner { login } } contributions { totalCount }"
QUERY = f"""
query($login: String!) {{
  user(login: $login) {{
    contributionsCollection {{
      startedAt
      endedAt
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      commitContributionsByRepository(maxRepositories: 100) {{ {BY_REPO} }}
      pullRequestContributionsByRepository(maxRepositories: 100) {{ {BY_REPO} }}
      pullRequestReviewContributionsByRepository(maxRepositories: 100) {{ {BY_REPO} }}
    }}
  }}
}}
"""

# Same colours as the github-readme-stats "default" and "github_dark" themes,
# so these cards sit next to the generated stats cards without clashing.
THEMES = {
    "light": {"bg": "#fffefe", "title": "#2f80ed", "text": "#434d58", "muted": "#7a8592", "accent": "#4c71f2", "rule": "#e4e2e2"},
    "dark": {"bg": "#0d1117", "title": "#58a6ff", "text": "#c3d1d9", "muted": "#8b949e", "accent": "#1f6feb", "rule": "#30363d"},
}
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"
TOP_REPOS = 6
# Longest repo name that fits before the right-aligned star column at x=360.
NAME_MAX = 42


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


def external_repos(login, contributions):
    """Merge per-repo counts, keeping only public repos owned by someone else."""
    repos = {}
    for field, key in (
        ("pullRequestContributionsByRepository", "prs"),
        ("pullRequestReviewContributionsByRepository", "reviews"),
        ("commitContributionsByRepository", "commits"),
    ):
        for item in contributions[field]:
            repo = item["repository"]
            if repo["isPrivate"] or repo["owner"]["login"].lower() == login.lower():
                continue
            row = repos.setdefault(
                repo["nameWithOwner"],
                {"name": repo["nameWithOwner"], "stars": repo["stargazerCount"], "prs": 0, "reviews": 0, "commits": 0},
            )
            row[key] = item["contributions"]["totalCount"]
    # Stars break ties so that, among one-PR repos, well-known projects outrank tiny ones.
    return sorted(repos.values(), key=lambda r: (r["prs"] + r["reviews"], r["stars"]), reverse=True)


def card(width, height, title, body, theme):
    """Wrap pre-rendered SVG elements in a themed card with a title."""
    c = THEMES[theme]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">
<style>
  text {{ font-family: {FONT}; fill: {c['text']}; }}
  .title {{ font-size: 18px; font-weight: 600; fill: {c['title']}; }}
  .muted {{ font-size: 12px; fill: {c['muted']}; }}
  .num {{ font-size: 26px; font-weight: 700; fill: {c['accent']}; }}
  .label {{ font-size: 13px; }}
  .cell {{ font-size: 13px; }}
  .head {{ font-size: 12px; font-weight: 600; fill: {c['muted']}; }}
</style>
<rect x="0.5" y="0.5" rx="4.5" width="{width - 1}" height="{height - 1}" fill="{c['bg']}"/>
<text x="25" y="35" class="title">{escape(title)}</text>
{body}
</svg>
"""


def activity_svg(contributions, theme):
    stats = [
        ("Commits", contributions["totalCommitContributions"]),
        ("PRs opened", contributions["totalPullRequestContributions"]),
        ("PRs reviewed", contributions["totalPullRequestReviewContributions"]),
        ("Issues", contributions["totalIssueContributions"]),
    ]
    span = f"{contributions['startedAt'][:10]} → {contributions['endedAt'][:10]}"
    parts = [f'<text x="25" y="56" class="muted">{span}</text>']
    for i, (label, value) in enumerate(stats):
        x = 25 + i * 110
        parts.append(f'<text x="{x}" y="105" class="num">{value:,}</text>')
        parts.append(f'<text x="{x}" y="128" class="label">{label}</text>')
    # 467 is the github-readme-stats card width, so this lines up with the stats card above it.
    return card(467, 150, "Last 12 Months", "\n".join(parts), theme)


def impact_svg(rows, theme):
    cols = [("★", 360), ("PRs", 415), ("Reviews", 485), ("Commits", 555)]
    parts = ['<text x="25" y="70" class="head">Repository</text>']
    parts += [f'<text x="{x}" y="70" class="head" text-anchor="end">{h}</text>' for h, x in cols]
    parts.append(f'<line x1="25" y1="79" x2="555" y2="79" stroke="{THEMES[theme]['rule']}"/>')
    for i, r in enumerate(rows):
        y = 102 + i * 26
        name = r["name"] if len(r["name"]) <= NAME_MAX else r["name"][: NAME_MAX - 1] + "…"
        parts.append(f'<text x="25" y="{y}" class="cell">{escape(name)}</text>')
        for (_, x), value in zip(cols, (r["stars"], r["prs"], r["reviews"], r["commits"])):
            parts.append(f'<text x="{x}" y="{y}" class="cell" text-anchor="end">{value:,}</text>')
    height = 102 + len(rows) * 26
    return card(580, height, "Open Source Impact (last 12 months)", "\n".join(parts), theme)


def main():
    login, out_dir = sys.argv[1], sys.argv[2]
    contributions = fetch(login, os.environ["GITHUB_TOKEN"])
    rows = external_repos(login, contributions)[:TOP_REPOS]
    os.makedirs(out_dir, exist_ok=True)
    for theme in THEMES:
        with open(os.path.join(out_dir, f"activity-{theme}.svg"), "w") as f:
            f.write(activity_svg(contributions, theme))
        with open(os.path.join(out_dir, f"impact-{theme}.svg"), "w") as f:
            f.write(impact_svg(rows, theme))


if __name__ == "__main__":
    main()
