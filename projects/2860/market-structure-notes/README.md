# Market Structure Notes

Clean, extensible CLI tool for structured technical analysis note-taking. Installable + optional web viewer.

Supports 8 templates (Wyckoff, SMC, Price Action, Minimal, Volume Profile, Macro, Session, and more). Designed to be community-extensible.

## Quick start (after install)

```bash
pip install -e .
msn templates
msn new --template wyckoff --symbol BTC --timeframe 4H
msn list
msn search "liquidity"
msn serve --port 8765
```

## Adding new templates

Drop any `.md` file with `{{date}}`, `{{symbol}}`, and `{{timeframe}}` placeholders into the `templates/` folder. The CLI discovers them automatically.

## Web viewer

```bash
pip install 'market-structure-notes[web]'
msn serve
```

Then open http://localhost:8765 to browse all notes in the browser.

## Project goals

- Provide a solid, neutral foundation for structured market notes
- Stay completely private — no trading logic or personal data is included
- Allow easy extension by the community

## License

MIT

## Status

Early version. Contributions welcome.