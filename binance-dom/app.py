"""Binance DOM Interpreter — Streamlit app.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import dom_analysis as da
from binance_client import BASE_URLS, DEPTH_LIMITS, BinanceAPIError, BinanceClient

QUOTE_ASSETS = ["USDT", "FDUSD", "USDC", "TUSD", "BTC", "ETH", "BNB", "EUR", "TRY"]
POPULAR = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]

st.set_page_config(page_title="Binance DOM Interpreter", page_icon="📖", layout="wide")


@st.cache_resource
def get_client(base_url: str) -> BinanceClient:
    return BinanceClient(base_url)


@st.cache_data(ttl=300, show_spinner=False)
def load_symbols(base_url: str, quote_assets: tuple[str, ...]) -> list[str]:
    return get_client(base_url).get_symbols(quote_assets)


@st.cache_data(ttl=60, show_spinner=False)
def load_volume_rank(base_url: str, quote_assets: tuple[str, ...]) -> dict[str, float]:
    tickers = get_client(base_url).get_24h_tickers(quote_assets)
    return {t["symbol"]: float(t["quoteVolume"]) for t in tickers}


def ladder_frame(levels, n: int, reverse: bool) -> pd.DataFrame:
    df = da.to_frame(levels).head(n)
    df["cum_quote"] = df["quote"].cumsum()
    df = df[["price", "qty", "quote", "cum_quote"]]
    df.columns = ["Price", "Qty", "Size (quote)", "Cumulative (quote)"]
    return df.iloc[::-1] if reverse else df


def main() -> None:
    st.title("📖 Binance DOM Interpreter")
    st.caption("Live depth-of-market (order book) analytics from Binance public market data.")

    with st.sidebar:
        st.header("Data source")
        base_label = st.selectbox("API endpoint", list(BASE_URLS), index=0)
        base_url = BASE_URLS[base_label]
        quote_assets = tuple(
            st.multiselect("Quote assets", QUOTE_ASSETS, default=["USDT"])
        ) or ("USDT",)

        st.header("Ticker")
        try:
            symbols = load_symbols(base_url, quote_assets)
        except BinanceAPIError as e:
            st.error(f"Could not load symbols: {e}")
            st.stop()
        volume = load_volume_rank(base_url, quote_assets)
        symbols = sorted(symbols, key=lambda s: volume.get(s, 0.0), reverse=True)
        default_idx = next(
            (i for i, s in enumerate(symbols) if s == "BTCUSDT"),
            next((i for i, s in enumerate(symbols) if s in POPULAR), 0),
        )
        symbol = st.selectbox(
            "Symbol (sorted by 24h quote volume)", symbols, index=default_idx
        )
        limit = st.selectbox("Book depth (levels)", DEPTH_LIMITS, index=4)

        st.header("Analysis")
        wall_mult = st.slider("Wall threshold (× median level)", 2.0, 20.0, 5.0, 0.5)
        order_size = st.number_input(
            "Hypothetical market order size (quote)", min_value=100.0,
            value=50_000.0, step=10_000.0, format="%.0f",
        )
        ladder_rows = st.slider("Ladder rows shown", 5, 40, 15)

        st.header("Live updates")
        auto = st.toggle("Auto-refresh", value=False)
        interval = st.slider("Interval (s)", 2, 60, 5, disabled=not auto)
        if st.button("🔄 Refresh now", use_container_width=True):
            st.rerun()

    if auto:
        st_autorefresh(interval=interval * 1000, key="dom-refresh")

    client = get_client(base_url)
    try:
        book = client.get_order_book(symbol, limit)
        last_price = client.get_price(symbol)
    except BinanceAPIError as e:
        st.error(str(e))
        st.stop()

    m = da.spread_metrics(book)
    band1 = da.depth_within_pct(book, 1.0)
    top10 = da.top_n_imbalance(book, 10)

    st.subheader(f"{symbol} — order book snapshot")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Last price", f"{last_price:,.6g}")
    c2.metric("Mid price", f"{m['mid']:,.6g}")
    c3.metric("Spread", f"{m['spread_bps']:.2f} bps")
    c4.metric("Imbalance ±1%", f"{band1['imbalance']:+.2f}")
    c5.metric("Top-10 imbalance", f"{top10:+.2f}")

    st.markdown("### Interpretation")
    for line in da.interpret(book, wall_mult):
        st.markdown(f"- {line}")

    st.markdown("### Depth chart")
    depth = da.cumulative_depth(book)
    fig = go.Figure()
    for side, color in (("Bids", "#26a69a"), ("Asks", "#ef5350")):
        d = depth[depth["side"] == side]
        fig.add_trace(go.Scatter(
            x=d["pct_from_mid"], y=d["cum_quote"], name=side,
            fill="tozeroy", line=dict(color=color, width=2),
            hovertemplate="%{x:.2f}% from mid<br>$%{y:,.0f} cumulative<extra>%{fullData.name}</extra>",
        ))
    fig.update_layout(
        xaxis_title="Distance from mid price (%)",
        yaxis_title="Cumulative depth (quote currency)",
        height=380, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Order book ladder")
    bid_col, ask_col = st.columns(2)
    with bid_col:
        st.markdown("**Bids** 🟢")
        st.dataframe(
            ladder_frame(book.bids, ladder_rows, reverse=True).style.format(
                {"Price": "{:,.6g}", "Qty": "{:,.4f}",
                 "Size (quote)": "{:,.0f}", "Cumulative (quote)": "{:,.0f}"}
            ).bar(subset=["Size (quote)"], color="#26a69a"),
            use_container_width=True, height=420,
        )
    with ask_col:
        st.markdown("**Asks** 🔴")
        st.dataframe(
            ladder_frame(book.asks, ladder_rows, reverse=False).style.format(
                {"Price": "{:,.6g}", "Qty": "{:,.4f}",
                 "Size (quote)": "{:,.0f}", "Cumulative (quote)": "{:,.0f}"}
            ).bar(subset=["Size (quote)"], color="#ef5350"),
            use_container_width=True, height=420,
        )

    st.markdown("### Walls & market impact")
    w1, w2, w3 = st.columns(3)
    with w1:
        st.markdown("**Bid walls** (potential support)")
        bw = da.detect_walls(book.bids, wall_mult)
        st.dataframe(bw.style.format({"price": "{:,.6g}", "qty": "{:,.4f}",
                                      "quote": "{:,.0f}", "size_vs_median": "{:.1f}×"}),
                     use_container_width=True) if not bw.empty else st.info("None detected.")
    with w2:
        st.markdown("**Ask walls** (potential resistance)")
        aw = da.detect_walls(book.asks, wall_mult)
        st.dataframe(aw.style.format({"price": "{:,.6g}", "qty": "{:,.4f}",
                                      "quote": "{:,.0f}", "size_vs_median": "{:.1f}×"}),
                     use_container_width=True) if not aw.empty else st.info("None detected.")
    with w3:
        st.markdown(f"**Market order impact** (${order_size:,.0f})")
        buy = da.estimate_market_order(book.asks, order_size)
        sell = da.estimate_market_order(book.bids, order_size)
        impact = pd.DataFrame([
            {"Side": "Market BUY", "VWAP": buy["vwap"], "Slippage (bps)": buy["slippage_bps"],
             "Filled": f"{buy['fill_pct']:.1f}%"},
            {"Side": "Market SELL", "VWAP": sell["vwap"], "Slippage (bps)": sell["slippage_bps"],
             "Filled": f"{sell['fill_pct']:.1f}%"},
        ])
        st.dataframe(impact.style.format({"VWAP": "{:,.6g}", "Slippage (bps)": "{:.2f}"}),
                     use_container_width=True, hide_index=True)

    with st.expander("Raw order book data"):
        st.json({
            "symbol": book.symbol,
            "lastUpdateId": book.last_update_id,
            "bids": book.bids[:ladder_rows],
            "asks": book.asks[:ladder_rows],
        })


if __name__ == "__main__":
    main()
