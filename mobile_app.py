import os
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# --- CONFIGURAZIONE DASHBOARD MOBILE-FIRST ---
st.set_page_config(
    page_title="Apex Institutional Quant",
    layout="centered",
    page_icon="🛡️",
    initial_sidebar_state="collapsed"
)

# --- CSS DARK INSTITUTIONAL THEME ---
st.markdown("""
<style>
    .stApp { background-color: #080b10; color: #e0e6ed; }
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    div[data-testid="stMetricValue"] { color: #00d2ff !important; font-size: 1.25rem !important; }
    div[data-testid="stMetricLabel"] { font-size: 0.78rem !important; color: #8fa0b5 !important; }
    .stButton>button {
        width: 100%;
        background-color: #00d2ff;
        color: #080b10;
        font-weight: bold;
        border-radius: 8px;
        padding: 0.6rem;
    }
</style>
""", unsafe_allow_html=True)

# --- CONFIGURAZIONE NOTIFICHE ---
NTFY_TOPIC = "apex_signals_gullo"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_push_notification(title: str, message: str, priority: str = "high"):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": priority, "Tags": "chart_with_upwards_trend,rotating_light"},
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

# --- LISTA ASSET & ENDPOINT MULTI-PROVIDER ---
ASSETS = [
    {"name": "BTC/USD", "symbol": "BTC", "cb_pair": "BTC-USD"},
    {"name": "ETH/USD", "symbol": "ETH", "cb_pair": "ETH-USD"},
    {"name": "SOL/USD", "symbol": "SOL", "cb_pair": "SOL-USD"},
    {"name": "TAO/USD", "symbol": "TAO", "cb_pair": "TAO-USD"},
    {"name": "ONDO/USD", "symbol": "ONDO", "cb_pair": "ONDO-USD"},
    {"name": "HYPE/USD", "symbol": "HYPE", "cb_pair": "HYPE-USD"},
    {"name": "WLD/USD", "symbol": "WLD", "cb_pair": "WLD-USD"},
    {"name": "ZEC/USD", "symbol": "ZEC", "cb_pair": "ZEC-USD"}
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# --- MOTORE DI CALCOLO INDICATORI QUANTITATIVI ---
def compute_full_quant_suite(df: pd.DataFrame):
    closes = df["close"]
    highs = df["high"]
    lows = df["low"]
    vols = df["volumeto"]

    # 1. RSI (14 periodi - Wilder Smoothing)
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
    current_rsi = round(float(rsi_series.iloc[-1]), 1) if not pd.isna(rsi_series.iloc[-1]) else 50.0

    # 2. ATR (14 periodi - Volatilità Reale)
    tr1 = highs - lows
    tr2 = (highs - closes.shift(1)).abs()
    tr3 = (lows - closes.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_series = tr.rolling(14).mean()
    current_atr = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else float(tr.mean())

    # 3. Bollinger Bands (20, 2.0)
    sma20 = closes.rolling(20).mean()
    std20 = closes.rolling(20).std()
    df["bb_upper"] = sma20 + (2.0 * std20)
    df["bb_middle"] = sma20
    df["bb_lower"] = sma20 - (2.0 * std20)

    # 4. Keltner Channels (20, 1.5 ATR)
    df["kc_upper"] = sma20 + (1.5 * atr_series)
    df["kc_lower"] = sma20 - (1.5 * atr_series)

    # 5. John Carter Squeeze Check
    squeeze_on = bool(df["bb_lower"].iloc[-1] > df["kc_lower"].iloc[-1] and df["bb_upper"].iloc[-1] < df["kc_upper"].iloc[-1])

    # 6. EMA (7, 25, 50)
    df["ema7"] = closes.ewm(span=7, adjust=False).mean()
    df["ema25"] = closes.ewm(span=25, adjust=False).mean()
    df["ema50"] = closes.ewm(span=50, adjust=False).mean()
    trend_bullish = df["ema7"].iloc[-1] > df["ema25"].iloc[-1]

    # 7. MACD (12, 26, 9)
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - macd_signal
    macd_bull = macd_line.iloc[-1] > macd_signal.iloc[-1]

    # 8. VWAP Intraday
    typical_price = (highs + lows + closes) / 3
    cum_vol = vols.cumsum()
    vwap_series = (typical_price * vols).cumsum() / cum_vol.replace(0, np.nan)
    current_vwap = float(vwap_series.iloc[-1]) if not pd.isna(vwap_series.iloc[-1]) else float(closes.iloc[-1])

    # 9. Supporti e Resistenze Pivot (Donchian 20 periodi)
    support_level = float(lows.tail(20).min())
    resistance_level = float(highs.tail(20).max())

    # 10. ADX / Forza del Trend (14)
    up_move = highs - highs.shift(1)
    down_move = lows.shift(1) - lows
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / atr_series)
    minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / atr_series)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(20)
    adx = float(dx.rolling(14).mean().iloc[-1]) if not pd.isna(dx.rolling(14).mean().iloc[-1]) else 22.0

    return {
        "rsi": current_rsi,
        "atr": current_atr,
        "squeeze": squeeze_on,
        "trend_bull": trend_bullish,
        "macd_bull": macd_bull,
        "macd_hist_val": float(macd_hist.iloc[-1]),
        "vwap": current_vwap,
        "support": support_level,
        "resistance": resistance_level,
        "adx": round(adx, 1),
        "df": df
    }

