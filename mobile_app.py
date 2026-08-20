import os
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st

# --- CONFIGURAZIONE MOBILE-FIRST ---
st.set_page_config(
    page_title="Apex Mobile Terminal",
    layout="centered",
    page_icon="🛡️",
    initial_sidebar_state="collapsed"
)

# --- CSS MOBILE ---
st.markdown("""
<style>
    .stApp { background-color: #0b0e14; color: #e0e6ed; }
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
    }
    div[data-testid="stMetricValue"] { color: #00d2ff !important; font-size: 1.3rem !important; }
    div[data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
    .stButton>button {
        width: 100%;
        background-color: #00d2ff;
        color: #0b0e14;
        font-weight: bold;
        border-radius: 8px;
        padding: 0.6rem;
    }
</style>
""", unsafe_allow_html=True)

# --- NOTIFICHE NTFY & TELEGRAM ---
NTFY_TOPIC = "apex_signals_gullo"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_push_notification(title: str, message: str, priority: str = "high"):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": priority, "Tags": "warning,chart_with_upwards_trend"},
            timeout=3
        )
    except Exception:
        pass

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": f"*{title}*\n{message}", "parse_mode": "Markdown"},
                timeout=3
            )
        except Exception:
            pass

# --- LISTA ASSET BINANCE (SPOT / PERP) ---
ASSETS = [
    {"name": "BTC/USDT", "symbol": "BTCUSDT", "is_futures": False},
    {"name": "ETH/USDT", "symbol": "ETHUSDT", "is_futures": False},
    {"name": "SOL/USDT", "symbol": "SOLUSDT", "is_futures": False},
    {"name": "TAO/USDT", "symbol": "TAOUSDT", "is_futures": False},
    {"name": "ONDO/USDT", "symbol": "ONDOUSDT", "is_futures": False},
    {"name": "HYPE/USDT", "symbol": "HYPEUSDT", "is_futures": True},
    {"name": "WLD/USDT", "symbol": "WLDUSDT", "is_futures": False},
    {"name": "ZEC/USDT", "symbol": "ZECUSDT", "is_futures": False}
]

# --- CALCOLO INDICATORI QUANTITATIVI REALI ---
def compute_technical_indicators(df: pd.DataFrame):
    closes = df["close"]
    highs = df["high"]
    lows = df["low"]

    # 1. RSI Reale (14 periodi con Wilder's Smoothing)
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    current_rsi = round(float(rsi.iloc[-1]), 1) if not pd.isna(rsi.iloc[-1]) else 50.0

    # 2. Bollinger Bands (20, 2.0)
    sma20 = closes.rolling(20).mean()
    std20 = closes.rolling(20).std()
    bb_upper = sma20 + (2.0 * std20)
    bb_lower = sma20 - (2.0 * std20)

    # 3. Keltner Channels (20, 1.5 ATR)
    tr1 = highs - lows
    tr2 = (highs - closes.shift(1)).abs()
    tr3 = (lows - closes.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr20 = tr.rolling(20).mean()
    kc_upper = sma20 + (1.5 * atr20)
    kc_lower = sma20 - (1.5 * atr20)

    # 4. John Carter Squeeze Check (BB dentro KC)
    squeeze_on = bool(bb_lower.iloc[-1] > kc_lower.iloc[-1] and bb_upper.iloc[-1] < kc_upper.iloc[-1])

    # 5. Trend EMA
    ema7 = closes.ewm(span=7, adjust=False).mean().iloc[-1]
    ema25 = closes.ewm(span=25, adjust=False).mean().iloc[-1]
    trend_bullish = ema7 > ema25

    return current_rsi, squeeze_on, trend_bullish

@st.cache_data(ttl=15)
def fetch_real_quant_matrix():
    matrix = []
    
    for item in ASSETS:
        symbol = item["symbol"]
        base_url = "https://fapi.binance.com/fapi/v1" if item["is_futures"] else "https://api.binance.com/api/v3"
        
        try:
            # Candele 1H reali (ultime 60 ore)
            kline_res = requests.get(f"{base_url}/klines?symbol={symbol}&interval=1h&limit=60", timeout=3).json()
            if not isinstance(kline_res, list) or len(kline_res) < 30:
                continue

            df_k = pd.DataFrame(kline_res, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "q_vol", "trades", "tb_base", "tb_quote", "ignore"
            ])
            df_k["high"] = df_k["high"].astype(float)
            df_k["low"] = df_k["low"].astype(float)
            df_k["close"] = df_k["close"].astype(float)
            df_k["volume"] = df_k["volume"].astype(float)

            curr_price = df_k["close"].iloc[-1]
            prev_24h_close = df_k["close"].iloc[-24] if len(df_k) >= 25 else df_k["close"].iloc[0]
            pct_change_24h = ((curr_price - prev_24h_close) / prev_24h_close) * 100

            rsi, squeeze, trend_bull = compute_technical_indicators(df_k)

            # Algoritmo Score Quantitativo
            score = 50
            if rsi < 35: score += 20      # Ipervenduto
            elif rsi > 65: score -= 18    # Ipercomprato
            if trend_bull: score += 12    # Trend EMA a favore
            else: score -= 12
            if squeeze: score += 10       # Compressione pronta all'esplosione
            
            score = max(5, min(95, score))
            bias = "BULLISH" if score >= 50 else "BEARISH"

            if score >= 70 and squeeze:
                action = "🔥 ULTRA LONG"
            elif score >= 58:
                action = "🟢 LONG"
            elif score <= 32 and squeeze:
                action = "🚨 ULTRA SHORT"
            elif score <= 42:
                action = "🔴 SHORT"
            else:
                action = "💤 WAIT"

            # Formattazione prezzo
            fmt_price = f"${curr_price:,.2f}" if curr_price >= 1 else f"${curr_price:.4f}"

            matrix.append({
                "Asset": item["name"],
                "symbol": symbol,
                "Price": fmt_price,
                "raw_price": curr_price,
                "24h %": f"{pct_change_24h:+.2f}%",
                "Squeeze": "⚡ SI" if squeeze else "NO",
                "Bias": f"🟢 {bias}" if bias == "BULLISH" else f"🔴 {bias}",
                "RSI": rsi,
                "Score": score,
                "Action": action,
                "df_k": df_k
            })

        except Exception:
            continue

    return matrix

