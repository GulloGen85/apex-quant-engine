import os
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components

# --- CONFIGURAZIONE SMARTPHONE FIRST ---
st.set_page_config(
    page_title="Apex Mobile Terminal",
    layout="wide",
    page_icon="📱",
    initial_sidebar_state="collapsed"
)

# --- CSS RESPONSIVE & DARK INSTITUTIONAL ---
st.markdown("""
<style>
    .stApp { background-color: #06090e; color: #f1f5f9; }
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 3rem !important;
        padding-left: 0.4rem !important;
        padding-right: 0.4rem !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.15rem !important;
        color: #00e5ff !important;
        font-weight: 700;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.72rem !important;
        color: #94a3b8 !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        display: flex;
        overflow-x: auto;
        white-space: nowrap;
        gap: 4px;
        padding-bottom: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #0f172a;
        border-radius: 8px;
        color: #94a3b8;
        padding: 8px 12px;
        font-size: 0.8rem;
        font-weight: 700;
        border: 1px solid #1e293b;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e293b !important;
        color: #00e5ff !important;
        border: 1px solid #00e5ff !important;
    }
    .stButton>button {
        width: 100% !important;
        min-height: 44px !important;
        font-weight: 800 !important;
        border-radius: 8px !important;
        background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%) !important;
        color: #ffffff !important;
        border: none !important;
    }
    div[data-testid="stExpander"] {
        background-color: #0d131d;
        border: 1px solid #1e293b !important;
        border-radius: 8px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- NOTIFICHE (NTFY & TELEGRAM) ---
NTFY_TOPIC = "apex_signals_gullo"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_alert(title: str, message: str):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": "high", "Tags": "iphone,chart_with_upwards_trend"},
            timeout=2.0
        )
    except Exception:
        pass

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": f"📱 *{title}*\n\n{message}", "parse_mode": "Markdown"},
                timeout=2.0
            )
        except Exception:
            pass

# --- ASSET MASTER LIST ---
ASSETS = [
    {"name": "BTC", "pair": "BTC/USDC", "cb_pair": "BTC-USD", "tv_symbol": "BINANCE:BTCUSDT"},
    {"name": "ETH", "pair": "ETH/USDC", "cb_pair": "ETH-USD", "tv_symbol": "BINANCE:ETHUSDT"},
    {"name": "SOL", "pair": "SOL/USDC", "cb_pair": "SOL-USD", "tv_symbol": "BINANCE:SOLUSDT"},
    {"name": "NEAR", "pair": "NEAR/USDC", "cb_pair": "NEAR-USD", "tv_symbol": "BINANCE:NEARUSDT"},
    {"name": "TAO", "pair": "TAO/USDT", "cb_pair": "TAO-USD", "tv_symbol": "BINANCE:TAOUSDT"},
    {"name": "WLD", "pair": "WLD/USDC", "cb_pair": "WLD-USD", "tv_symbol": "BINANCE:WLDUSDT"},
    {"name": "ONDO", "pair": "ONDO/USDT", "cb_pair": "ONDO-USD", "tv_symbol": "BINANCE:ONDOUSDT"},
    {"name": "ZEC", "pair": "ZEC/USDT", "cb_pair": "ZEC-USD", "tv_symbol": "BINANCE:ZECUSDT"},
    {"name": "HYPE", "pair": "HYPE/USDT", "cb_pair": "HYPE-USD", "tv_symbol": "BYBIT:HYPEUSDT"}
]

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_crypto_history(cb_pair: str, symbol: str):
    try:
        url = f"https://api.exchange.coinbase.com/products/{cb_pair}/candles?granularity=3600"
        res = requests.get(url, headers=HEADERS, timeout=2.0).json()
        if isinstance(res, list) and len(res) >= 25:
            df = pd.DataFrame(res, columns=["time", "low", "high", "open", "close", "volume"])
            df = df.sort_values("time").reset_index(drop=True)
            df["volumeto"] = df["volume"] * df["close"]
            return df
    except Exception:
        pass

    try:
        url = f"https://min-api.cryptocompare.com/data/v2/histohour?fsym={symbol}&tsym=USD&limit=50"
        res = requests.get(url, headers=HEADERS, timeout=2.0).json()
        data = res.get("Data", {}).get("Data", [])
        if data and len(data) >= 25:
            df = pd.DataFrame(data)[["time", "open", "high", "low", "close", "volumeto"]]
            return df[df["close"] > 0].reset_index(drop=True)
    except Exception:
        pass
    return None

@st.cache_data(ttl=300)
def fetch_fear_and_greed():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=2.0).json()
        item = res["data"][0]
        return int(item["value"]), item["value_classification"]
    except Exception:
        return 50, "Neutral"

# --- MOTORE QUANTITATIVO & SEGNALI NETTI (BUY/SELL) ---
def analyze_crypto_quant(df: pd.DataFrame):
    closes = df["close"]
    highs = df["high"]
    lows = df["low"]
    vols = df["volumeto"]

    # RSI (14)
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
    rsi = round(float(rsi_series.iloc[-1]), 1)

    # ATR (14)
    tr = pd.concat([highs - lows, (highs - closes.shift(1)).abs(), (lows - closes.shift(1)).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])

    # Squeeze (Bollinger in Keltner)
    sma20 = closes.rolling(20).mean()
    std20 = closes.rolling(20).std()
    bb_u = sma20 + (2.0 * std20)
    bb_l = sma20 - (2.0 * std20)
    kc_u = sma20 + (1.5 * tr.rolling(14).mean())
    kc_l = sma20 - (1.5 * tr.rolling(14).mean())
    squeeze_on = bool(bb_l.iloc[-1] > kc_l.iloc[-1] and bb_u.iloc[-1] < kc_u.iloc[-1])

    # Trend & Momentum Slope
    ema7 = closes.ewm(span=7, adjust=False).mean()
    ema25 = closes.ewm(span=25, adjust=False).mean()
    slope = ((ema7.iloc[-1] - ema7.iloc[-4]) / ema7.iloc[-4]) * 100 if len(df) >= 5 else 0.0
    bullish = ema7.iloc[-1] >= ema25.iloc[-1]

    # Z-Score Volume
    v_mean, v_std = vols.tail(20).mean(), vols.tail(20).std()
    z_score = (vols.iloc[-1] - v_mean) / v_std if v_std > 0 else 0.0

    # Punteggio Confluenza (0 - 100)
    score = 50
    if rsi < 35: score += 18
    elif rsi > 65: score -= 18
    if bullish: score += 14
    else: score -= 14
    if squeeze_on: score += 10
    if slope > 0.15: score += 8
    elif slope < -0.15: score -= 8
    score = max(5, min(95, score))

    # Definizione Azione Chiara (Acquisto / Vendita)
    if score >= 70 or (score >= 58 and bullish and slope > 0):
        action = "🟢 COMPRA (BUY / LONG)"
        action_code = "BUY"
    elif score <= 30 or (score <= 42 and not bullish and slope < 0):
        action = "🔴 VENDI (SELL / SHORT)"
        action_code = "SELL"
    elif bullish:
        action = "🟡 ACCUMULA IN PULLBACK"
        action_code = "BUY"
    else:
        action = "🟠 DISTRIBUISCI / ATTESA"
        action_code = "SELL"

    grade = "GRADE A+" if score >= 75 else ("GRADE A" if score >= 58 else ("GRADE A-" if score <= 32 else "GRADE B"))

    df["ema7"], df["ema25"], df["bb_u"], df["bb_l"] = ema7, ema25, bb_u, bb_l

    return {
        "rsi": rsi, "atr": atr, "squeeze": squeeze_on,
        "bullish": bullish, "slope": slope, "z_score": z_score,
        "score": score, "grade": grade, "action": action, "action_code": action_code,
        "support": float(lows.tail(20).min()),
        "resistance": float(highs.tail(20).max()),
        "df": df
    }

@st.cache_data(ttl=25)
def get_terminal_data():
    dataset = []
    for item in ASSETS:
        df = fetch_crypto_history(item["cb_pair"], item["name"])
        if df is None or len(df) < 25:
            continue
        q = analyze_crypto_quant(df)
        curr_price = float(q["df"]["close"].iloc[-1])
        
        # Calcolo Target e Stop Loss
        is_buy = q["action_code"] == "BUY"
        sl_val = curr_price - (1.5 * q["atr"]) if is_buy else curr_price + (1.5 * q["atr"])
        tp1_val = curr_price + (2.0 * q["atr"]) if is_buy else curr_price - (2.0 * q["atr"])
        tp2_val = curr_price + (3.5 * q["atr"]) if is_buy else curr_price - (3.5 * q["atr"])

        dataset.append({
            "name": item["name"],
            "pair": item["pair"],
            "tv_symbol": item["tv_symbol"],
            "price": curr_price,
            "fmt_price": f"${curr_price:,.2f}" if curr_price >= 1 else f"${curr_price:.4f}",
            "rsi": q["rsi"],
            "atr": q["atr"],
            "slope": q["slope"],
            "z_score": q["z_score"],
            "score": q["score"],
            "grade": q["grade"],
            "action": q["action"],
            "action_code": q["action_code"],
            "squeeze": q["squeeze"],
            "bullish": q["bullish"],
            "support": q["support"],
            "resistance": q["resistance"],
            "sl": sl_val,
            "tp1": tp1_val,
            "tp2": tp2_val,
            "df": q["df"]
        })
    return dataset

data_list = get_terminal_data()
fng_score, fng_sentiment = fetch_fear_and_greed()
avg_market_score = int(np.mean([x["score"] for x in data_list])) if data_list else 50

# --- HEADER TOP STATS PER SMARTPHONE ---
st.markdown("### 📱 Apex Mobile Terminal")
kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("F&G Index", f"{fng_score}/100", delta=fng_sentiment, delta_color="off")
kpi2.metric("Apex Score", f"{avg_market_score}/100", delta="BULL" if avg_market_score >= 50 else "BEAR")
active_sqz = sum(1 for x in data_list if x["squeeze"])
kpi3.metric("Squeeze", f"{active_sqz} Attivi", delta="Spike Imminente" if active_sqz > 0 else "Stabile", delta_color="inverse" if active_sqz > 0 else "normal")

# --- TABS TOUCH ---
tab_radar, tab_calc, tab_chart, tab_night = st.tabs([
    "⚡ Segnali Buy/Sell",
    "🎯 Calcola Trade",
    "📈 Grafico Live TV",
    "🌙 Dormi Tranquillo"
])

# ==========================================
# TAB 1: SEGNALI OPERATIVI BUY / SELL (NATIVI STREAMLIT)
# ==========================================
with tab_radar:
    filter_type = st.radio("Filtro:", ["Tutti", "🟢 Solo Buy (Long)", "🔴 Solo Sell (Short)", "⚡ Squeeze Attivi"], horizontal=True)

    for item in data_list:
        if filter_type == "🟢 Solo Buy (Long)" and item["action_code"] != "BUY":
            continue
        if filter_type == "🔴 Solo Sell (Short)" and item["action_code"] != "SELL":
            continue
        if filter_type == "⚡ Squeeze Attivi" and not item["squeeze"]:
            continue

        # Scheda nativa con contenitore Streamlit senza glitch HTML
        with st.container(border=True):
            head_col1, head_col2 = st.columns([3, 2])
            head_col1.markdown(f"### {item['pair']}")
            head_col2.markdown(f"<h3 style='text-align:right;color:#00e5ff;'>{item['fmt_price']}</h3>", unsafe_allow_html=True)

            # Badge e Segnale
            st.markdown(f"**Segnale:** `{item['action']}` | **Grado:** `{item['grade']}`")
            if item["squeeze"]:
                st.warning("⚡ **Squeeze di Volatilità:** Compressione attiva, breakout imminente!")

            # Parametri quantitativi
            c1, c2, c3 = st.columns(3)
            c1.metric("RSI (1h)", f"{item['rsi']}")
            c2.metric("Slope Momentum", f"{item['slope']:+.2f}%")
            c3.metric("Confluenza", f"{item['score']}/100")

            # Livelli Operativi Immediati
            st.markdown("---")
            l1, l2, l3 = st.columns(3)
            l1.markdown(f"🛑 **Stop Loss:**\n`${item['sl']:,.2f}`" if item['sl'] >= 1 else f"🛑 **Stop Loss:**\n`${item['sl']:.4f}`")
            l2.markdown(f"🎯 **Target 1:**\n`${item['tp1']:,.2f}`" if item['tp1'] >= 1 else f"🎯 **Target 1:**\n`${item['tp1']:.4f}`")
            l3.markdown(f"🚀 **Target 2:**\n`${item['tp2']:,.2f}`" if item['tp2'] >= 1 else f"🚀 **Target 2:**\n`${item['tp2']:.4f}`")

# ==========================================
# TAB 2: CALCOLATORE TRADE & POSITION SIZING
# ==========================================
with tab_calc:
    st.markdown("##### 🎯 Dimensionamento Rischio & Position Sizing")
    names = [d["name"] for d in data_list]
    chosen = st.selectbox("Seleziona Moneta:", names, index=0)
    c_item = next(d for d in data_list if d["name"] == chosen)

    col_in1, col_in2 = st.columns(2)
    with col_in1:
        entry_price = st.number_input("Prezzo Entrata ($)", value=float(c_item["price"]), format="%.4f")
        direction = st.selectbox("Operazione", ["LONG (Compra) 📈", "SHORT (Vendi) 📉"], index=0 if c_item["action_code"] == "BUY" else 1)
    with col_in2:
        capital = st.number_input("Capitale Account ($)", value=2000.0, step=250.0)
        risk_pct = st.number_input("Rischio Max (%)", value=1.0, min_value=0.2, max_value=5.0, step=0.1)

    is_long = "LONG" in direction
    dist = c_item["atr"] * 1.5
    sl_calc = entry_price - dist if is_long else entry_price + dist
    loss_usd = capital * (risk_pct / 100.0)
    units = loss_usd / dist if dist > 0 else 0
    total_usd = units * entry_price

    st.markdown("---")
    r1, r2 = st.columns(2)
    r1.metric("Capitale Posizione", f"${total_usd:,.2f}")
    r2.metric("Perdita a SL", f"-${loss_usd:,.2f}")

    r3, r4 = st.columns(2)
    r3.metric("Quantità Monete", f"{units:,.4f}")
    r4.metric("Stop Loss Rigido", f"${sl_calc:,.4f}")

    st.markdown("##### 🎯 Target di Uscita Scalettati")
    t1 = entry_price + (dist * 1.5) if is_long else entry_price - (dist * 1.5)
    t2 = entry_price + (dist * 2.5) if is_long else entry_price - (dist * 2.5)
    t3 = entry_price + (dist * 4.0) if is_long else entry_price - (dist * 4.0)

    tp_df = pd.DataFrame([
        {"Target": "TP1 (Chiudi 50%)", "R:R": "1 : 1.5", "Prezzo": f"${t1:,.4f}", "Profitto": f"+${loss_usd * 1.5:,.2f}"},
        {"Target": "TP2 (Chiudi 30%)", "R:R": "1 : 2.5", "Prezzo": f"${t2:,.4f}", "Profitto": f"+${loss_usd * 2.5:,.2f}"},
        {"Target": "TP3 (Chiudi 20%)", "R:R": "1 : 4.0", "Prezzo": f"${t3:,.4f}", "Profitto": f"+${loss_usd * 4.0:,.2f}"}
    ])
    st.dataframe(tp_df, use_container_width=True, hide_index=True)

# ==========================================
# TAB 3: GRAFICI LIVE TRADINGVIEW PER MOBILE
# ==========================================
with tab_chart:
    st.markdown("##### 📈 Grafico Interattivo")
    chart_choice = st.selectbox("Seleziona Moneta Grafico:", names, index=0, key="chart_box_sel")
    ch_item = next(d for d in data_list if d["name"] == chart_choice)

    s1, s2 = st.columns(2)
    s1.metric("Supporto 24h", f"${ch_item['support']:,.2f}" if ch_item['support'] >= 1 else f"${ch_item['support']:.4f}")
    s2.metric("Resistenza 24h", f"${ch_item['resistance']:,.2f}" if ch_item['resistance'] >= 1 else f"${ch_item['resistance']:.4f}")

    # Widget TradingView Ufficiale Responsive
    tv_html = f"""
    <div style="height:380px;width:100%">
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "autosize": true,
        "symbol": "{ch_item['tv_symbol']}",
        "interval": "60",
        "timezone": "Europe/Rome",
        "theme": "dark",
        "style": "1",
        "locale": "it",
        "toolbar_bg": "#06090e",
        "enable_publishing": false,
        "hide_top_toolbar": false,
        "hide_side_toolbar": true,
        "save_image": false,
        "container_id": "tradingview_widget_box"
      }}
      );
      </script>
      <div id="tradingview_widget_box" style="height:100%;width:100%"></div>
    </div>
    """
    components.html(tv_html, height=390)

# ==========================================
# TAB 4: MODULO DORMI TRANQUILLO NOTTURNO
# ==========================================
with tab_night:
    st.markdown("##### 🌙 Audit Notturno Salvacapitale")
    sqz_coins = [d["name"] for d in data_list if d["squeeze"]]
    if sqz_coins:
        st.warning(f"⚠️ **Compressione attiva su:** {', '.join(sqz_coins)}. Possibili spike durante la notte.")
    else:
        st.success("✅ **Nessun pericolo di spike anomali.** Volatilità nella norma.")

    st.markdown("---")
    c1 = st.checkbox("Stop Loss inseriti nell'exchange per TUTTI i trade aperti", value=True)
    c2 = st.checkbox("Rischio controllato (max 1-2% del conto per operazione)", value=True)
    c3 = st.checkbox("Notifiche Push attive sullo smartphone", value=True)

    if c1 and c2 and c3:
        st.success("🛡️ **RISK AUDIT SUPERATO:** Il tuo capitale è protetto.")
    else:
        st.error("🚨 **ATTENZIONE:** Non lasciare posizioni senza Stop Loss!")

    st.markdown("---")
    if st.button("🔔 Invia Test Notifica"):
        send_alert(
            title="🌙 APEX NIGHT CHECK",
            message=f"Tutti i controlli sono attivi.\nFear & Greed: {fng_score}/100\nScore Confluenza Medio: {avg_market_score}/100"
        )
        st.info("Notifica inviata a ntfy e Telegram!")