# --- FETCH DATA SERVICES ---
def fetch_history_coinbase(pair: str):
    try:
        url = f"https://api.exchange.coinbase.com/products/{pair}/candles?granularity=3600"
        res = requests.get(url, headers=HEADERS, timeout=2.5).json()
        if isinstance(res, list) and len(res) >= 20:
            df = pd.DataFrame(res, columns=["time", "low", "high", "open", "close", "volume"])
            df = df.sort_values("time").reset_index(drop=True)
            df["volumeto"] = df["volume"] * df["close"]
            return df
    except Exception:
        pass
    return None

def fetch_history_cryptocompare(symbol: str):
    try:
        url = f"https://min-api.cryptocompare.com/data/v2/histohour?fsym={symbol}&tsym=USD&limit=50"
        res = requests.get(url, headers=HEADERS, timeout=2.5).json()
        data_list = res.get("Data", {}).get("Data", [])
        if data_list and len(data_list) >= 20:
            df = pd.DataFrame(data_list)
            df = df[["time", "open", "high", "low", "close", "volumeto"]].copy()
            df = df[df["close"] > 0].reset_index(drop=True)
            return df
    except Exception:
        pass
    return None

@st.cache_data(ttl=300)
def fetch_fear_and_greed():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=2.5).json()
        item = res["data"][0]
        return int(item["value"]), item["value_classification"]
    except Exception:
        return 50, "Neutral"

