# Flywheel Monitor

## What
A lightweight interactive dashboard to evaluate deep-tech execution flywheels over time.

It tracks one compounding loop:

**deployment → recurring revenue → reinvestment → unit-cost decline → faster deployment**

The app includes:
- company selector
- KPI cards
- flywheel stage bars
- trend lines across reporting periods
- a loop velocity score and execution diagnosis

## Required env
None.

## How to start
For local preview in Starchild, serve this directory as a static preview:
- directory: `output/projects/flywheel-monitor/src`

## Outputs
- Interactive web UI (`src/index.html`)
- Public URL (after publish)

## Troubleshooting
- If the preview tab is blank, restart the preview.
- If values do not change, select another company from the dropdown.
- If you update data, hard refresh the preview tab.
