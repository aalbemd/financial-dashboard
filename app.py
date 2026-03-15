import json

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, ALL, callback_context, no_update, html, dcc
from flask_caching import Cache

from data import (
    get_stock_data,
    get_benchmarks,
    compute_moving_averages,
    compute_rsi,
    compute_cumulative_performance,
    compute_monthly_volume,
    period_to_dates,
    DEFAULT_START,
)
from layout import build_layout, benchmark_card

import plotly.graph_objects as go
import pandas as pd
from datetime import date

# ---------------------------------------------------------------------------
# App init
# ---------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Financial Dashboard",
)
server = app.server

cache = Cache(server, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300})

app.layout = build_layout()


# ---------------------------------------------------------------------------
# Theme helpers
# ---------------------------------------------------------------------------
POS_COLOR = "#0fa958"
NEG_COLOR = "#e84040"
ACCENT    = "#2563eb"


def chart_layout(dark: bool = False, height: int = 500) -> dict:
    if dark:
        bg = "#0d1117"
        fc = "#e6edf3"
        gc = "#21262d"
        lb = "rgba(0,0,0,0)"
    else:
        bg = "#ffffff"
        fc = "#1f2937"
        gc = "#e5e7eb"
        lb = "rgba(255,255,255,0.9)"
    return dict(
        height=height,
        paper_bgcolor=bg,
        plot_bgcolor=bg,
        font=dict(color=fc, family="Inter, sans-serif"),
        xaxis=dict(gridcolor=gc, showgrid=True, rangeslider_visible=False),
        yaxis=dict(gridcolor=gc, showgrid=True),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(bgcolor=lb, font=dict(color=fc)),
    )


def make_empty_figure(message: str = "Selecione um ativo para visualizar", dark: bool = False) -> go.Figure:
    fc = "#8b949e" if dark else "#9ca3af"
    fig = go.Figure()
    fig.add_annotation(
        text=message, x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font=dict(size=15, color=fc),
    )
    fig.update_layout(**chart_layout(dark))
    return fig


def build_main_trace(df: pd.DataFrame, ticker: str, chart_type: str, dark: bool) -> go.BaseTraceType:
    up_c = POS_COLOR
    dn_c = NEG_COLOR
    line_c = ACCENT if not dark else "#00d4aa"

    if chart_type == "ohlc":
        return go.Ohlc(
            x=df.index,
            open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name=ticker,
            increasing_line_color=up_c,
            decreasing_line_color=dn_c,
        )
    elif chart_type == "line":
        return go.Scatter(
            x=df.index, y=df["Close"],
            mode="lines", name=ticker,
            line=dict(color=line_c, width=2),
        )
    elif chart_type == "area":
        return go.Scatter(
            x=df.index, y=df["Close"],
            mode="lines", name=ticker,
            fill="tozeroy",
            line=dict(color=line_c, width=2),
            fillcolor=f"rgba(37,99,235,0.08)" if not dark else "rgba(0,212,170,0.08)",
        )
    else:  # candle (default)
        return go.Candlestick(
            x=df.index,
            open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name=ticker,
            increasing_line_color=up_c,
            decreasing_line_color=dn_c,
        )


def build_asset_header(df: pd.DataFrame, ticker: str, dark: bool) -> html.Div:
    """Large price + variation bar shown above the chart."""
    if df.empty:
        return html.Div()
    last = df["Close"].iloc[-1]
    prev = df["Close"].iloc[-2] if len(df) > 1 else last
    chg = last - prev
    chg_pct = (chg / prev) * 100 if prev != 0 else 0
    arrow = "▲" if chg >= 0 else "▼"
    var_color = POS_COLOR if chg >= 0 else NEG_COLOR

    return html.Div(
        [
            html.Span(ticker, className="ah-ticker"),
            html.Span(f"{last:,.2f}", className="ah-price"),
            html.Span(
                f"{arrow} {chg:+.2f}  ({chg_pct:+.2f}%)",
                className="ah-change",
                style={"color": var_color},
            ),
        ],
        className="asset-header-bar",
    )


