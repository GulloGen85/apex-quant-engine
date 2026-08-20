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

# --- LISTA ASSET GLOBALI ---
ASSETS = [
    {"name": "BTC/USD", "symbol": "BTC"},
    {"name": "ETH/USD", "symbol": "ETH"},
    {"name": "SOL/USD", "symbol": "SOL"},
    {"name": "TAO/USD", "symbol": "TAO"},
    {"name": "ONDO/USD", "symbol": "ONDO"},
    {"name": "HYPE/USD", "symbol": "HYPE"},
    {"name": "WLD/USD", "symbol": "WLD"},
    {"name": "ZEC/USD", "symbol": "ZEC"}
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

    # 4. Squeeze Check (Bollinger all'interno di Keltner)
    squeeze_on = bool(bb_lower.iloc[-1] > kc_lower.iloc[-1] and bb_upper.iloc[-1] < kc_upper.iloc[-1])

    # 5. Trend EMA (7 vs 25)
    ema7 = closes.ewm(span=7, adjust=False).mean().iloc[-1]
    ema25 = closes.ewm(span=25, adjust=False).mean().iloc[-1]
    trend_bullish = ema7 > ema25

    return current_rsi, squeeze_on, trend_bullish

@st.cache_data(ttl=30)
def fetch_real_quant_matrix():
    matrix = []
    
    for item in ASSETS:
        sym = item["symbol"]
        try:
            # Candele orarie reali da CryptoCompare (compatibile con server USA / Cloud)
            url = f"https://min-api.cryptocompare.com/data/v2/histohour?fsym={sym}&tsym=USD&limit=50"
            res = requests.get(url, timeout=4).json()
            
            data_list = res.get("Data", {}).get("Data", [])
            if not data_list or len(data_list) < 25:
                continue

            df_k = pd.DataFrame(data_list)
            df_k = df_k[["time", "open", "high", "low", "close", "volumeto"]].copy()
            df_k = df_k[df_k["close"] > 0].reset_index(drop=True)

            if len(df_k) < 20:
                continue

            curr_price = float(df_k["close"].iloc[-1])
            prev_24h_close = float(df_k["close"].iloc[-24]) if len(df_k) >= 25 else float(df_k["close"].iloc[0])
            pct_change_24h = ((curr_price - prev_24h_close) / prev_24h_close) * 100

            rsi, squeeze, trend_bull = compute_technical_indicators(df_k)

            # Scoring quantitativo
            score = 50
            if rsi < 35: score += 20
            elif rsi > 65: score -= 18
            if trend_bull: score += 12
            else: score -= 12
            if squeeze: score += 10
            
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

            fmt_price = f"${curr_price:,.2f}" if curr_price >= 1 else f"${curr_price:.4f}"

            matrix.append({
                "Asset": item["name"],
                "symbol": sym,
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

# --- ESECUZIONE APP ---
st.markdown("### 🛡️ Institutional Apex Quant")
st.caption("⚡ Motore Algoritmico Live Feed | Dati OHLCV Reali")

matrix_data = fetch_real_quant_matrix()
df_display = pd.DataFrame(matrix_data)

if not df_display.empty:
    # 1. GAUGE SENTIMENT GLOBALE
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

    # 2. TABELLA SEGNALI E CONFLUENZA
    st.markdown("#### 📊 Segnali & Confluenza di Mercato")
    st.dataframe(
        df_display[["Asset", "Price", "24h %", "RSI", "Squeeze", "Score", "Action"]],
        use_container_width=True,
        hide_index=True
    )

    # 3. GRAFICO CANDLESTICK REALE
    st.markdown("---")
    st.markdown("#### 📈 Struttura Prezzo Oraria")
    
    asset_names = [a["Asset"] for a in matrix_data]
    selected_name = st.selectbox("Seleziona Asset", asset_names, index=0)
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

    # 4. METRICHE VOLUMI E PREZZO
    st.markdown("---")
    st.markdown("#### ⚡ Volatilità & Volumi")
    vol_24h = df_chart["volumeto"].sum()
    m1, m2 = st.columns(2)
    with m1:
        st.metric(label="Volume 24h (USD)", value=f"${vol_24h:,.0f}")
    with m2:
        st.metric(label="RSI Attuale (1H)", value=f"{selected_row['RSI']}")

    # 5. DISPATCH NOTIFICHE PUSH
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
    st.error("Errore di connessione all'API dati. Ricarica la pagina.")
