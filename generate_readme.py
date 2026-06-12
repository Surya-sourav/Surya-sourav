#!/usr/bin/env python3
"""Generate profile README assets with live GitHub stats."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, List

from PIL import Image

REPO_ROOT = pathlib.Path(__file__).resolve().parent
README_PATH = REPO_ROOT / "README.md"
LIGHT_SVG_PATH = REPO_ROOT / "light_mode.svg"
DARK_SVG_PATH = REPO_ROOT / "dark_mode.svg"

USERNAME = "Surya-sourav"
EMAIL = "surya.aimlx@gmail.com"
AVATAR_URL = f"https://github.com/{USERNAME}.png?size=512"
GRAPHQL_URL = "https://api.github.com/graphql"
ASCII_CHARS = "@%#*+=-:. "

PROFILE_INFO = [
    ("os", "Linux, macOS"),
    ("uptime", "22 years & continuing"),
    ("host", "LocalHost"),
    ("kernel", "Any Kernel You Like"),
    ("ide", "VS Code, IDEA"),
    ("languages", "TypeScript, Go, Java, Python, C++"),
    ("software", "Low Level Systems, Backends, AI Pipelines"),
    ("hobbies", "Trekking, Traveling, Camping"),
    ("email", EMAIL),
]


@dataclass
class GitHubStats:
    commits: int
    repositories: int
    stars: int
    followers: int
    loc: int


class GitHubClient:
    def __init__(self, token: str):
        self.token = token

    def graphql(self, query: str, variables: Dict[str, object]) -> Dict[str, object]:
        req = urllib.request.Request(
            GRAPHQL_URL,
            data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
            headers={
                "Authorization": f"bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": f"{USERNAME}-readme-generator",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if payload.get("errors"):
            raise RuntimeError(f"GitHub GraphQL errors: {payload['errors']}")
        return payload["data"]

    def fetch_stats(self, username: str) -> GitHubStats:
        summary_query = """
        query($login: String!) {
          user(login: $login) {
            followers { totalCount }
            repositories(ownerAffiliations: OWNER, isFork: false, first: 1) { totalCount }
            contributionsCollection {
              contributionCalendar {
                totalContributions
              }
            }
          }
        }
        """

        summary = self.graphql(summary_query, {"login": username})["user"]
        total_repositories = summary["repositories"]["totalCount"]

        repo_query = """
        query($login: String!, $after: String) {
          user(login: $login) {
            repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $after) {
              pageInfo { hasNextPage endCursor }
              nodes {
                stargazerCount
                languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
                  edges { size }
                }
              }
            }
          }
        }
        """

        stars = 0
        language_bytes = 0
        cursor = None
        while True:
            repo_data = self.graphql(repo_query, {"login": username, "after": cursor})["user"]["repositories"]
            for repo in repo_data["nodes"]:
                stars += repo["stargazerCount"]
                language_bytes += sum(edge["size"] for edge in repo["languages"]["edges"])

            page_info = repo_data["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]

        approx_loc = round(language_bytes / 40) if language_bytes else 0

        return GitHubStats(
            commits=summary["contributionsCollection"]["contributionCalendar"]["totalContributions"],
            repositories=total_repositories,
            stars=stars,
            followers=summary["followers"]["totalCount"],
            loc=approx_loc,
        )


def download_image(url: str) -> Image.Image:
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read()
    from io import BytesIO

    return Image.open(BytesIO(data)).convert("L")


def to_ascii_lines(image: Image.Image, width: int = 30) -> List[str]:
    ratio = image.height / image.width
    height = max(1, int(width * ratio * 0.55))
    resized = image.resize((width, height))
    pixels = list(resized.tobytes())

    lines: List[str] = []
    for y in range(height):
        row = pixels[y * width : (y + 1) * width]
        text = "".join(ASCII_CHARS[int(value / 255 * (len(ASCII_CHARS) - 1))] for value in row)
        lines.append(text.rstrip() or " ")
    return lines


def render_svg(theme: str, ascii_lines: List[str], stats: GitHubStats) -> str:
    if theme == "dark":
        bg = "#0d1117"
        fg = "#c9d1d9"
        subtle = "#8b949e"
        accent = "#58a6ff"
        command = "#3fb950"
        border = "#30363d"
    else:
        bg = "#ffffff"
        fg = "#1f2328"
        subtle = "#57606a"
        accent = "#0969da"
        command = "#1a7f37"
        border = "#d0d7de"

    lines = []
    lines.append(f'<svg width="980" height="510" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{USERNAME} profile card">')
    lines.append(f'  <rect width="980" height="510" fill="{bg}"/>')
    lines.append(f'  <text x="26" y="40" font-size="24" font-weight="700" fill="{fg}" font-family="monospace">{USERNAME.lower()}@localhost ~ %</text>')
    lines.append(f'  <line x1="24" y1="55" x2="956" y2="55" stroke="{border}" stroke-width="2"/>')

    y = 88
    for row in ascii_lines[:30]:
        lines.append(
            f'  <text x="34" y="{y}" font-size="11" fill="{fg}" font-family="monospace">{html.escape(row)}</text>'
        )
        y += 12

    row_y = 88
    for key, value in PROFILE_INFO:
        lines.append(
            f'  <text x="390" y="{row_y}" font-size="14" font-family="monospace" fill="{fg}">'
            f'<tspan fill="{accent}" font-weight="700">{html.escape(key):<10}</tspan>'
            f'<tspan fill="{subtle}"> : {html.escape(value)}</tspan></text>'
        )
        row_y += 32

    lines.append(
        f'  <text x="390" y="380" font-size="14" font-family="monospace" fill="{fg}">' 
        f'<tspan fill="{subtle}">$</tspan> <tspan fill="{command}" font-weight="700">cat ~/github-stats</tspan></text>'
    )

    stats_lines = [
        f"total_commits      : {stats.commits:,}",
        f"total_repositories : {stats.repositories:,}",
        f"total_stars        : {stats.stars:,}",
        f"followers          : {stats.followers:,}",
        f"lines_of_code*     : {stats.loc:,}",
    ]
    sy = 408
    for stat_line in stats_lines:
        lines.append(
            f'  <text x="390" y="{sy}" font-size="13" font-family="monospace" fill="{subtle}">{html.escape(stat_line)}</text>'
        )
        sy += 18

    lines.append("</svg>")
    return "\n".join(lines)


def update_readme(stats: GitHubStats) -> None:
    content = README_PATH.read_text(encoding="utf-8")
    new_block = f"""<!-- DYNAMIC_STATS_START -->