def build_summary_stats(df: pd.DataFrame, ticker: str) -> html.Div:
    if df.empty:
        return html.Div()
    close = df["Close"]
    last  = close.iloc[-1]
    first = close.iloc[0]
    high  = df["High"].max() if "High" in df.columns else close.max()
    low   = df["Low"].min()  if "Low"  in df.columns else close.min()
    vol   = df["Volume"].iloc[-1] if "Volume" in df.columns else None
    variation = (last - first) / first * 100 if first != 0 else 0

    var_cls = "stat-value stat-pos" if variation >= 0 else "stat-value stat-neg"

    def vol_fmt(v):
        if v is None: return "—"
        if v >= 1_000_000_000: return f"{v/1_000_000_000:.1f}B"
        if v >= 1_000_000:     return f"{v/1_000_000:.1f}M"
        return f"{v:,.0f}"

    stats = [
        ("Ativo",          ticker,               "stat-value stat-ticker"),
        ("Preço Atual",    f"{last:,.2f}",        "stat-value"),
        ("Máxima Período", f"{high:,.2f}",        "stat-value"),
        ("Mínima Período", f"{low:,.2f}",         "stat-value"),
        ("Volume Diário",  vol_fmt(vol),          "stat-value"),
        ("Variação Total", f"{variation:+.2f}%",  var_cls),
    ]

    cards = [
        dbc.Col(
            html.Div(
                [html.P(label, className="stat-label"), html.P(value, className=cls)],
                className="stat-card",
            ),
            width="auto",
        )
        for label, value, cls in stats
    ]
    return dbc.Row(cards, className="g-2")


# ---------------------------------------------------------------------------
# Theme toggle
# ---------------------------------------------------------------------------
@app.callback(
    Output("theme-store", "data"),
    Output("app-container", "className"),
    Output("theme-toggle", "children"),
    Input("theme-toggle", "n_clicks"),
    State("theme-store", "data"),
    prevent_initial_call=True,
)
def toggle_theme(n_clicks, current_theme):
    if current_theme == "light":
        return "dark", "app-container dark-theme", "☀ Tema Claro"
    return "light", "app-container light-theme", "🌙 Tema Escuro"


# ---------------------------------------------------------------------------
# Benchmark cards
# ---------------------------------------------------------------------------
@app.callback(
    Output("benchmark-cards", "children"),
    Input("benchmark-refresh", "n_intervals"),
)
def refresh_benchmarks(_):
    data = get_benchmarks()
    return [
        benchmark_card(name, info["ticker"], info["price"], info["change_pct"])
        for name, info in data.items()
    ]


# ---------------------------------------------------------------------------
# Watchlist management
# ---------------------------------------------------------------------------
@app.callback(
    Output("watchlist-store", "data"),
    Input("add-ticker-btn", "n_clicks"),
    Input({"type": "remove-btn", "index": ALL}, "n_clicks"),
    State("ticker-input", "value"),
    State("watchlist-store", "data"),
    prevent_initial_call=True,
)
def manage_watchlist(add_clicks, remove_clicks, ticker_value, watchlist):
    ctx = callback_context
    if not ctx.triggered:
        return no_update

    prop_id = ctx.triggered[0]["prop_id"]

    if "add-ticker-btn" in prop_id:
        if ticker_value and ticker_value.strip():
            symbol = ticker_value.strip().upper()
            if symbol not in watchlist:
                watchlist = watchlist + [symbol]
        return watchlist

    if "remove-btn" in prop_id:
        idx = json.loads(prop_id.split(".")[0])["index"]
        watchlist = [t for t in watchlist if t != idx]

    return watchlist


@app.callback(
    Output("watchlist-items", "children"),
    Input("watchlist-store", "data"),
    State("active-ticker-store", "data"),  # State = não re-renderiza ao selecionar ticker
)
def render_watchlist(watchlist, active_ticker):
    if not watchlist:
        return html.P("Nenhum ativo adicionado", className="empty-watchlist")
    items = []
    for ticker in watchlist:
        is_active = ticker == active_ticker
        items.append(
            html.Div(
                dbc.Row(
                    [
                        dbc.Col(
                            # ── FIX: usar dbc.Button para clique confiável ──
                            dbc.Button(
                                ticker,
                                id={"type": "watchlist-item", "index": ticker},
                                color="link",
                                size="sm",
                                className="watchlist-ticker-btn-active" if is_active else "watchlist-ticker-btn",
                                n_clicks=0,
                            ),
                            width=8,
                        ),
                        dbc.Col(
                            dbc.Button(
                                "×",
                                id={"type": "remove-btn", "index": ticker},
                                size="sm",
                                color="danger",
                                outline=True,
                                className="remove-btn",
                            ),
                            width=4,
                            className="text-end",
                        ),
                    ],
                    align="center",
                ),
                className="watchlist-card mb-1 p-1" + (" watchlist-card-active" if is_active else ""),
            )
        )
    return items


