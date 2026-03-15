# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
# Install dependencies
pip install -r requirements.txt

# Run the development server (http://localhost:8050)
python app.py
```

The app runs with `debug=True` and binds to `0.0.0.0:8050`. There are no tests or lint configurations defined.

## Architecture

The project is a single-page **Plotly Dash** financial dashboard that fetches live market data via **yfinance** and renders interactive charts. It is structured across three modules:

- **`data.py`** — All data fetching and computation. Functions: `get_stock_data`, `get_benchmarks`, `compute_moving_averages`, `compute_rsi`, `compute_cumulative_performance`, `compute_monthly_volume`, `period_to_dates`. No caching here — caching is handled at the Flask layer in `app.py`.
- **`layout.py`** — Pure UI construction; returns Dash component trees with no callbacks or data logic. `build_layout()` is the root layout builder; `benchmark_card()` builds individual index cards.
- **`app.py`** — App initialization, Flask-Caching setup (SimpleCache, 5-minute TTL), theme helpers, and all Dash callbacks. All reactive logic lives here.

### State management

Dash `dcc.Store` components act as client-side state:
- `watchlist-store` — list of user-added tickers
- `compare-store` — tickers for normalized comparison chart
- `active-ticker-store` — currently selected ticker (drives main chart)
- `active-period-store` — selected period string (e.g. `"6M"`)
- `theme-store` — `"light"` or `"dark"`

Benchmark cards auto-refresh every 60 seconds via `dcc.Interval`.

### Chart callbacks (app.py)

- `update_chart` — main candlestick/line/area/OHLC chart + RSI + asset header + summary stats; triggered by ticker, period, date picker, interval, MA toggles, RSI toggle, chart type, or theme change.
- `update_extra_charts` — cumulative performance (from 2000, weekly) and monthly volume (last 3 years, daily); triggered by ticker or theme.
- `update_comparison` — normalized close price comparison (base 100) for tickers in `compare-store`.

## GitHub Repository

O projeto está publicado em **https://github.com/aalbemd/financial-dashboard**.

### Auto-sync com GitHub

A cada alteração feita por Claude Code (Edit ou Write), o projeto é automaticamente commitado e enviado ao GitHub via hook `PostToolUse` configurado em `.claude/settings.local.json`.

O hook executa:
```bash
git add -A
git commit -m "auto-update: YYYY-MM-DD HH:MM:SS"
git push origin master
```

Para sincronizar manualmente:
```bash
cd "financial-dashboard"
git add -A && git commit -m "mensagem" && git push origin master
```

O `gh` CLI está instalado em `C:\Program Files\GitHub CLI\gh.exe` e autenticado com a conta **aalbemd**.

### Styling

`assets/style.css` is auto-loaded by Dash. Theme switching is done by toggling the `className` on `#app-container` between `light-theme` and `dark-theme`; chart colors are recalculated in Python callbacks and passed to Plotly figures.