| Metric | Value |
| --- | ---: |
| Total commits (year) | {stats.commits:,} |
| Public repositories | {stats.repositories:,} |
| Total stars | {stats.stars:,} |
| Followers | {stats.followers:,} |
| Lines of code* | {stats.loc:,} |

_Last updated: {dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M UTC')}_
<!-- DYNAMIC_STATS_END -->"""

    content, replaced = re.subn(
        r"<!-- DYNAMIC_STATS_START -->.*?<!-- DYNAMIC_STATS_END -->",
        new_block,
        content,
        flags=re.S,
    )
    if not replaced:
        raise RuntimeError("README.md is missing DYNAMIC_STATS markers")

    README_PATH.write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate profile README assets")
    parser.add_argument("--skip-api", action="store_true", help="Use fallback values instead of GitHub API")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.skip_api:
        stats = GitHubStats(commits=0, repositories=0, stars=0, followers=0, loc=0)
    else:
        token = os.getenv("PROFILE_STATS_TOKEN") or os.getenv("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("Missing token: set PROFILE_STATS_TOKEN or GITHUB_TOKEN")
        stats = GitHubClient(token).fetch_stats(USERNAME)

    image = download_image(AVATAR_URL)
    ascii_lines = to_ascii_lines(image, width=30)

    LIGHT_SVG_PATH.write_text(render_svg("light", ascii_lines, stats), encoding="utf-8")
    DARK_SVG_PATH.write_text(render_svg("dark", ascii_lines, stats), encoding="utf-8")
    update_readme(stats)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, urllib.error.URLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
