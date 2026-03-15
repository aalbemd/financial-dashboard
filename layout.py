import dash_bootstrap_components as dbc
from dash import dcc, html

PERIOD_BUTTONS = ["1S", "1M", "3M", "6M", "YTD", "1A", "2A", "Máx"]

INTERVAL_OPTIONS = [
    {"label": "Diário", "value": "1d"},
    {"label": "Semanal", "value": "1wk"},
    {"label": "Mensal", "value": "1mo"},
]

CHART_TYPE_OPTIONS = [
    {"label": "Candle", "value": "candle"},
    {"label": "OHLC", "value": "ohlc"},
    {"label": "Linha", "value": "line"},
    {"label": "Área", "value": "area"},
]


def benchmark_card(name: str, ticker: str, price, change_pct) -> dbc.Card:
    if price is None:
        price_text = "—"
        badge_color = "secondary"
        change_text = "—"
    else:
        price_text = f"{price:,.2f}"
        change_text = f"{change_pct:+.2f}%"
        badge_color = "success" if change_pct >= 0 else "danger"

    return html.Div(
        [
            html.P(name, className="benchmark-name"),
            html.P(price_text, className="benchmark-price"),
            dbc.Badge(change_text, color=badge_color, className="benchmark-badge"),
        ],
        className="benchmark-card mb-2 p-2",
        id={"type": "benchmark-card", "index": ticker},
        n_clicks=0,
        style={"cursor": "pointer"},
    )