@st.cache_data(ttl=25)
def build_quant_matrix():
    matrix = []
    
    for item in ASSETS:
        df_raw = fetch_history_coinbase(item["cb_pair"])
        if df_raw is None or len(df_raw) < 25:
            df_raw = fetch_history_cryptocompare(item["symbol"])

        if df_raw is None or len(df_raw) < 25:
            continue

        metrics = compute_full_quant_suite(df_raw)
        curr_price = float(metrics["df"]["close"].iloc[-1])
        prev_24h_close = float(metrics["df"]["close"].iloc[-24]) if len(metrics["df"]) >= 25 else float(metrics["df"]["close"].iloc[0])
        pct_change = ((curr_price - prev_24h_close) / prev_24h_close) * 100

        # Algoritmo di Scoring Istituzionale (0-100)
        score = 50
        if metrics["rsi"] < 32: score += 18
        elif metrics["rsi"] > 68: score -= 18
        
        if metrics["trend_bull"]: score += 12
        else: score -= 12
        
        if metrics["macd_bull"]: score += 10
        else: score -= 10
        
        if metrics["squeeze"]: score += 10
        if metrics["adx"] > 25: score += (5 if metrics["trend_bull"] else -5)

        score = max(5, min(95, score))

        # Calcolo Target & Rischio Dinamici (ATR-Based)
        if score >= 50:
            bias = "🟢 BULL"
            sl_price = curr_price - (1.5 * metrics["atr"])
            tp1_price = curr_price + (2.0 * metrics["atr"])
            tp2_price = curr_price + (3.5 * metrics["atr"])
            if score >= 70 and metrics["squeeze"]:
                action = "🔥 ULTRA LONG"
            elif score >= 58:
                action = "🟢 LONG"
            else:
                action = "💤 WAIT"
        else:
            bias = "🔴 BEAR"
            sl_price = curr_price + (1.5 * metrics["atr"])
            tp1_price = curr_price - (2.0 * metrics["atr"])
            tp2_price = curr_price - (3.5 * metrics["atr"])
            if score <= 30 and metrics["squeeze"]:
                action = "🚨 ULTRA SHORT"
            elif score <= 42:
                action = "🔴 SHORT"
            else:
                action = "💤 WAIT"

        fmt_price = f"${curr_price:,.2f}" if curr_price >= 1 else f"${curr_price:.4f}"
        fmt_atr = f"${metrics['atr']:,.2f}" if metrics['atr'] >= 1 else f"${metrics['atr']:.4f}"

        matrix.append({
            "Asset": item["name"],
            "Prezzo": fmt_price,
            "raw_price": curr_price,
            "24h %": f"{pct_change:+.2f}%",
            "RSI": metrics["rsi"],
            "ADX": metrics["adx"],
            "ATR (14)": fmt_atr,
            "raw_atr": metrics["atr"],
            "MACD": "🟢 Bull" if metrics["macd_bull"] else "🔴 Bear",
            "Squeeze": "⚡ SI" if metrics["squeeze"] else "NO",
            "Score": score,
            "Bias": bias,
            "Action": action,
            "VWAP": metrics["vwap"],
            "Supporto": metrics["support"],
            "Resistenza": metrics["resistance"],
            "Stop Loss": sl_price,
            "TP 1": tp1_price,
            "TP 2": tp2_price,
            "df": metrics["df"]
        })

    return matrix

# --- CARICAMENTO INTERFACCIA ---
st.markdown("### 🛡️ Institutional Apex Quant")
st.caption("⚡ Motore Algoritmico Multifattoriale & Dati OHLCV")

matrix_data = build_quant_matrix()
fng_val, fng_class = fetch_fear_and_greed()

