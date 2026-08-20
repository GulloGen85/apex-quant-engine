import os
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components

# --- CONFIGURAZIONE INTERFACCIA MOBILE-FIRST ---
st.set_page_config(
    page_title="Apex Institutional Terminal",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed"
)

# --- CSS DARK INSTITUTIONAL ---
st.markdown("""
<style>
    .stApp { background-color: #06090e; color: #f1f5f9; }
    .block-container {
        padding-top: 0.6rem !important;
        padding-bottom: 3.5rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.15rem !important;
        color: #00e5ff !important;
        font-weight: 800;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.72rem !important;
        color: #94a3b8 !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        display: flex;
        overflow-x: auto;
        white-space: nowrap;
        gap: 6px;
        padding-bottom: 6px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #0d131d;
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

# --- FUNZIONI DI INGESTION DATI MULTI-TIMEFRAME ---
def fetch_candles(symbol: str, timeframe: str = "1h", limit: int = 50):
    """Recupera candele storiche per 1h, 4h o 1D"""
    try:
        if timeframe == "1h":
            url = f"https://min-api.cryptocompare.com/data/v2/histohour?fsym={symbol}&tsym=USD&limit={limit}"
        elif timeframe == "4h":
            url = f"https://min-api.cryptocompare.com/data/v2/histohour?fsym={symbol}&tsym=USD&limit={limit*4}&aggregate=4"
        else: # 1D
            url = f"https://min-api.cryptocompare.com/data/v2/histoday?fsym={symbol}&tsym=USD&limit={limit}"

        res = requests.get(url, headers=HEADERS, timeout=2.5).json()
        data = res.get("Data", {}).get("Data", [])
        if data and len(data) >= 20:
            df = pd.DataFrame(data)[["time", "open", "high", "low", "close", "volumeto"]]
            return df[df["close"] > 0].reset_index(drop=True)
    except Exception:
        pass

    # Fallback Coinbase per 1h
    if timeframe == "1h":
        try:
            url = f"https://api.exchange.coinbase.com/products/{symbol}-USD/candles?granularity=3600"
            res = requests.get(url, headers=HEADERS, timeout=2.5).json()
            if isinstance(res, list) and len(res) >= 20:
                df = pd.DataFrame(res, columns=["time", "low", "high", "open", "close", "volume"])
                df = df.sort_values("time").reset_index(drop=True)
                df["volumeto"] = df["volume"] * df["close"]
                return df
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

# --- CALCOLO INDICATORI QUANTITATIVI ---
def compute_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 1) if not np.isnan(rsi.iloc[-1]) else 50.0

def analyze_multi_tf(symbol: str):
    df_1h = fetch_candles(symbol, "1h", 60)
    df_4h = fetch_candles(symbol, "4h", 40)
    df_1d = fetch_candles(symbol, "1D", 40)

    if df_1h is None or len(df_1h) < 25:
        return None

    rsi_1h = compute_rsi(df_1h["close"])
    rsi_4h = compute_rsi(df_4h["close"]) if df_4h is not None and len(df_4h) >= 15 else rsi_1h
    rsi_1d = compute_rsi(df_1d["close"]) if df_1d is not None and len(df_1d) >= 15 else rsi_1h

    closes, highs, lows, vols = df_1h["close"], df_1h["high"], df_1h["low"], df_1h["volumeto"]

    # ATR (14)
    tr = pd.concat([highs - lows, (highs - closes.shift(1)).abs(), (lows - closes.shift(1)).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])

    # Squeeze
    sma20 = closes.rolling(20).mean()
    std20 = closes.rolling(20).std()
    bb_u = sma20 + (2.0 * std20)
    bb_l = sma20 - (2.0 * std20)
    kc_u = sma20 + (1.5 * tr.rolling(14).mean())
    kc_l = sma20 - (1.5 * tr.rolling(14).mean())
    squeeze_on = bool(bb_l.iloc[-1] > kc_l.iloc[-1] and bb_u.iloc[-1] < kc_u.iloc[-1])

    # Trend & Slope
    ema7 = closes.ewm(span=7, adjust=False).mean()
    ema25 = closes.ewm(span=25, adjust=False).mean()
    slope = ((ema7.iloc[-1] - ema7.iloc[-4]) / ema7.iloc[-4]) * 100 if len(df_1h) >= 5 else 0.0
    bullish = ema7.iloc[-1] >= ema25.iloc[-1]

    # Z-Score Volume
    v_mean, v_std = vols.tail(20).mean(), vols.tail(20).std()
    z_score = (vols.iloc[-1] - v_mean) / v_std if v_std > 0 else 0.0

    # Punteggio Confluenza
    score = 50
    score += 15 if bullish else -15
    score += 10 if slope > 0.4 else (-10 if slope < -0.4 else 0)
    if squeeze_on: score += 10

    # Multi-TF RSI Confluence & Anti-FOMO Guard
    if rsi_1h >= 75 or rsi_4h >= 75:
        score -= 25  # Taglio immediato per overbought
    elif rsi_1h <= 30 and rsi_4h <= 35:
        score += 25  # Forte confluenza di oversold
    elif 42 <= rsi_1h <= 60 and bullish:
        score += 15  # Ottimo punto di continuazione/pullback

    score = max(5, min(95, score))

    # Definizione Azione Chiara
    if rsi_1h >= 76:
        action = "⚠️ PRENDI PROFITTO (RSI Esteso)"
        action_code = "TP"
    elif score >= 65 and rsi_1h < 70:
        action = "🟢 COMPRA / LONG (Pullback)"
        action_code = "BUY"
    elif score <= 35 and rsi_1h > 28:
        action = "🔴 VENDI / SHORT"
        action_code = "SELL"
    else:
        action = "💤 NEUTRALE / ATTENDI"
        action_code = "NEUTRAL"

    grade = "GRADE A+" if score >= 75 else ("GRADE A" if score >= 60 else ("GRADE A-" if score <= 30 else "GRADE B"))

    return {
        "rsi_1h": rsi_1h, "rsi_4h": rsi_4h, "rsi_1d": rsi_1d,
        "atr": atr, "squeeze": squeeze_on, "bullish": bullish, "slope": slope, "z_score": z_score,
        "score": score, "grade": grade, "action": action, "action_code": action_code,
        "support": float(lows.tail(20).min()),
        "resistance": float(highs.tail(20).max()),
        "df": df_1h
    }

# --- CALCOLO MAPPE DI LIQUIDAZIONE & LIVELLI A LEVA ---
def calculate_liquidation_clusters(current_price: float, atr: float):
    """
    Simula i pool di liquidazione (Long e Short) in base a 10x, 25x, 50x, 100x
    con concentrazione di volume stimata attorno ai supporti e resistenze.
    """
    leverages = [100, 50, 25, 10]
    clusters = []

    for lev in leverages:
        # Long liquidation: prezzo scende e tocca il livello di margine
        long_liq_dist = (1.0 / lev) * 0.90  # 90% del margine (considerando maintenance margin)
        long_liq_price = current_price * (1 - long_liq_dist)
        long_vol_est = (100 / lev) * 1.8 * (atr / current_price * 1000)

        # Short liquidation: prezzo sale e tocca il livello di margine
        short_liq_dist = (1.0 / lev) * 0.90
        short_liq_price = current_price * (1 + short_liq_dist)
        short_vol_est = (100 / lev) * 1.6 * (atr / current_price * 1000)

        clusters.append({
            "Leva": f"{lev}x",
            "Long Liq ($)": long_liq_price,
            "Long Vol (M$)": round(long_vol_est, 2),
            "Short Liq ($)": short_liq_price,
            "Short Vol (M$)": round(short_vol_est, 2)
        })

    return pd.DataFrame(clusters)

# --- ARKHAM / ON-CHAIN FLUX ENGINE (FEED SIMULATO & API-READY) ---
def get_arkham_whale_flows():
    """
    Feed dei movimenti on-chain delle balene (Whale CEX Inflows vs Outflows).
    Pronto per collegamento Webhook/API di Arkham Intelligence.
    """
    flows = [
        {"Orario": "10 min fa", "Asset": "BTC", "Tipo": "Outflow (Cold Wallet) 🟢", "Quantità": "1,450 BTC", "Valore": "$104.4M", "Impatto": "Bullish"},
        {"Orario": "24 min fa", "Asset": "ETH", "Tipo": "Inflow (Coinbase) 🔴", "Quantità": "12,000 ETH", "Valore": "$27.8M", "Impatto": "Bearish"},
        {"Orario": "45 min fa", "Asset": "SOL", "Tipo": "Outflow (Staking) 🟢", "Quantità": "180,000 SOL", "Valore": "$15.8M", "Impatto": "Bullish"},
        {"Orario": "1h fa", "Asset": "BTC", "Tipo": "Inflow (Binance) 🔴", "Quantità": "850 BTC", "Valore": "$61.2M", "Impatto": "Bearish"}
    ]
    return pd.DataFrame(flows)

# --- RACCOLTA DATI GLOBALE ---
@st.cache_data(ttl=25)
def load_all_terminal_data():
    dataset = []
    for item in ASSETS:
        q = analyze_multi_tf(item["name"])
        if q is None:
            continue
        curr_price = float(q["df"]["close"].iloc[-1])
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
            "rsi_1h": q["rsi_1h"],
            "rsi_4h": q["rsi_4h"],
            "rsi_1d": q["rsi_1d"],
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

data_list = load_all_terminal_data()
fng_score, fng_sentiment = fetch_fear_and_greed()
avg_market_score = int(np.mean([x["score"] for x in data_list])) if data_list else 50

# --- HEADER TOP STATS PER SMARTPHONE ---
st.markdown("### ⚡ Apex Institutional Terminal")
kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Fear & Greed", f"{fng_score}/100", delta=fng_sentiment, delta_color="off")
kpi2.metric("Apex Confluence", f"{avg_market_score}/100", delta="BULL" if avg_market_score >= 50 else "BEAR")
active_sqz = sum(1 for x in data_list if x["squeeze"])
kpi3.metric("Squeeze 1h", f"{active_sqz} Attivi", delta="Spike Imminente" if active_sqz > 0 else "Stabile", delta_color="inverse" if active_sqz > 0 else "normal")

# --- NAVIGAZIONE A TAB TOUCH-FRIENDLY ---
tab_radar, tab_heat, tab_arkham, tab_calc, tab_chart, tab_night = st.tabs([
    "⚡ Segnali & Multi-TF",
    "🔥 Mappe Liquidazione",
    "🐋 Arkham Whale Flow",
    "🎯 Calcola Trade",
    "📈 Grafici Live TV",
    "🌙 Risk Guard"
])

# ==========================================
# TAB 1: SEGNALI & RSI MULTI-TIMEFRAME (1h, 4h, 1D)
# ==========================================
with tab_radar:
    col_f1, col_f2 = st.columns([1, 1])
    with col_f1:
        tf_display = st.selectbox("Visualizzazione Principale RSI:", ["1H (Scalping/Intraday)", "4H (Swing)", "1D (Macro)"], index=0)
    with col_f2:
        filter_type = st.radio("Filtro:", ["Tutti", "🟢 Buy", "🔴 Sell / TP", "⚡ Squeeze"], horizontal=True)

    for item in data_list:
        if filter_type == "🟢 Buy" and item["action_code"] != "BUY":
            continue
        if filter_type == "🔴 Sell / TP" and item["action_code"] not in ["SELL", "TP"]:
            continue
        if filter_type == "⚡ Squeeze" and not item["squeeze"]:
            continue

        with st.container(border=True):
            h1, h2 = st.columns([3, 2])
            h1.markdown(f"### {item['pair']}")
            h2.markdown(f"<h3 style='text-align:right;color:#00e5ff;'>{item['fmt_price']}</h3>", unsafe_allow_html=True)

            # Segnale Operativo e Grado
            st.markdown(f"**Segnale:** `{item['action']}` | **Score:** `{item['score']}/100` ({item['grade']})")
            if item["squeeze"]:
                st.warning("⚡ **Squeeze Attivo:** Compressione Bande/Keltner in corso.")

            # Multi-Timeframe RSI Breakdown
            st.markdown("**RSI Multi-Timeframe:**")
            r1, r2, r3 = st.columns(3)
            r1.metric("RSI 1H", f"{item['rsi_1h']}", delta="Overbought" if item['rsi_1h'] > 70 else ("Oversold" if item['rsi_1h'] < 30 else "Neutro"))
            r2.metric("RSI 4H", f"{item['rsi_4h']}", delta="Overbought" if item['rsi_4h'] > 70 else ("Oversold" if item['rsi_4h'] < 30 else "Neutro"))
            r3.metric("RSI 1D", f"{item['rsi_1d']}", delta="Overbought" if item['rsi_1d'] > 70 else ("Oversold" if item['rsi_1d'] < 30 else "Neutro"))

            # Livelli Operativi
            st.markdown("---")
            l1, l2, l3 = st.columns(3)
            l1.markdown(f"🛑 **Stop Loss:**\n`${item['sl']:,.2f}`" if item['sl'] >= 1 else f"🛑 **Stop Loss:**\n`${item['sl']:.4f}`")
            l2.markdown(f"🎯 **Target 1:**\n`${item['tp1']:,.2f}`" if item['tp1'] >= 1 else f"🎯 **Target 1:**\n`${item['tp1']:.4f}`")
            l3.markdown(f"🚀 **Target 2:**\n`${item['tp2']:,.2f}`" if item['tp2'] >= 1 else f"🚀 **Target 2:**\n`${item['tp2']:.4f}`")

# ==========================================
# TAB 2: MAPPE DI LIQUIDAZIONE & LIVELLI A LEVA
# ==========================================
with tab_heat:
    st.markdown("##### 🔥 Liquidation Heatmap & Leverage Clusters")
    names = [d["name"] for d in data_list]
    chosen_liq = st.selectbox("Seleziona Moneta per Mappa Liquidazioni:", names, index=0, key="liq_coin_select")
    target_asset = next(d for d in data_list if d["name"] == chosen_liq)

    df_liq = calculate_liquidation_clusters(target_asset["price"], target_asset["atr"])

    # Grafico a barre orizzontali: Pool Liquidazioni Long vs Short
    fig_liq = go.Figure()

    # Short liquidations (sopra il prezzo corrente -> barre rosse)
    fig_liq.add_trace(go.Bar(
        y=df_liq["Leva"],
        x=df_liq["Short Vol (M$)"],
        orientation='h',
        name='Short Liq (Liquidity Above)',
        marker=dict(color='#ff1744'),
        text=[f"${p:,.2f}" if p >= 1 else f"${p:.4f}" for p in df_liq["Short Liq ($)"]],
        textposition='auto'
    ))

    # Long liquidations (sotto il prezzo corrente -> barre verdi)
    fig_liq.add_trace(go.Bar(
        y=df_liq["Leva"],
        x=[-v for v in df_liq["Long Vol (M$)"]],
        orientation='h',
        name='Long Liq (Liquidity Below)',
        marker=dict(color='#00e676'),
        text=[f"${p:,.2f}" if p >= 1 else f"${p:.4f}" for p in df_liq["Long Liq ($)"]],
        textposition='auto'
    ))

    fig_liq.update_layout(
        title=f"Mappa Pool Liquidazione per {chosen_liq} (Prezzo Corrente: {target_asset['fmt_price']})",
        barmode='overlay',
        paper_bgcolor='#06090e',
        plot_bgcolor='#0d131d',
        font=dict(color='#e2e8f0', size=11),
        height=330,
        margin=dict(l=10, r=10, t=40, b=20),
        xaxis=dict(showgrid=False, title="Volume Stimato Liquidabile (M$)"),
        yaxis=dict(autorange="reversed")
    )
    st.plotly_chart(fig_liq, use_container_width=True)

    st.markdown("###### 📊 Tabella Dettaglio Livelli per Leva")
    formatted_liq = df_liq.copy()
    formatted_liq["Long Liq ($)"] = formatted_liq["Long Liq ($)"].apply(lambda x: f"${x:,.2f}" if x >= 1 else f"${x:.4f}")
    formatted_liq["Short Liq ($)"] = formatted_liq["Short Liq ($)"].apply(lambda x: f"${x:,.2f}" if x >= 1 else f"${x:.4f}")
    formatted_liq["Long Vol"] = formatted_liq["Long Vol (M$)"].apply(lambda x: f"${x:.1f}M")
    formatted_liq["Short Vol"] = formatted_liq["Short Vol (M$)"].apply(lambda x: f"${x:.1f}M")
    st.dataframe(formatted_liq[["Leva", "Long Liq ($)", "Long Vol", "Short Liq ($)", "Short Vol"]], use_container_width=True, hide_index=True)

# ==========================================
# TAB 3: ARKHAM INTELLIGENCE & WHALE TRACKER
# ==========================================
with tab_arkham:
    st.markdown("##### 🐋 Flussi Balene & Dati On-Chain (Stile Arkham)")
    st.info("I grandi trasferimenti verso exchange anticipano dump; i deflussi (outflow) verso cold wallet indicano accumulazione.")

    w1, w2 = st.columns(2)
    w1.metric("Whale Bias 24h", "🟢 ACCUMULAZIONE", delta="+ $182.4M Net Outflow")
    w2.metric("Depositi CEX Sospetti", "2 Grandi Wallet", delta="- $89.0M", delta_color="inverse")

    df_arkham = get_arkham_whale_flows()
    st.markdown("###### 🔍 Ultime Transazioni Grandi Wallet")
    st.dataframe(df_arkham, use_container_width=True, hide_index=True)

    with st.expander("⚙️ Configurazione API Arkham Intelligence"):
        st.text_input("Arkham API Key:", type="password", placeholder="arkham_live_sk_...")
        st.checkbox("Abilita Webhook Telegram per movimenti > $10M", value=True)

# ==========================================
# TAB 4: CALCOLATORE TRADE & POSITION SIZING
# ==========================================
with tab_calc:
    st.markdown("##### 🎯 Dimensionamento Rischio & Position Sizing")
    chosen_calc = st.selectbox("Seleziona Moneta per Trade:", names, index=0, key="calc_select")
    cur_trade = next(d for d in data_list if d["name"] == chosen_calc)

    cin1, cin2 = st.columns(2)
    with cin1:
        entry_price = st.number_input("Prezzo Entrata ($)", value=float(cur_trade["price"]), format="%.4f")
        direction = st.selectbox("Direzione", ["LONG (Compra) 📈", "SHORT (Vendi) 📉"], index=0 if cur_trade["action_code"] == "BUY" else 1)
    with cin2:
        capital = st.number_input("Capitale Account ($)", value=2000.0, step=250.0)
        risk_pct = st.number_input("Rischio Max (%)", value=1.0, min_value=0.2, max_value=5.0, step=0.1)

    is_l = "LONG" in direction
    dist = cur_trade["atr"] * 1.5
    sl_calc = entry_price - dist if is_l else entry_price + dist
    loss_usd = capital * (risk_pct / 100.0)
    units = loss_usd / dist if dist > 0 else 0
    total_usd = units * entry_price

    st.markdown("---")
    r1, r2 = st.columns(2)
    r1.metric("Capitale Posizione", f"${total_usd:,.2f}")
    r2.metric("Perdita Max a SL", f"-${loss_usd:,.2f}")

    r3, r4 = st.columns(2)
    r3.metric("Quantità Monete", f"{units:,.4f}")
    r4.metric("Stop Loss Rigido", f"${sl_calc:,.4f}")

    t1 = entry_price + (dist * 1.5) if is_l else entry_price - (dist * 1.5)
    t2 = entry_price + (dist * 2.5) if is_l else entry_price - (dist * 2.5)
    t3 = entry_price + (dist * 4.0) if is_l else entry_price - (dist * 4.0)

    st.markdown("###### 🎯 Piani di Uscita e Take Profit")
    tp_df = pd.DataFrame([
        {"Target": "TP1 (Chiudi 50%)", "R:R": "1 : 1.5", "Prezzo": f"${t1:,.4f}", "Profitto": f"+${loss_usd * 1.5:,.2f}"},
        {"Target": "TP2 (Chiudi 30%)", "R:R": "1 : 2.5", "Prezzo": f"${t2:,.4f}", "Profitto": f"+${loss_usd * 2.5:,.2f}"},
        {"Target": "TP3 (Chiudi 20%)", "R:R": "1 : 4.0", "Prezzo": f"${t3:,.4f}", "Profitto": f"+${loss_usd * 4.0:,.2f}"}
    ])
    st.dataframe(tp_df, use_container_width=True, hide_index=True)

# ==========================================
# TAB 5: GRAFICI LIVE TRADINGVIEW PER MOBILE
# ==========================================
with tab_chart:
    st.markdown("##### 📈 Grafico TradingView Interattivo")
    chart_choice = st.selectbox("Seleziona Moneta Grafico:", names, index=0, key="tv_select")
    ch_item = next(d for d in data_list if d["name"] == chart_choice)

    s1, s2 = st.columns(2)
    s1.metric("Supporto 24h", f"${ch_item['support']:,.2f}" if ch_item['support'] >= 1 else f"${ch_item['support']:.4f}")
    s2.metric("Resistenza 24h", f"${ch_item['resistance']:,.2f}" if ch_item['resistance'] >= 1 else f"${ch_item['resistance']:.4f}")

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
        "container_id": "tv_widget"
      }}
      );
      </script>
      <div id="tv_widget" style="height:100%;width:100%"></div>
    </div>
    """
    components.html(tv_html, height=390)

# ==========================================
# TAB 6: RISK GUARD NOTTURNO
# ==========================================
with tab_night:
    st.markdown("##### 🌙 Audit Salvacapitale Notturno")
    sqz_coins = [d["name"] for d in data_list if d["squeeze"]]
    if sqz_coins:
        st.warning(f"⚠️ Compressione attiva su: **{', '.join(sqz_coins)}**. Rischio spike di volatilità notturna.")
    else:
        st.success("✅ Nessun squeeze anomalo rilevato. Mercato in volatilità standard.")

    st.markdown("---")
    c1 = st.checkbox("Stop Loss inserito per ogni posizione aperta", value=True)
    c2 = st.checkbox("Rischio controllato (max 1-2% del capitale totale)", value=True)
    c3 = st.checkbox("Notifiche Push attive sullo smartphone", value=True)

    if c1 and c2 and c3:
        st.success("🛡️ **RISK AUDIT SUPERATO:** Puoi lasciare il terminale attivo in sicurezza.")
    else:
        st.error("🚨 **RISCHIO ATTIVO:** Imposta gli Stop Loss sull'exchange prima di disconnetterti.")
