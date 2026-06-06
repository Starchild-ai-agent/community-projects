# MONSKILLS EZ-Path

## What
Open-source package mirror of `infiniteezverse/monskills-ezpath` wrapped for Starchild community publishing.

## Required env
None required for packaging/publishing. Runtime usage supports optional `EZPATH_URL`.

## How to start
```bash
cd output/projects/monskills-ezpath/src/repo
npm install
npm run build
npm test
```

## Outputs
- Built JS output in `dist/` after `npm run build`
- Package metadata in `package.json`

## Troubleshooting
- If npm install fails, retry with a clean cache or check registry connectivity.
- If tests fail, verify Node.js version is compatible with TypeScript/Jest versions in package.json.