if matrix_data:
    df_table = pd.DataFrame(matrix_data)

    # --- 1. MACRO REGIME & SENTIMENT ---
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("##### 🌐 Crypto Fear & Greed")
        st.metric(label="Sentiment di Mercato", value=f"{fng_val}/100", delta=fng_class)
    with col_g2:
        avg_score = int(df_table["Score"].mean())
        st.markdown("##### ⚙️ Apex Quant Score")
        st.metric(label="Indice Confluenza Medio", value=f"{avg_score}/100", delta="Bullish" if avg_score >= 50 else "Bearish")

    # --- 2. GAUGE GLOBALE ---
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
    fig_gauge.update_layout(height=160, margin=dict(l=5, r=5, t=5, b=5), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
    st.plotly_chart(fig_gauge, use_container_width=True)

    # --- 3. MATRICE COMPLETA DEI PARAMETRI ---
    st.markdown("#### 📊 Matrice Parametrica Multi-Asset")
    st.dataframe(
        df_table[["Asset", "Prezzo", "24h %", "RSI", "ADX", "MACD", "Squeeze", "Score", "Action"]],
        use_container_width=True,
        hide_index=True
    )

    # --- 4. DETTAGLIO QUANTITATIVO ASSET SELEZIONATO ---
    st.markdown("---")
    selected_name = st.selectbox("Seleziona Asset per Deep Analysis", [a["Asset"] for a in matrix_data], index=0)
    asset_data = next(item for item in matrix_data if item["Asset"] == selected_name)
    df_asset = asset_data["df"].tail(35).copy()

    st.markdown(f"#### 🎯 Parametri di Esecuzione & Livelli ({selected_name})")
    
    # Metriche Istituzionali
    p1, p2, p3 = st.columns(3)
    with p1:
        st.metric("VWAP Sessione", f"${asset_data['VWAP']:,.2f}" if asset_data['VWAP'] >= 1 else f"${asset_data['VWAP']:.4f}")
        st.metric("Supporto Chiave", f"${asset_data['Supporto']:,.2f}" if asset_data['Supporto'] >= 1 else f"${asset_data['Supporto']:.4f}")
    with p2:
        st.metric("ATR Volatilità", asset_data["ATR (14)"])
        st.metric("Resistenza Chiave", f"${asset_data['Resistenza']:,.2f}" if asset_data['Resistenza'] >= 1 else f"${asset_data['Resistenza']:.4f}")
    with p3:
        st.metric("Stop Loss (1.5x ATR)", f"${asset_data['Stop Loss']:,.2f}" if asset_data['Stop Loss'] >= 1 else f"${asset_data['Stop Loss']:.4f}")
        st.metric("Take Profit 1 (2x ATR)", f"${asset_data['TP 1']:,.2f}" if asset_data['TP 1'] >= 1 else f"${asset_data['TP 1']:.4f}")

    # --- 5. GRAFICO CON BANDE BOLLINGER, KELTNER ED EMA ---
    st.markdown("#### 📈 Grafico Strutturale con Indicatori")
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=np.arange(len(df_asset)),
        open=df_asset["open"],
        high=df_asset["high"],
        low=df_asset["low"],
        close=df_asset["close"],
        name="OHLC"
    ), row=1, col=1)

    # EMA 7 & 25
    fig.add_trace(go.Scatter(x=np.arange(len(df_asset)), y=df_asset["ema7"], line=dict(color="#00e676", width=1), name="EMA 7"), row=1, col=1)
    fig.add_trace(go.Scatter(x=np.arange(len(df_asset)), y=df_asset["ema25"], line=dict(color="#ff9100", width=1), name="EMA 25"), row=1, col=1)

    # Bollinger Bands
    fig.add_trace(go.Scatter(x=np.arange(len(df_asset)), y=df_asset["bb_upper"], line=dict(color="rgba(0, 210, 255, 0.35)", width=1, dash="dot"), name="BB Upper"), row=1, col=1)
    fig.add_trace(go.Scatter(x=np.arange(len(df_asset)), y=df_asset["bb_lower"], line=dict(color="rgba(0, 210, 255, 0.35)", width=1, dash="dot"), name="BB Lower"), row=1, col=1)

    # Volumi
    colors_vol = ['#00e676' if c >= o else '#ff1744' for c, o in zip(df_asset['close'], df_asset['open'])]
    fig.add_trace(go.Bar(x=np.arange(len(df_asset)), y=df_asset["volumeto"], marker_color=colors_vol, name="Volume"), row=2, col=1)

    fig.update_layout(
        height=320,
        margin=dict(l=5, r=5, t=5, b=5),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_rangeslider_visible=False,
        showlegend=False,
        font={'color': "white"}
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- 6. DISPATCH NOTIFICHE PUSH ---
    st.markdown("---")
    if st.button("📲 Invia Notifiche Push"):
        alert_rows = df_table[df_table["Action"].str.contains("LONG|SHORT", regex=True)]
        if not alert_rows.empty:
            for _, r in alert_rows.iterrows():
                send_push_notification(
                    title=f"🚨 {r['Asset']} — {r['Action']}",
                    message=f"Prezzo: {r['Prezzo']} | RSI: {r['RSI']} | ADX: {r['ADX']} | SL: ${r['Stop Loss']:.2f} | TP1: ${r['TP 1']:.2f}"
                )
            st.success("🔔 Notifiche inviate con successo!")
        else:
            st.info("Nessuna anomalia quantitativa rilevata al momento.")
else:
    st.warning("Caricamento stream dati di mercato...")
