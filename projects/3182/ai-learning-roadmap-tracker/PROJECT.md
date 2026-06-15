# AI Learning Roadmap Tracker

## What
A browser-based tracker that helps learners plan and execute a practical AI upskilling journey.

Features:
- Generate a 30/60/90-day roadmap from level, goal, and weekly hours
- Weekly execution board with checkable tasks
- Milestone tracking for Day 30/60/90
- Reflection journal (wins, blockers, next focus)
- Exportable progress summary for mentors, managers, or accountability groups

## Required env
No environment variables required for this MVP.

## How to start
1. Serve as a preview from this project directory.
2. Open the preview URL.
3. Fill in your profile and click **Generate Plan**.
4. Track progress weekly and export a summary when needed.

## Outputs
- Interactive app UI at `src/index.html`
- User plan and progress persisted in browser local storage
- Copyable text summary from the Export section

## Troubleshooting
- If progress does not update, refresh once and try again.
- If local data appears stale, click **Reset Plan** and regenerate.
- If copied summary is empty, ensure a plan has been generated first.
