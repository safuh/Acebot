import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_market_figure(
    df,
    daily=None,
    symbol="BTC/USDT",
    timeframe="1h",
    lookback=5,
):
    """Build the existing price and RSI chart."""
    if df.empty:
        return go.Figure()

    required_columns = {
        "open", "high", "low", "close", "day", "day_high", "day_low", "rsi"
    }
    missing = required_columns.difference(df.columns)
    if missing:
        raise ValueError(
            f"Missing required chart columns: {sorted(missing)}"
        )

    chart = df.copy().sort_index()
    chart = chart[~chart.index.duplicated(keep="last")]
    chart = chart.dropna(subset=["open", "high", "low", "close"])
    if chart.empty:
        return go.Figure()

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.72, 0.28],
        subplot_titles=(
            "Price Action & Liquidity Structure",
            "Relative Strength Index",
        ),
    )

    fig.add_trace(
        go.Candlestick(
            x=chart.index,
            open=chart["open"],
            high=chart["high"],
            low=chart["low"],
            close=chart["close"],
            name="Price",
            increasing=dict(line=dict(color="#26a69a"), fillcolor="#26a69a"),
            decreasing=dict(line=dict(color="#ef5350"), fillcolor="#ef5350"),
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=chart.index,
            y=chart["rsi"],
            mode="lines",
            name="RSI",
            line=dict(color="#42a5f5", width=1.6),
            connectgaps=False,
        ),
        row=2,
        col=1,
    )

    for level, label, color in (
        (70, "Overbought (70)", "#ff5252"),
        (30, "Oversold (30)", "#00c853"),
    ):
        fig.add_trace(
            go.Scatter(
                x=chart.index,
                y=[level] * len(chart),
                mode="lines",
                name=label,
                line=dict(color=color, width=1, dash="dash"),
                hoverinfo="skip",
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        title=dict(
            text=f"{symbol} | {timeframe} | Market Structure",
            x=0.02,
            xanchor="left",
        ),
        template="plotly_dark",
        height=900,
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        dragmode="pan",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
        margin=dict(l=65, r=150, t=100, b=45),
        uirevision=f"{symbol}_{timeframe}",
    )
    fig.update_yaxes(title_text="Price", row=1, col=1, autorange=True)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    fig.update_xaxes(
        title_text="Time (UTC)",
        showgrid=True,
        rangeslider_visible=False,
        row=2,
        col=1,
    )
    fig.update_xaxes(showgrid=True, row=1, col=1)
    return fig


def add_divergence_traces(fig, events):
    """Plot historical hidden-divergence lines on price and RSI panels."""
    colors = {"bearish": "#ef5350", "bullish": "#26a69a"}
    legend_seen = set()

    for event in events:
        direction = event["direction"]
        if direction not in colors:
            continue

        color = colors[direction]
        invalidated = event["status"] == "invalidated"
        opacity = 0.35 if invalidated else 1.0
        dash = "dot" if invalidated else "dash"
        name = "Hidden bearish" if direction == "bearish" else "Hidden bullish"

        price_x = [
            event["reference_price_timestamp"],
            event["current_price_timestamp"],
        ]
        price_y = [event["reference_price"], event["current_price"]]
        rsi_x = [
            event["reference_rsi_timestamp"],
            event["current_rsi_timestamp"],
        ]
        rsi_y = [event["reference_rsi"], event["current_rsi"]]

        if any(pd.isna(value) for value in price_x + rsi_x):
            continue

        price_difference = event["current_price"] - event["reference_price"]
        price_difference_pct = (
            price_difference / event["reference_price"] * 100
            if event["reference_price"] != 0
            else float("nan")
        )
        difference_label = (
            f"{price_difference:+.2f} ({price_difference_pct:+.2f}%)"
        )

        hover = (
            f"<b>{name}</b><br>"
            f"Reference day: {event['reference_day']}<br>"
            f"Current day: {event['current_day']}<br>"
            f"Detected: {event['detected_at']}<br>"
            f"Status: {event['status']}<br>"
            f"Price difference: {price_difference:+.2f}<br>"
            f"Price difference (%): {price_difference_pct:+.2f}%<br>"
        )

        fig.add_trace(
            go.Scatter(
                x=price_x,
                y=price_y,
                mode="lines+markers+text",
                text=["", difference_label],
                textposition="top center",
                textfont=dict(color=color, size=10),
                name=name,
                legendgroup=direction,
                showlegend=direction not in legend_seen,
                opacity=opacity,
                line=dict(color=color, width=2, dash=dash),
                marker=dict(size=8),
                hovertemplate=hover + "Price: %{y:.2f}<extra></extra>",
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=rsi_x,
                y=rsi_y,
                mode="lines+markers",
                name=f"{name} RSI",
                legendgroup=direction,
                showlegend=False,
                opacity=opacity,
                line=dict(color=color, width=2, dash=dash),
                marker=dict(size=7),
                hovertemplate=hover + "RSI: %{y:.2f}<extra></extra>",
            ),
            row=2,
            col=1,
        )
        legend_seen.add(direction)

    return fig


def add_swing_traces(fig, snapshot):
    """
    Add confirmed swing points, BOS/CHoCH lines, and liquidity-sweep markers.

    `snapshot` is returned by SwingStructureEngine.get_snapshot().
    """
    if not snapshot:
        return fig

    swings = snapshot.get("swings", [])
    events = snapshot.get("events", [])

    high_swings = [item for item in swings if item["side"] == "high"]
    low_swings = [item for item in swings if item["side"] == "low"]

    if high_swings:
        fig.add_trace(
            go.Scatter(
                x=[item["timestamp"] for item in high_swings],
                y=[item["price"] for item in high_swings],
                mode="markers+text",
                text=[item.get("classification") or "SH" for item in high_swings],
                textposition="top center",
                name="Swing highs",
                marker=dict(symbol="triangle-down", size=10, color="#ef5350"),
                customdata=[
                    [item["confirmed_at"], item["liquidity_swept"]]
                    for item in high_swings
                ],
                hovertemplate=(
                    "Swing high: %{y:.4f}<br>"
                    "Formed: %{x}<br>"
                    "Confirmed: %{customdata[0]}<br>"
                    "Liquidity swept: %{customdata[1]}<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    if low_swings:
        fig.add_trace(
            go.Scatter(
                x=[item["timestamp"] for item in low_swings],
                y=[item["price"] for item in low_swings],
                mode="markers+text",
                text=[item.get("classification") or "SL" for item in low_swings],
                textposition="bottom center",
                name="Swing lows",
                marker=dict(symbol="triangle-up", size=10, color="#26a69a"),
                customdata=[
                    [item["confirmed_at"], item["liquidity_swept"]]
                    for item in low_swings
                ],
                hovertemplate=(
                    "Swing low: %{y:.4f}<br>"
                    "Formed: %{x}<br>"
                    "Confirmed: %{customdata[0]}<br>"
                    "Liquidity swept: %{customdata[1]}<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    structure_seen = set()
    swing_by_id = {item["swing_id"]: item for item in swings}
    for event in events:
        event_type = event.get("event_type")

        if event_type == "structure_break":
            structure_type = event["structure_type"]
            color = "#26a69a" if event["direction"] == "bullish" else "#ef5350"
            show_legend = structure_type not in structure_seen
            broken_swing = swing_by_id.get(event["swing_id"], {})
            level_timestamp = broken_swing.get("timestamp", event["timestamp"])
            fig.add_trace(
                go.Scatter(
                    x=[level_timestamp, event["timestamp"]],
                    y=[event["price"], event["price"]],
                    mode="lines+markers+text",
                    text=["", structure_type],
                    textposition="top right",
                    name=structure_type,
                    showlegend=show_legend,
                    line=dict(color=color, width=1.5, dash="dash"),
                    marker=dict(size=6, color=color),
                    hovertemplate=(
                        f"<b>{structure_type}</b><br>"
                        f"Direction: {event['direction']}<br>"
                        f"Swing level: {event['price']:.4f}<br>"
                        f"Break candle close: {event['close']:.4f}<br>"
                        f"Confirmed: {event['confirmed_at']}<extra></extra>"
                    ),
                ),
                row=1,
                col=1,
            )
            structure_seen.add(structure_type)

        elif event_type == "liquidity_sweep":
            color = "#ffca28" if event["side"] == "high" else "#ab47bc"
            label = "High sweep" if event["side"] == "high" else "Low sweep"
            fig.add_trace(
                go.Scatter(
                    x=[event["timestamp"]],
                    y=[event["candle_extreme"]],
                    mode="markers",
                    name=label,
                    showlegend=not any(
                        e.get("event_type") == "liquidity_sweep"
                        and e.get("side") == event["side"]
                        for e in events[:events.index(event)]
                    ),
                    marker=dict(symbol="diamond", size=9, color=color),
                    hovertemplate=(
                        f"<b>{label}</b><br>"
                        f"Swing level: {event['price']:.4f}<br>"
                        f"Candle extreme: {event['candle_extreme']:.4f}<br>"
                        f"Confirmed: {event['confirmed_at']}<extra></extra>"
                    ),
                ),
                row=1,
                col=1,
            )

    return fig


def build_market_figure_with_divergence(
    df,
    events,
    symbol,
    timeframe,
    daily=None,
    swings=None,
):
    """Build the market chart with divergence and optional swing overlays."""
    fig = build_market_figure(
        df,
        daily=daily,
        symbol=symbol,
        timeframe=timeframe,
    )
    fig = add_divergence_traces(fig, events)
    if swings is not None:
        fig = add_swing_traces(fig, swings)
    return fig