def build_layout() -> dbc.Container:
    sidebar = dbc.Col(
        [
            html.H4("Benchmarks", className="sidebar-title"),
            html.Div(id="benchmark-cards"),
            html.Hr(className="sidebar-divider"),
            # ── TICKERS (watchlist) ──────────────────────────
            html.H5("TICKERS", className="sidebar-title"),
            dbc.InputGroup(
                [
                    dbc.Input(
                        id="ticker-input",
                        placeholder="Ex: AAPL, PETR4.SA",
                        type="text",
                        className="ticker-input",
                        debounce=True,
                    ),
                    dbc.Button("+", id="add-ticker-btn", color="primary", className="add-btn"),
                ],
                className="mb-2",
            ),
            html.Div(id="watchlist-items"),
            html.Hr(className="sidebar-divider"),
            # ── COMPARAR ─────────────────────────────────────
            html.H5("COMPARAR", className="sidebar-title"),
            dbc.InputGroup(
                [
                    dbc.Input(
                        id="compare-input",
                        placeholder="Ex: VALE3.SA, ^BVSP",
                        type="text",
                        className="ticker-input",
                        debounce=True,
                    ),
                    dbc.Button("+", id="add-compare-btn", color="success", className="add-btn"),
                ],
                className="mb-2",
            ),
            html.Div(id="compare-items"),
        ],
        width=2,
        className="sidebar",
    )

    controls_row = dbc.Row(
        [
            dbc.Col(
                dbc.ButtonGroup(
                    [
                        dbc.Button(
                            p,
                            id={"type": "period-btn", "index": p},
                            size="sm",
                            outline=True,
                            color="secondary",
                        )
                        for p in PERIOD_BUTTONS
                    ],
                    className="period-buttons",
                ),
                width="auto",
            ),
            dbc.Col(
                dcc.DatePickerRange(
                    id="date-picker",
                    min_date_allowed="2000-01-01",
                    display_format="DD/MM/YYYY",
                    className="date-picker",
                ),
                width="auto",
            ),
            dbc.Col(
                dbc.RadioItems(
                    id="interval-selector",
                    options=INTERVAL_OPTIONS,
                    value="1d",
                    inline=True,
                    className="interval-radio",
                ),
                width="auto",
            ),
            dbc.Col(
                dbc.RadioItems(
                    id="chart-type-selector",
                    options=CHART_TYPE_OPTIONS,
                    value="candle",
                    inline=True,
                    className="interval-radio",
                ),
                width="auto",
            ),
            dbc.Col(
                dbc.Checklist(
                    id="ma-toggle",
                    options=[
                        {"label": "MA20", "value": "MA20"},
                        {"label": "MA50", "value": "MA50"},
                        {"label": "MA200", "value": "MA200"},
                    ],
                    value=["MA20", "MA50"],
                    inline=True,
                    className="ma-toggle",
                ),
                width="auto",
            ),
            dbc.Col(
                dbc.Checklist(
                    id="rsi-toggle",
                    options=[{"label": "RSI", "value": "rsi"}],
                    value=[],
                    inline=True,
                    className="ma-toggle",
                ),
                width="auto",
            ),
        ],
        className="controls-row g-2 align-items-center mb-2",
    )

    main_area = dbc.Col(
        [
            # ── Asset header bar ─────────────────────────────
            html.Div(id="asset-header", className="asset-header mb-2"),
            # ── Controls ─────────────────────────────────────
            controls_row,
            # ── Summary stat cards ───────────────────────────
            html.Div(id="summary-stats", className="summary-row mb-2"),
            # ── Main chart ───────────────────────────────────
            dcc.Loading(
                dcc.Graph(
                    id="candlestick-chart",
                    className="main-chart",
                    config={"displayModeBar": True},
                ),
                color="#2563eb",
            ),
            # ── RSI chart ────────────────────────────────────
            dcc.Loading(
                dcc.Graph(
                    id="rsi-chart",
                    className="rsi-chart",
                    config={"displayModeBar": False},
                ),
                color="#2563eb",
            ),
            # ── Comparison chart ─────────────────────────────
            html.Div(
                [
                    html.H6(
                        "Comparação — Preço de Fechamento Normalizado (base 100)",
                        className="section-title mt-3 mb-1",
                    ),
                    dcc.Loading(
                        dcc.Graph(
                            id="comparison-chart",
                            className="sub-chart",
                            config={"displayModeBar": True},
                        ),
                        color="#2563eb",
                    ),
                ],
                id="comparison-section",
                style={"display": "none"},
            ),
            # ── Cumulative performance ────────────────────────
            html.Div(
                [
                    html.H6(
                        "Performance Acumulada desde 2000 (%)",
                        className="section-title mt-3 mb-1",
                    ),
                    dcc.Loading(
                        dcc.Graph(
                            id="cumulative-chart",
                            className="sub-chart",
                            config={"displayModeBar": True},
                        ),
                        color="#2563eb",
                    ),
                ],
                id="cumulative-section",
                style={"display": "none"},
            ),
            # ── Monthly volume ────────────────────────────────
            html.Div(
                [
                    html.H6(
                        "Volume Negociado Mensal",
                        className="section-title mt-3 mb-1",
                    ),
                    dcc.Loading(
                        dcc.Graph(
                            id="monthly-volume-chart",
                            className="sub-chart",
                            config={"displayModeBar": True},
                        ),
                        color="#2563eb",
                    ),
                ],
                id="monthly-volume-section",
                style={"display": "none"},
            ),
        ],
        width=10,
        className="main-area",
    )

    return dbc.Container(
        [
            # ── App header ────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    dbc.Row(
                        [
                            dbc.Col(
                                html.H2("Financial Dashboard", className="app-title"),
                                width=True,
                            ),
                            dbc.Col(
                                dbc.Button(
                                    "🌙 Tema Escuro",
                                    id="theme-toggle",
                                    size="sm",
                                    color="outline-secondary",
                                    className="theme-btn",
                                    n_clicks=0,
                                ),
                                width="auto",
                                className="d-flex align-items-center",
                            ),
                        ],
                        align="center",
                    ),
                    width=12,
                ),
                className="header-row",
            ),
            dbc.Row([sidebar, main_area], className="g-0 flex-nowrap"),
            # ── Stores ───────────────────────────────────────
            dcc.Store(id="watchlist-store", data=[]),
            dcc.Store(id="compare-store", data=[]),
            dcc.Store(id="active-ticker-store", data=None),
            dcc.Store(id="active-period-store", data="6M"),
            dcc.Store(id="theme-store", data="light"),
            dcc.Interval(id="benchmark-refresh", interval=60_000, n_intervals=0),
        ],
        fluid=True,
        # Default: light theme
        className="app-container light-theme",
        id="app-container",
    )