# ---------------------------------------------------------------------------
# Compare list management
# ---------------------------------------------------------------------------
@app.callback(
    Output("compare-store", "data"),
    Input("add-compare-btn", "n_clicks"),
    Input({"type": "compare-remove-btn", "index": ALL}, "n_clicks"),
    State("compare-input", "value"),
    State("compare-store", "data"),
    prevent_initial_call=True,
)
def manage_compare_list(add_clicks, remove_clicks, ticker_value, compare_list):
    ctx = callback_context
    if not ctx.triggered:
        return no_update

    prop_id = ctx.triggered[0]["prop_id"]

    if "add-compare-btn" in prop_id:
        if ticker_value and ticker_value.strip():
            symbol = ticker_value.strip().upper()
            if symbol not in compare_list:
                compare_list = compare_list + [symbol]
        return compare_list

    if "compare-remove-btn" in prop_id:
        idx = json.loads(prop_id.split(".")[0])["index"]
        compare_list = [t for t in compare_list if t != idx]

    return compare_list


@app.callback(
    Output("compare-items", "children"),
    Input("compare-store", "data"),
)
def render_compare_list(compare_list):
    if not compare_list:
        return html.P("Nenhum ticker adicionado", className="empty-watchlist")
    items = []
    for ticker in compare_list:
        items.append(
            html.Div(
                dbc.Row(
                    [
                        dbc.Col(
                            html.Span(ticker, className="watchlist-ticker"),
                            width=8,
                        ),
                        dbc.Col(
                            dbc.Button(
                                "×",
                                id={"type": "compare-remove-btn", "index": ticker},
                                size="sm",
                                color="danger",
                                outline=True,
                                className="remove-btn",
                            ),
                            width=4,
                            className="text-end",
                        ),
                    ],
                    align="center",
                ),
                className="watchlist-card mb-1 p-1",
            )
        )
    return items


