#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build summary.json from a single SEC Form 13F quarterly dataset.

Downloads the official quarterly ZIP from www.sec.gov, parses
COVERPAGE.tsv + SUBMISSION.tsv + INFOTABLE.tsv, and computes:
  - Top managers by total reported $value
  - Most-widely-held issuers (by number of distinct funds)

Output: summary.json next to this script (the dashboard reads it directly).

Usage:
    python build_summary.py                              # default quarter
    python build_summary.py 01jun2025-31aug2025          # custom date range slug

The date-range slug must match the SEC filename pattern, e.g.:
    01mar2025-31may2025  ->  01mar2025-31may2025_form13f.zip
"""

import io
import csv
import sys
import json
import zipfile
from pathlib import Path
from collections import defaultdict

import requests

DEFAULT_QUARTER = '01jun2025-31aug2025'
SEC_BASE = 'https://www.sec.gov/files/structureddata/data/form-13f-data-sets'
# SEC requires a contactable User-Agent. Override via env if you fork this.
UA = 'Starchild Community 13F Dashboard MVP (contact@example.com)'

BASE = Path(__file__).resolve().parent
OUT = BASE / 'summary.json'


def download_zip(quarter_slug: str) -> zipfile.ZipFile:
    url = f'{SEC_BASE}/{quarter_slug}_form13f.zip'
    print(f'Downloading {url} ...')
    r = requests.get(url, headers={'User-Agent': UA}, timeout=120)
    r.raise_for_status()
    return zipfile.ZipFile(io.BytesIO(r.content))


def reader(z: zipfile.ZipFile, name: str):
    return csv.DictReader(io.TextIOWrapper(z.open(name), encoding='utf-8', newline=''), delimiter='\t')


def build(quarter_slug: str) -> dict:
    z = download_zip(quarter_slug)
    prefix = quarter_slug.upper()

    mgr = {}
    for row in reader(z, f'{prefix}/COVERPAGE.tsv'):
        mgr[row['ACCESSION_NUMBER']] = (row.get('FILINGMANAGER_NAME') or '').strip()

    cik_map = {}
    filings_count = 0
    for row in reader(z, f'{prefix}/SUBMISSION.tsv'):
        filings_count += 1
        cik_map[row['ACCESSION_NUMBER']] = (row.get('CIK') or '').strip()

    manager_value = defaultdict(float)
    issuer_funds = defaultdict(set)
    issuer_value = defaultdict(float)
    holdings_count = 0

    for row in reader(z, f'{prefix}/INFOTABLE.tsv'):
        acc = row['ACCESSION_NUMBER']
        holdings_count += 1
        try:
            v = float(row.get('VALUE') or 0)
        except Exception:
            v = 0.0

        manager_value[(mgr.get(acc, '(unknown)') or '(unknown)', cik_map.get(acc, ''))] += v

        if (row.get('PUTCALL') or '').strip() == '':
            key = ((row.get('NAMEOFISSUER') or '').strip(), (row.get('CUSIP') or '').strip())
            issuer_funds[key].add(acc)
            issuer_value[key] += v

    top_mgr = sorted(manager_value.items(), key=lambda x: x[1], reverse=True)[:20]
    pop = sorted(issuer_value.items(), key=lambda x: (len(issuer_funds[x[0]]), x[1]), reverse=True)[:20]

    return {
        'dataset': {
            'quarters': [quarter_slug],
            'filings_count': filings_count,
            'holdings_count': holdings_count,
        },
        'top_managers_latest': [
            {'manager_name': k[0], 'cik': k[1], 'total_musd': round(v / 1000.0, 2)}
            for k, v in top_mgr
        ],
        'popular_holdings_latest': [
            {'issuer': k[0], 'cusip': k[1], 'fund_count': len(issuer_funds[k]), 'total_musd': round(v / 1000.0, 2)}
            for k, v in pop
        ],
    }


def main():
    quarter = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUARTER
    summary = build(quarter)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {OUT}')
    print(f'  filings  = {summary["dataset"]["filings_count"]:,}')
    print(f'  holdings = {summary["dataset"]["holdings_count"]:,}')


if __name__ == '__main__':
    main()
