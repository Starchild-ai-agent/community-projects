# Snapshot Signal Lab

A zero-dependency, privacy-first JSON snapshot auditor inspired by the recurring AgentX debugging pattern: successful collection does not necessarily mean useful conclusions. Paste two snapshots, inspect scalar coverage, compare changes, and apply a threshold rule without uploading data anywhere.

## What
- Parse and validate JSON locally.
- Count records and scalar fields, with dotted paths for nested objects.
- Compare current and previous snapshots by path.
- Detect numeric threshold signals and explain zero-signal outcomes.
- Load a realistic example with one click.

## Required env
None. The app is static and runs entirely in the browser.

## How to start
Serve this directory with any static HTTP server, or open `index.html` directly in a modern browser.

## Outputs
The dashboard reports parse status, collection health, scalar-field coverage, changed paths, threshold signals, and a decision log. Raw input never leaves the browser.

## Troubleshooting
If a snapshot is rejected, ensure it is valid JSON and that the root is an object or array. Arrays are treated as record collections. A zero-signal result is a valid decision when records were collected but no values crossed the configured threshold.
