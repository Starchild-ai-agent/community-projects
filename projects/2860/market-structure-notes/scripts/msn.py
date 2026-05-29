#!/usr/bin/env python3
"""
Market Structure Notes (MSN) - CLI tool for structured technical analysis notes.
Extensible template system. Zero personal methodology included.
"""

import argparse
import os
import re
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = ROOT / "templates"
NOTES_DIR = ROOT / "notes"
EXAMPLES_DIR = ROOT / "examples"

def ensure_notes_dir():
    NOTES_DIR.mkdir(exist_ok=True)

def list_templates():
    templates = sorted([p.stem for p in TEMPLATES_DIR.glob("*.md")])
    return templates

def load_template(name: str) -> str:
    path = TEMPLATES_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Template '{name}' not found in templates/")
    return path.read_text()

def substitute(template: str, values: dict) -> str:
    def replacer(match):
        key = match.group(1)
        return str(values.get(key, f"{{{{{key}}}}}"))
    return re.sub(r"\{\{(\w+)\}\}", replacer, template)

def create_note(template_name: str, symbol: str, timeframe: str, date_str: str = None):
    ensure_notes_dir()
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    template = load_template(template_name)
    values = {
        "date": date_str,
        "symbol": symbol.upper(),
        "timeframe": timeframe.upper()
    }
    content = substitute(template, values)
    
    filename = f"{date_str}-{symbol.upper()}-{timeframe.upper()}.md"
    filepath = NOTES_DIR / filename
    filepath.write_text(content)
    print(f"Created: {filepath.relative_to(ROOT)}")
    return filepath

def list_notes(filter_str: str = None):
    ensure_notes_dir()
    notes = sorted(NOTES_DIR.glob("*.md"), reverse=True)
    if filter_str:
        notes = [n for n in notes if filter_str.lower() in n.name.lower()]
    
    if not notes:
        print("No notes found.")
        return
    
    print(f"Found {len(notes)} notes:")
    for note in notes:
        print(f"  {note.name}")

def search_notes(query: str):
    ensure_notes_dir()
    results = []
    for note in NOTES_DIR.glob("*.md"):
        content = note.read_text().lower()
        if query.lower() in content:
            results.append(note.name)
    
    if not results:
        print(f"No matches for '{query}'")
        return
    
    print(f"Matches for '{query}':")
    for r in results:
        print(f"  {r}")

def export_notes(output_format: str = "json"):
    ensure_notes_dir()
    notes = list(NOTES_DIR.glob("*.md"))
    if not notes:
        print("No notes to export.")
        return
    
    if output_format == "json":
        data = []
        for note in notes:
            data.append({
                "filename": note.name,
                "content": note.read_text()
            })
        out_path = ROOT / "export.json"
        out_path.write_text(json.dumps(data, indent=2))
        print(f"Exported {len(notes)} notes to export.json")
    else:
        print("Only JSON export supported currently.")

def main():
    parser = argparse.ArgumentParser(
        description="Market Structure Notes CLI - structured technical analysis notes"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # new
    p_new = subparsers.add_parser("new", help="Create a new note from template")
    p_new.add_argument("--template", required=True, choices=list_templates(),
                       help="Template name (auto-discovered from templates/)")
    p_new.add_argument("--symbol", required=True, help="Trading symbol (e.g. BTC, ETH)")
    p_new.add_argument("--timeframe", required=True, help="Timeframe (e.g. 4H, 1D, 15m)")
    p_new.add_argument("--date", help="Override date (YYYY-MM-DD)")

    # list
    p_list = subparsers.add_parser("list", help="List existing notes")
    p_list.add_argument("--filter", help="Filter notes by substring")

    # search
    p_search = subparsers.add_parser("search", help="Search inside notes")
    p_search.add_argument("query", help="Search term")

    # export
    p_export = subparsers.add_parser("export", help="Export notes")
    p_export.add_argument("--format", default="json", choices=["json"], help="Export format")

    # templates
    p_templates = subparsers.add_parser("templates", help="List available templates")

    args = parser.parse_args()

    if args.command == "new":
        create_note(args.template, args.symbol, args.timeframe, args.date)
    elif args.command == "list":
        list_notes(args.filter)
    elif args.command == "search":
        search_notes(args.query)
    elif args.command == "export":
        export_notes(args.format)
    elif args.command == "templates":
        print("Available templates:")
        for t in list_templates():
            print(f"  {t}")

if __name__ == "__main__":
    main()