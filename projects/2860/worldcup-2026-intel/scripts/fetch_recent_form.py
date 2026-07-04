#!/usr/bin/env python3
"""
Reusable Recent Form Fetcher for World Cup 2026 Market Desk

Fetches real historical match data from FBref for national teams.
Outputs structured CSV with source metadata for credibility and GitHub publishing.

Usage:
    python fetch_recent_form.py --teams "United States,England,Croatia" --limit 10
    python fetch_recent_form.py --all --limit 8

Requirements:
    pip install requests beautifulsoup4 pandas lxml

Data source: FBref.com (https://fbref.com)
Each row is tagged with source_url so the data remains auditable.
"""

import argparse
import csv
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
FBREF_BASE = "https://fbref.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; WorldCupMarketDesk/0.1; +https://github.com/yourname/worldcup-market-desk)"
}
DELAY = 1.2  # polite scraping

# FBref squad codes for the 48 World Cup teams (2026)
# These are the codes used in FBref URLs. Add more as needed.
TEAM_CODES = {
    "United States": "USA",
    "England": "ENG",
    "Croatia": "CRO",
    "Ghana": "GHA",
    "Panama": "PAN",
    "Paraguay": "PAR",
    "Australia": "AUS",
    "Türkiye": "TUR",
    "Mexico": "MEX",
    "South Korea": "KOR",
    "Brazil": "BRA",
    "Germany": "GER",
    "France": "FRA",
    "Spain": "ESP",
    "Argentina": "ARG",
    "Portugal": "POR",
    "Netherlands": "NED",
    "Belgium": "BEL",
    # ... add remaining 30 teams as you expand
}

OUTPUT_FILE = Path(__file__).parent / "recent_form_real.csv"


def get_fbref_url(team_name: str) -> str | None:
    """Return FBref squad URL for a team."""
    code = TEAM_CODES.get(team_name)
    if not code:
        return None
    # National team pages use the code + country slug
    slug = team_name.lower().replace(" ", "-").replace("'", "")
    return f"{FBREF_BASE}/en/squads/{code}/{slug}-Stats"


def fetch_recent_matches(team_name: str, limit: int = 10) -> list[dict]:
    """
    Scrape the last N matches for a national team from FBref.
    Returns list of dicts with keys:
        date, opponent, result, score, competition, xg, xga, source_url
    """
    url = get_fbref_url(team_name)
    if not url:
        print(f"[SKIP] No FBref code for {team_name}")
        return []

    print(f"[FETCH] {team_name} → {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"[ERROR] {team_name}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")

    # FBref usually has a "Scores & Fixtures" table
    # We look for the first table that contains match data
    table = soup.find("table", {"id": re.compile(r"matchlogs|scores")})
    if not table:
        # fallback: try any table with "Date" header
        tables = soup.find_all("table")
        for t in tables:
            if t.find("th", string=re.compile(r"Date|Comp")):
                table = t
                break

    if not table:
        print(f"[WARN] No match table found for {team_name}")
        return []

    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) < 6:
            continue

        # Typical FBref row structure for national teams
        # Date | Comp | Round | Day | Venue | Result | GF | GA | Opponent | ...
        date_text = cells[0].get_text(strip=True)
        if not re.match(r"\d{4}-\d{2}-\d{2}", date_text):
            continue

        comp = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        result = cells[5].get_text(strip=True) if len(cells) > 5 else ""
        gf = cells[6].get_text(strip=True) if len(cells) > 6 else ""
        ga = cells[7].get_text(strip=True) if len(cells) > 7 else ""
        opp = cells[8].get_text(strip=True) if len(cells) > 8 else ""

        # Skip future matches (no result yet)
        if result not in ("W", "D", "L"):
            continue

        score = f"{gf}-{ga}" if gf and ga else ""

        # xG / xGA are usually in later columns if present
        xg = cells[9].get_text(strip=True) if len(cells) > 9 else ""
        xga = cells[10].get_text(strip=True) if len(cells) > 10 else ""

        rows.append({
            "team": team_name,
            "match_date": date_text,
            "opponent": opp,
            "result": result,
            "score": score,
            "competition": comp,
            "xg": xg,
            "xga": xga,
            "source": "FBref",
            "source_url": url,
        })

        if len(rows) >= limit:
            break

    time.sleep(DELAY)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", help="Comma-separated list of teams")
    parser.add_argument("--all", action="store_true", help="Fetch for all teams in TEAM_CODES")
    parser.add_argument("--limit", type=int, default=10, help="Matches per team (default 10)")
    args = parser.parse_args()

    if args.all:
        team_list = list(TEAM_CODES.keys())
    elif args.teams:
        team_list = [t.strip() for t in args.teams.split(",")]
    else:
        print("Usage: --teams 'United States,England'  or  --all")
        sys.exit(1)

    all_matches = []
    for team in team_list:
        matches = fetch_recent_matches(team, limit=args.limit)
        all_matches.extend(matches)
        print(f"  → {len(matches)} matches for {team}")

    if not all_matches:
        print("No data fetched.")
        return

    # Write CSV
    fieldnames = ["team", "match_date", "opponent", "result", "score",
                  "competition", "xg", "xga", "source", "source_url"]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_matches)

    print(f"\n[OK] Wrote {len(all_matches)} matches to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()