# ---------------------------------------------------------------------------
# Active ticker selection (watchlist button or benchmark card click)
# ---------------------------------------------------------------------------
@app.callback(
    Output("active-ticker-store", "data"),
    Input({"type": "watchlist-item", "index": ALL}, "n_clicks"),
    Input({"type": "benchmark-card", "index": ALL}, "n_clicks"),
    State({"type": "watchlist-item", "index": ALL}, "id"),
    State({"type": "benchmark-card", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def select_active_ticker(watchlist_clicks, benchmark_clicks, watchlist_ids, benchmark_ids):
    ctx = callback_context
    if not ctx.triggered:
        return no_update

    triggered = ctx.triggered[0]

    try:
        id_obj = json.loads(triggered["prop_id"].split(".")[0])
    except Exception:
        return no_update

    # Benchmark cards re-renderizam a cada 60s com n_clicks=0 — ignorar esses eventos.
    # Watchlist items: sempre processar (value pode ser None em dbc.Button dinâmico).
    if id_obj.get("type") == "benchmark-card" and not triggered["value"]:
        return no_update

    return id_obj["index"]


# ---------------------------------------------------------------------------
# Period store update
# ---------------------------------------------------------------------------
@app.callback(
    Output("active-period-store", "data"),
    Input({"type": "period-btn", "index": ALL}, "n_clicks"),
    State({"type": "period-btn", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def update_period(clicks, ids):
    ctx = callback_context
    if not ctx.triggered:
        return no_update
    id_obj = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])
    return id_obj["index"]


# ---------------------------------------------------------------------------
# Main chart + RSI + asset header + summary stats
# ---------------------------------------------------------------------------
@app.callback(
    Output("candlestick-chart", "figure"),
    Output("rsi-chart", "figure"),
    Output("rsi-chart", "style"),
    Output("asset-header", "children"),
    Output("summary-stats", "children"),
    Input("active-ticker-store", "data"),
    Input("active-period-store", "data"),
    Input("date-picker", "start_date"),
    Input("date-picker", "end_date"),
    Input("interval-selector", "value"),
    Input("ma-toggle", "value"),
    Input("rsi-toggle", "value"),
    Input("chart-type-selector", "value"),
    Input("theme-store", "data"),
)
def update_chart(ticker, period, date_start, date_end, interval, ma_values, rsi_values, chart_type, theme):
    dark = theme == "dark"

    if not ticker:
        empty = make_empty_figure(dark=dark)
        return empty, make_empty_figure("", dark), {"display": "none"}, html.Div(), html.Div()

    start, end = (date_start, date_end) if (date_start and date_end) else period_to_dates(period or "6M")
    df = get_stock_data(ticker, start, end, interval or "1d")

    if df.empty:
        msg = f"Sem dados para {ticker}"
        return make_empty_figure(msg, dark), make_empty_figure("", dark), {"display": "none"}, html.Div(), html.Div()

    df = compute_moving_averages(df)
    rsi_series = compute_rsi(df) if rsi_values else None

    # --- Main chart ---
    fig = go.Figure()
    fig.add_trace(build_main_trace(df, ticker, chart_type or "candle", dark))

    ma_colors = {"MA20": "#f59e0b", "MA50": ACCENT, "MA200": "#8b5cf6"}
    for ma in ma_values or []:
        if ma in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index, y=df[ma],
                    mode="lines", name=ma,
                    line=dict(color=ma_colors.get(ma, "#888"), width=1.2),
                )
            )

    # Volume (secondary y-axis)
    if "Volume" in df.columns:
        vol_colors = [
            POS_COLOR if c >= o else NEG_COLOR
            for c, o in zip(df["Close"], df["Open"])
        ]
        fig.add_trace(
            go.Bar(
                x=df.index, y=df["Volume"],
                name="Volume",
                marker_color=vol_colors,
                opacity=0.30,
                yaxis="y2",
            )
        )

    gc = "#21262d" if dark else "#e5e7eb"
    lk = chart_layout(dark, height=480)
    lk.update(
        yaxis2=dict(
            overlaying="y", side="right",
            showgrid=False, showticklabels=False,
            range=[0, df["Volume"].max() * 5] if "Volume" in df.columns else [],
        ),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )
    fig.update_layout(**lk)

    # --- RSI chart ---
    rsi_fig = make_empty_figure("", dark)
    rsi_style = {"display": "none"}
    if rsi_values and rsi_series is not None and not rsi_series.empty:
        rsi_fig = go.Figure()
        rsi_fig.add_trace(
            go.Scatter(
                x=rsi_series.index, y=rsi_series,
                mode="lines", name="RSI(14)",
                line=dict(color="#f59e0b", width=1.5),
            )
        )
        rsi_fig.add_hline(y=70, line_dash="dash", line_color=NEG_COLOR, opacity=0.6)
        rsi_fig.add_hline(y=30, line_dash="dash", line_color=POS_COLOR, opacity=0.6)
        rsi_lk = chart_layout(dark, height=150)
        rsi_lk.update(
            yaxis=dict(range=[0, 100], gridcolor=gc),
            title=dict(text="RSI (14)", font=dict(size=12, color="#9ca3af"), x=0.01),
            margin=dict(l=10, r=10, t=25, b=10),
        )
        rsi_fig.update_layout(**rsi_lk)
        rsi_style = {"display": "block"}

    header  = build_asset_header(df, ticker, dark)
    summary = build_summary_stats(df, ticker)
    return fig, rsi_fig, rsi_style, header, summary


# ---------------------------------------------------------------------------
# Cumulative performance + Monthly volume
# ---------------------------------------------------------------------------
@app.callback(
    Output("cumulative-chart", "figure"),
    Output("cumulative-section", "style"),
    Output("monthly-volume-chart", "figure"),
    Output("monthly-volume-section", "style"),
    Input("active-ticker-store", "data"),
    Input("theme-store", "data"),
)
def update_extra_charts(ticker, theme):
    dark = theme == "dark"
    hidden = {"display": "none"}
    shown  = {"display": "block"}
    gc = "#21262d" if dark else "#e5e7eb"
    line_c = "#00d4aa" if dark else ACCENT

    if not ticker:
        return make_empty_figure("", dark), hidden, make_empty_figure("", dark), hidden

    today = date.today().strftime("%Y-%m-%d")

    # --- Cumulative performance from 2000 ---
    df_cum = get_stock_data(ticker, DEFAULT_START, today, "1wk")
    cum_fig   = make_empty_figure(f"Sem dados históricos para {ticker}", dark)
    cum_style = hidden

    if not df_cum.empty:
        perf = compute_cumulative_performance(df_cum)
        if not perf.empty:
            final_val = perf.iloc[-1]
            color = POS_COLOR if final_val >= 0 else NEG_COLOR
            cum_fig = go.Figure()
            cum_fig.add_trace(
                go.Scatter(
                    x=perf.index, y=perf,
                    mode="lines", name=ticker,
                    line=dict(color=color, width=1.5),
                    fill="tozeroy",
                    fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.07)",
                )
            )
            cum_fig.add_hline(y=0, line_dash="dash", line_color="#9ca3af", opacity=0.5)
            lk = chart_layout(dark, height=300)
            lk.update(yaxis=dict(gridcolor=gc, ticksuffix="%"), hovermode="x unified")
            cum_fig.update_layout(**lk)
            cum_style = shown

    # --- Monthly volume (last 3 years) ---
    three_years_ago = (pd.Timestamp(today) - pd.DateOffset(years=3)).strftime("%Y-%m-%d")
    df_vol    = get_stock_data(ticker, three_years_ago, today, "1d")
    vol_fig   = make_empty_figure(f"Sem dados de volume para {ticker}", dark)
    vol_style = hidden

    if not df_vol.empty:
        monthly = compute_monthly_volume(df_vol)
        if not monthly.empty:
            vol_fig = go.Figure()
            vol_fig.add_trace(
                go.Bar(
                    x=monthly["Date"], y=monthly["Volume"],
                    name="Volume Mensal",
                    marker_color=line_c,
                    opacity=0.8,
                )
            )
            lk = chart_layout(dark, height=260)
            lk.update(yaxis=dict(gridcolor=gc), hovermode="x unified")
            vol_fig.update_layout(**lk)
            vol_style = shown

    return cum_fig, cum_style, vol_fig, vol_style


# ---------------------------------------------------------------------------
# Comparison chart — driven by compare-store (input+button in sidebar)
# ---------------------------------------------------------------------------
@app.callback(
    Output("comparison-chart", "figure"),
    Output("comparison-section", "style"),
    Input("compare-store", "data"),
    Input("active-period-store", "data"),
    Input("date-picker", "start_date"),
    Input("date-picker", "end_date"),
    Input("theme-store", "data"),
)
def update_comparison(tickers, period, date_start, date_end, theme):
    dark = theme == "dark"
    hidden = {"display": "none"}
    gc = "#21262d" if dark else "#e5e7eb"

    if not tickers:
        return make_empty_figure("Adicione tickers na seção COMPARAR →", dark), hidden

    start, end = (date_start, date_end) if (date_start and date_end) else period_to_dates(period or "6M")

    palette = [ACCENT, "#f59e0b", POS_COLOR, "#8b5cf6", NEG_COLOR, "#06b6d4", "#ec4899", "#84cc16"]
    fig = go.Figure()

    for i, ticker in enumerate(tickers):
        df = get_stock_data(ticker, start, end, "1d")
        if df.empty or "Close" not in df.columns:
            continue
        close = df["Close"].dropna()
        if close.empty:
            continue
        normalized = (close / close.iloc[0]) * 100
        fig.add_trace(
            go.Scatter(
                x=normalized.index, y=normalized,
                mode="lines", name=ticker,
                line=dict(color=palette[i % len(palette)], width=2),
            )
        )

    if not fig.data:
        return make_empty_figure("Sem dados para os tickers selecionados", dark), hidden

    fig.add_hline(y=100, line_dash="dot", line_color="#9ca3af", opacity=0.5)
    lk = chart_layout(dark, height=340)
    lk.update(
        yaxis=dict(gridcolor=gc),
        yaxis_title="Índice (base 100)",
        hovermode="x unified",
    )
    fig.update_layout(**lk)
    return fig, {"display": "block"}


# ---------------------------------------------------------------------------
# Period button highlight
# ---------------------------------------------------------------------------
@app.callback(
    Output({"type": "period-btn", "index": ALL}, "outline"),
    Output({"type": "period-btn", "index": ALL}, "color"),
    Input("active-period-store", "data"),
    State({"type": "period-btn", "index": ALL}, "id"),
)
def highlight_period_btn(active_period, ids):
    outlines, colors = [], []
    for id_obj in ids:
        is_active = id_obj["index"] == active_period
        outlines.append(not is_active)
        colors.append("primary" if is_active else "secondary")
    return outlines, colors


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
