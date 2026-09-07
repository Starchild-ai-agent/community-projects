---
name: local-pii-redactor
version: 1.0.0
description: Detect and redact common personally identifiable information from text locally, with deterministic replacement and a JSON detection report.
tags:
  - privacy
  - pii
  - redaction
  - text-processing
  - security
delivery: script
metadata:
  starchild:
    emoji: "🛡️"
    skillKey: local-pii-redactor
---

# Local PII Redactor

Use this skill when text contains emails, phone numbers, IPv4 addresses, credit-card-like numbers, or long token-like strings and the user wants a safe-to-share version.

## Guarantees

- Processing is deterministic and local to the agent runtime.
- The tool never sends text to a third-party API.
- Replacement tags are stable: `[EMAIL]`, `[PHONE]`, `[IP ADDRESS]`, `[CARD]`, and `[TOKEN]`.
- The report contains counts only, not the original matched values.

## Runnable interface

The bundled script accepts UTF-8 text from stdin and prints JSON to stdout:

```bash
printf 'Contact jane@example.com from 192.168.1.2' | python3 skills/local-pii-redactor/scripts/redact.py
```

Output shape:

```json
{
  "redacted_text": "Contact [EMAIL] from [IP ADDRESS]",
  "counts": {"email": 1, "phone": 0, "ipv4": 1, "credit_card": 0, "token": 0},
  "total": 2
}
```

## Workflow

1. Read the text from stdin or a file supplied by the caller.
2. Apply the patterns in a fixed order: email, phone, IPv4, credit card, token.
3. Replace matches with the corresponding stable tag.
4. Return the redacted text and aggregate counts as JSON.
5. Tell the user that pattern matching is heuristic and should be reviewed before external sharing.

## Limitations

This is not a compliance-grade DLP system. It can miss obfuscated values and can flag numeric strings that are not secrets. Do not treat the report as proof that text is safe.

## Troubleshooting

- If the output is empty, verify that UTF-8 text was actually piped to stdin.
- If a phone number is not detected, normalize unusual punctuation before scanning.
- For files, use shell redirection: `python3 .../redact.py < notes.txt`.
