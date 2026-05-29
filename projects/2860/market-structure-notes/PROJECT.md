# Market Structure Notes

Clean, extensible CLI tool for structured technical analysis note-taking. Supports multiple templates (Wyckoff, SMC, Price Action, Minimal) and is designed for easy community extensions.

## What it does

- Creates dated, structured notes from reusable templates
- Supports 8 built-in templates (Wyckoff, SMC, Price Action, Minimal, Volume Profile, Macro, Session, etc.)
- Simple search and listing of existing notes
- Export notes to JSON
- Optional web viewer (`msn serve`)
- Fully installable via pip
- Zero personal trading logic or data included

## Required environment

None. Pure local tool.

## How to start

```bash
pip install -e .
msn --help
msn new --template wyckoff --symbol BTC --timeframe 4H
msn serve
```

## Outputs

- `notes/YYYY-MM-DD-symbol-timeframe.md` files
- Searchable, filterable note collection
- Exportable bundles for Obsidian / Notion / archive

## Troubleshooting

- Template not found: check `templates/` folder for .md files
- Permission error on note creation: ensure `notes/` directory is writable

## Extensibility

Add new templates by dropping a `.md` file in `templates/`. The CLI auto-discovers them. Community contributions welcome via PR.