# --- ESECUZIONE FETCH ---
st.markdown("### 🛡️ Institutional Apex Quant")
st.caption("⚡ Motore Algoritmico Live Feed | Dati OHLCV Reali")

matrix_data = fetch_real_quant_matrix()
df_display = pd.DataFrame(matrix_data)

if not df_display.empty:
    # --- 1. GLOBAL MARKET SENTIMENT (GAUGE) ---
    st.markdown("#### 🌐 Sentiment Quantitativo Globale")
    avg_score = int(df_display["Score"].mean())
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=avg_score,
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "#00d2ff"},
            'steps': [
                {'range': [0, 35], 'color': "#ff1744"},
                {'range': [35, 65], 'color': "#ffb300"},
                {'range': [65, 100], 'color': "#00e676"}
            ]
        }
    ))
    fig_gauge.update_layout(height=180, margin=dict(l=5, r=5, t=5, b=5), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
    st.plotly_chart(fig_gauge, use_container_width=True)

    # --- 2. CONFLUENCE TABLE MOBILE ---
    st.markdown("#### 📊 Segnali & Confluenza di Mercato")
    st.dataframe(
        df_display[["Asset", "Price", "24h %", "RSI", "Squeeze", "Score", "Action"]],
        use_container_width=True,
        hide_index=True
    )

    # --- 3. ANALISI TECNICA STRUTTURALE ---
    st.markdown("---")
    st.markdown("#### 📈 Struttura Prezzo & Bande Reali")
    
    selected_name = st.selectbox("Seleziona Asset", [a["Asset"] for a in matrix_data], index=0)
    selected_row = next(item for item in matrix_data if item["Asset"] == selected_name)
    df_chart = selected_row["df_k"].tail(30)

    fig_candlestick = go.Figure()
    fig_candlestick.add_trace(go.Candlestick(
        x=np.arange(len(df_chart)),
        open=df_chart["open"],
        high=df_chart["high"],
        low=df_chart["low"],
        close=df_chart["close"],
        name="OHLC"
    ))
    fig_candlestick.update_layout(
        height=260,
        margin=dict(l=5, r=5, t=5, b=5),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_rangeslider_visible=False,
        font={'color': "white"}
    )
    st.plotly_chart(fig_candlestick, use_container_width=True)

    # --- 4. DERIVATI & FUNDING RATE REALI ---
    st.markdown("---")
    st.markdown("#### ⚡ Posizionamento Derivati (Futures)")
    try:
        btc_funding = requests.get("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT", timeout=2).json()
        f_rate = float(btc_funding.get("lastFundingRate", 0)) * 100
        mark_price = float(btc_funding.get("markPrice", 0))
    except Exception:
        f_rate = 0.01
        mark_price = selected_row["raw_price"]

    m1, m2 = st.columns(2)
    with m1:
        st.metric(label="BTC Funding Rate", value=f"{f_rate:+.4f}%", delta="Basso" if abs(f_rate) < 0.015 else "Surriscaldato")
    with m2:
        st.metric(label=f"Mark Price {selected_name.split('/')[0]}", value=f"${mark_price:,.2f}" if mark_price > 1 else f"${mark_price:.4f}")

    # --- 5. NOTIFICHE PUSH DISPATCH ---
    st.markdown("---")
    if st.button("📲 Invia Notifiche Push"):
        alert_rows = df_display[df_display["Action"].str.contains("LONG|SHORT", regex=True)]
        if not alert_rows.empty:
            for _, r in alert_rows.iterrows():
                send_push_notification(
                    title=f"🚨 {r['Asset']} — {r['Action']}",
                    message=f"Prezzo: {r['Price']} ({r['24h %']}) | RSI: {r['RSI']} | Squeeze: {r['Squeeze']}"
                )
            st.success("🔔 Notifiche inviate con successo!")
        else:
            st.info("Nessuna anomalia quantitativa rilevata al momento.")
else:
    st.warning("Caricamento dati di mercato in corso...")
