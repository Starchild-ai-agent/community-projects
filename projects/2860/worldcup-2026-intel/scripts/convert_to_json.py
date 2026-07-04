#!/usr/bin/env python3
"""
Convert CSVs to JSON for the frontend.
Run this after editing recent_form_real.csv or group_market.csv.
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

def convert_recent_form():
    real_teams = ["United States", "Paraguay", "Australia", "Türkiye", "England", "Croatia", "Ghana", "Panama"]
    data = {}
    with open(DATA_DIR / "recent_form_real.csv") as f:
        for row in csv.DictReader(f):
            t = row["team"]
            if t not in real_teams:
                continue
            if t not in data:
                data[t] = []
            data[t].append({
                "d": row["match_date"],
                "o": row["opponent"],
                "r": row["result"],
                "s": row["score"],
                "c": row["competition"],
                "src": row["source"],
                "url": row["source_url"]
            })
    with open(DATA_DIR / "recent_form.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"[OK] recent_form.json: {len(data)} teams")

def convert_groups():
    groups = defaultdict(list)
    with open(DATA_DIR / "group_market.csv") as f:
        for row in csv.DictReader(f):
            groups[row["group"]].append({
                "name": row["team"],
                "market": float(row["market_prob_top_group"]),
                "user": float(row["user_prob_top_group"]) if row.get("user_prob_top_group") else 0.0
            })
    data = [{"group": g, "teams": teams} for g, teams in sorted(groups.items())]
    with open(DATA_DIR / "groups.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"[OK] groups.json: {len(data)} groups")

if __name__ == "__main__":
    convert_recent_form()
    convert_groups()
    print("Done. Commit the new JSONs + CSVs.")