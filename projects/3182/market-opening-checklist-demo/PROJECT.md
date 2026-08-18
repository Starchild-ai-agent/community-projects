# Market Opening Checklist Demo

A standalone static template for preparing a market-opening review. It separates observable market facts from interpretation, risk assessment, and scenarios.

## What

This project is a self-contained demo template that helps traders and analysts prepare for market opening. It provides a structured checklist interface that separates observable pre-market facts from analysis, risk assessment, and scenario planning. The interface contains sample data for demonstration purposes only.

## Required env

No environment variables are required for this static demo project. The project runs entirely in the browser with no backend dependencies.

## How to start

1. The project is a static HTML file that can be served by any HTTP server.
2. Open `index.html` in a browser directly, or serve it via:
   ```bash
   python3 -m http.server 8080
   ```
3. Navigate to `http://localhost:8080` in your browser.

## Outputs / Behavior

When opened in a browser, the page displays an interactive market-opening checklist with:
- Pre-market observable facts section
- Risk assessment section
- Scenario planning section
- Sample data pre-populated for demonstration

Replace the sample values with verified live data before using the checklist in an actual market review.

## Troubleshooting

- **Page does not load**: Ensure your HTTP server is running and you are accessing the correct port (default 8080).
- **Styles not loading**: This is a single-file project — all CSS is inline. Check that the browser supports modern HTML5/CSS3.
- **Sample data shows stale values**: The data is hardcoded in the HTML for demo purposes. Edit `index.html` directly to update sample values.

This project is educational and is not financial advice.
