# Market Structure Notes

Clean, extensible CLI tool for structured technical analysis note-taking.

Supports Wyckoff, SMC/ICT, Price Action, and Minimal templates out of the box. Designed to be community-extensible.

## Quick start

```bash
python scripts/msn.py templates
python scripts/msn.py new --template wyckoff --symbol BTC --timeframe 4H
python scripts/msn.py list
python scripts/msn.py search "liquidity"
```

## Adding new templates

Drop any `.md` file with `{{date}}`, `{{symbol}}`, and `{{timeframe}}` placeholders into the `templates/` folder. The CLI discovers them automatically.

## Project goals

- Provide a solid, neutral foundation for structured market notes
- Stay completely private — no trading logic or personal data is included
- Allow easy extension by the community

## License

MIT

## Status

Early version. Contributions welcome.