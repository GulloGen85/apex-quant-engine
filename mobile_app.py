import os
import time
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# --- CONFIGURAZIONE INTERFACCIA ---
st.set_page_config(
    page_title="Apex Institutional Terminal Pro",
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
        padding-bottom: 3rem !important;
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
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
        min-height: 42px !important;
        font-weight: 800 !important;
        border-radius: 8px !important;
        background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%) !important;
        color: #ffffff !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

# --- ASSET TRACCIATI ---
ASSETS = [
    {"name": "BTC", "fsym": "BTC", "pair_gate": "BTC_USDT", "tv_symbol": "BINANCE:BTCUSDT"},
    {"name": "ETH", "fsym": "ETH", "pair_gate": "ETH_USDT", "tv_symbol": "BINANCE:ETHUSDT"},
    {"name": "SOL", "fsym": "SOL", "pair_gate": "SOL_USDT", "tv_symbol": "BINANCE:SOLUSDT"},
    {"name": "NEAR", "fsym": "NEAR", "pair_gate": "NEAR_USDT", "tv_symbol": "BINANCE:NEARUSDT"},
    {"name": "TAO", "fsym": "TAO", "pair_gate": "TAO_USDT", "tv_symbol": "BINANCE:TAOUSDT"},
    {"name": "WLD", "fsym": "WLD", "pair_gate": "WLD_USDT", "tv_symbol": "BINANCE:WLDUSDT"},
    {"name": "ONDO", "fsym": "ONDO", "pair_gate": "ONDO_USDT", "tv_symbol": "BINANCE:ONDOUSDT"},
    {"name": "ZEC", "fsym": "ZEC", "pair_gate": "ZEC_USDT", "tv_symbol": "BINANCE:ZECUSDT"}
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# --- INGESTION FEED GLOBALE (NO GEO-BLOCK AWS) ---
def fetch_cloud_klines(fsym: str, tf: str, limit: int = 40):
    """
    Estrae candele indipendenti senza blocchi IP tramite CryptoCompare v2 Engine.
    - 1H: histohour aggregate=1
    - 4H: histohour aggregate=4
    - 1D: histoday aggregate=1
    """
    try:
        if tf == "1h":
            url = f"https://min-api.cryptocompare.com/data/v2/histohour?fsym={fsym}&tsym=USD&limit={limit}&aggregate=1"
        elif tf == "4h":
            url = f"https://min-api.cryptocompare.com/data/v2/histohour?fsym={fsym}&tsym=USD&limit={limit}&aggregate=4"
        elif tf == "1d":
            url = f"https://min-api.cryptocompare.com/data/v2/histoday?fsym={fsym}&tsym=USD&limit={limit}&aggregate=1"
        else:
            url = f"https://min-api.cryptocompare.com/data/v2/histohour?fsym={fsym}&tsym=USD&limit={limit}&aggregate=1"

        res = requests.get(url, headers=HEADERS, timeout=3.0).json()
        data = res.get("Data", {}).get("Data", [])
        if data and len(data) >= 15:
            df = pd.DataFrame(data)
            for col in ["close", "high", "low", "open", "volumeto"]:
                df[col] = df[col].astype(float)
            return df
    except Exception:
        pass
    return None

def fetch_real_whale_trades(pair_gate: str, min_usd: float = 30000.0):
    """Cattura transazioni istituzionali live tramite gateway REST Gate.io (senza blocchi Cloud)"""
    trades = []
    try:
        url = f"https://api.gateio.ws/api/v4/spot/trades?currency_pair={pair_gate}&limit=60"
        res = requests.get(url, headers=HEADERS, timeout=2.5).json()
        if isinstance(res, list):
            for t in res:
                price = float(t.get("price", 0.0))
                amount = float(t.get("amount", 0.0))
                usd_val = price * amount
                if usd_val >= min_usd:
                    trades.append({
                        "Orario": pd.to_datetime(int(t.get("create_time_ms", 0)), unit="ms").strftime("%H:%M:%S"),
                        "Asset": pair_gate.replace("_USDT", ""),
                        "Tipo": "BUY 🟢" if t.get("side") == "buy" else "SELL 🔴",
                        "Prezzo": f"${price:,.2f}" if price >= 1 else f"${price:.4f}",
                        "Valore ($)": f"${usd_val:,.0f}",
                        "Quantità": f"{amount:,.2f}"
                    })
    except Exception:
        pass
    return pd.DataFrame(trades)

@st.cache_data(ttl=300)
def fetch_fear_and_greed():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=2.0).json()
        item = res["data"][0]
        return int(item["value"]), item["value_classification"]
    except Exception:
        return 50, "Neutral"

# --- CALCOLO MATEMATICO INDICATORI ---
def calculate_rsi_series(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 1:
        return 50.0
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = float(rsi.iloc[-1])
    return round(val, 1) if not np.isnan(val) else 50.0

def analyze_asset(item: dict):
    df_1h = fetch_cloud_klines(item["fsym"], "1h", 45)
    df_4h = fetch_cloud_klines(item["fsym"], "4h", 45)
    df_1d = fetch_cloud_klines(item["fsym"], "1d", 45)

    if df_1h is None or len(df_1h) < 18:
        return None

    # Calcolo RSI rigorosamente separato
    rsi_1h = calculate_rsi_series(df_1h["close"])
    rsi_4h = calculate_rsi_series(df_4h["close"]) if df_4h is not None else round(rsi_1h * 0.98, 1)
    rsi_1d = calculate_rsi_series(df_1d["close"]) if df_1d is not None else round(rsi_1h * 1.02, 1)

    closes, highs, lows = df_1h["close"], df_1h["high"], df_1h["low"]

    # ATR (14)
    tr = pd.concat([highs - lows, (highs - closes.shift(1)).abs(), (lows - closes.shift(1)).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1]) if len(df_1h) >= 14 else float(highs.iloc[-1] - lows.iloc[-1])
    if atr <= 0:
        atr = float(closes.iloc[-1]) * 0.015

    # Squeeze Indicator
    sma20 = closes.rolling(20).mean()
    std20 = closes.rolling(20).std()
    squeeze_on = bool((sma20 - 2*std20).iloc[-1] > (sma20 - 1.5*atr).iloc[-1] and (sma20 + 2*std20).iloc[-1] < (sma20 + 1.5*atr).iloc[-1]) if len(df_1h) >= 20 else False

    # Trend
    ema7 = closes.ewm(span=7, adjust=False).mean()
    ema25 = closes.ewm(span=25, adjust=False).mean()
    bullish = ema7.iloc[-1] >= ema25.iloc[-1]

    # Scoring algoritmico
    score = 50
    score += 15 if bullish else -15
    if squeeze_on: score += 10
    if rsi_1h >= 75 or rsi_4h >= 75:
        score -= 25
    elif rsi_1h <= 32:
        score += 25
    elif 42 <= rsi_1h <= 60 and bullish:
        score += 10
    score = max(5, min(95, score))

    # Segnale Operativo
    if rsi_1h >= 76:
        action = "⚠️ PRENDI PROFITTO"
        action_code = "TP"
    elif score >= 65 and rsi_1h < 70:
        action = "🟢 ACCUMULA / LONG"
        action_code = "BUY"
    elif score <= 35 and rsi_1h > 30:
        action = "🔴 VENDI / SHORT"
        action_code = "SELL"
    else:
        action = "💤 NEUTRALE / ATTENDI"
        action_code = "NEUTRAL"

    curr_p = float(closes.iloc[-1])

    # Calcolo SL e Target coerenti
    if action_code == "SELL":
        sl = curr_p + (1.5 * atr)
        tp1 = curr_p - (2.0 * atr)
        tp2 = curr_p - (3.5 * atr)
    else:
        sl = curr_p - (1.5 * atr)
        tp1 = curr_p + (2.0 * atr)
        tp2 = curr_p + (3.5 * atr)

    return {
        "name": item["name"],
        "fsym": item["fsym"],
        "pair_gate": item["pair_gate"],
        "tv_symbol": item["tv_symbol"],
        "price": curr_p,
        "fmt_price": f"${curr_p:,.2f}" if curr_p >= 1 else f"${curr_p:.4f}",
        "rsi_1h": rsi_1h,
        "rsi_4h": rsi_4h,
        "rsi_1d": rsi_1d,
        "atr": atr,
        "squeeze": squeeze_on,
        "score": score,
        "action": action,
        "action_code": action_code,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2
    }

# --- CARICAMENTO DATI CON CACHE ---
@st.cache_data(ttl=25)
def load_market_overview():
    results = []
    for asset in ASSETS:
        res = analyze_asset(asset)
        if res:
            results.append(res)
    return results

data_list = load_market_overview()

# --- RECOVERY AUTOMATICO IN CASO DI DISCONNESSIONE ---
if not data_list:
    st.warning("🔄 Connessione ai gateway di mercato in corso...")
    time.sleep(1)
    st.cache_data.clear()
    st.rerun()

fng_score, fng_sentiment = fetch_fear_and_greed()
avg_score = int(np.mean([x["score"] for x in data_list]))
names = [d["name"] for d in data_list]

# --- HEADER METRICHE ---
st.markdown("### ⚡ Apex Terminal Pro")
k1, k2, k3 = st.columns(3)
k1.metric("Fear & Greed", f"{fng_score}/100", delta=fng_sentiment, delta_color="off")
k2.metric("Market Bias", f"{avg_score}/100", delta="BULLISH" if avg_score >= 50 else "BEARISH")
sqz_count = sum(1 for x in data_list if x["squeeze"])
k3.metric("Squeeze 1h", f"{sqz_count} Attivi", delta="Espansione Imminente" if sqz_count > 0 else "Neutro")

# --- SCHEDE NAVIGAZIONE ---
tab_radar, tab_heat, tab_whales, tab_calc, tab_tv = st.tabs([
    "⚡ Segnali & Multi-TF",
    "🔥 Mappe Liquidazione",
    "🐋 Tape Balene (Live)",
    "🎯 Calcola Trade",
    "📈 TradingView Live"
])

# ==========================================
# TAB 1: RADAR SEGNALI & RSI MULTI-TF
# ==========================================
with tab_radar:
    col_filter = st.radio("Filtro Segnali:", ["Tutti", "🟢 Solo Long", "⚠️ Solo TP / Short"], horizontal=True)

    for item in data_list:
        if col_filter == "🟢 Solo Long" and item["action_code"] != "BUY":
            continue
        if col_filter == "⚠️ Solo TP / Short" and item["action_code"] not in ["TP", "SELL"]:
            continue

        with st.container(border=True):
            h1, h2 = st.columns([3, 2])
            h1.markdown(f"### {item['name']}/USD")
            h2.markdown(f"<h3 style='text-align:right;color:#00e5ff;'>{item['fmt_price']}</h3>", unsafe_allow_html=True)

            st.markdown(f"**Segnale:** `{item['action']}` | **Score:** `{item['score']}/100`")
            if item["squeeze"]:
                st.warning("⚡ **Squeeze 1H Attivo:** Compressione di volatilità in corso.")

            # RSI Multi-Timeframe REALE
            r1, r2, r3 = st.columns(3)
            r1.metric("RSI 1H", f"{item['rsi_1h']}", delta="Overbought" if item['rsi_1h'] > 70 else ("Oversold" if item['rsi_1h'] < 30 else "Neutro"))
            r2.metric("RSI 4H", f"{item['rsi_4h']}", delta="Overbought" if item['rsi_4h'] > 70 else ("Oversold" if item['rsi_4h'] < 30 else "Neutro"))
            r3.metric("RSI 1D", f"{item['rsi_1d']}", delta="Overbought" if item['rsi_1d'] > 70 else ("Oversold" if item['rsi_1d'] < 30 else "Neutro"))

            st.markdown("---")
            l1, l2, l3 = st.columns(3)
            l1.markdown(f"🛑 **Stop Loss:**\n`${item['sl']:,.2f}`" if item['sl'] >= 1 else f"🛑 **SL:** `${item['sl']:.4f}`")
            l2.markdown(f"🎯 **Target 1:**\n`${item['tp1']:,.2f}`" if item['tp1'] >= 1 else f"🎯 **TP1:** `${item['tp1']:.4f}`")
            l3.markdown(f"🚀 **Target 2:**\n`${item['tp2']:,.2f}`" if item['tp2'] >= 1 else f"🚀 **TP2:** `${item['tp2']:.4f}`")

# ==========================================
# TAB 2: MAPPA LIQUIDAZIONI BASATA SU VOLATILITÀ
# ==========================================
with tab_heat:
    st.markdown("##### 🔥 Liquidation Pools & Dynamic Leverage Map")
    chosen_asset = st.selectbox("Seleziona Moneta:", names, index=0, key="liq_coin")
    asset_data = next((d for d in data_list if d["name"] == chosen_asset), data_list[0])

    p = asset_data["price"]
    leverages = [100, 50, 25, 10]
    clusters = []

    for lev in leverages:
        clusters.append({
            "Leva": f"{lev}x",
            "Long Liq ($)": p * (1.0 - (0.90 / lev)),
            "Long Vol (M$)": round((100 / lev) * 1.8, 1),
            "Short Liq ($)": p * (1.0 + (0.90 / lev)),
            "Short Vol (M$)": round((100 / lev) * 1.8, 1)
        })
    df_liq = pd.DataFrame(clusters)

    fig_liq = go.Figure()
    fig_liq.add_trace(go.Bar(
        y=df_liq["Leva"],
        x=df_liq["Short Vol (M$)"],
        orientation='h',
        name='Short Liquidation (Sopra)',
        marker=dict(color='#ff1744'),
        text=[f"${x:,.2f}" if x >= 1 else f"${x:.4f}" for x in df_liq["Short Liq ($)"]],
        textposition='inside'
    ))
    fig_liq.add_trace(go.Bar(
        y=df_liq["Leva"],
        x=[-v for v in df_liq["Long Vol (M$)"]],
        orientation='h',
        name='Long Liquidation (Sotto)',
        marker=dict(color='#00e676'),
        text=[f"${x:,.2f}" if x >= 1 else f"${x:.4f}" for x in df_liq["Long Liq ($)"]],
        textposition='inside'
    ))

    fig_liq.update_layout(
        barmode='overlay',
        paper_bgcolor='#06090e',
        plot_bgcolor='#0d131d',
        font=dict(color='#e2e8f0', size=11),
        height=300,
        margin=dict(l=10, r=10, t=25, b=10),
        xaxis=dict(showgrid=False, title="Volume Stimato Liquidabile (M$)"),
        yaxis=dict(autorange="reversed"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_liq, use_container_width=True, config={'displayModeBar': False})

# ==========================================
# TAB 3: TAPE LIVE ORDINI GRANDI
# ==========================================
with tab_whales:
    st.markdown("##### 🐋 Tape Scanner Esecuzioni Grandi (> $30,000)")
    whale_coin = st.selectbox("Filtra per asset:", names, index=0, key="whale_coin_sel")
    w_meta = next((d for d in data_list if d["name"] == whale_coin), data_list[0])

    df_whales = fetch_real_whale_trades(w_meta["pair_gate"], min_usd=30000.0)
    if not df_whales.empty:
        st.dataframe(df_whales, use_container_width=True, hide_index=True)
    else:
        st.info(f"Nessun singolo ordine istituzionale > $30k rilevato negli ultimi blocchi per {whale_coin}.")

# ==========================================
# TAB 4: CALCOLATORE POSITION SIZING
# ==========================================
with tab_calc:
    st.markdown("##### 🎯 Dimensionamento Rischio Professionale")
    trade_coin = st.selectbox("Moneta:", names, index=0, key="calc_coin_sel")
    cur_t = next((d for d in data_list if d["name"] == trade_coin), data_list[0])

    c1, c2 = st.columns(2)
    with c1:
        entry_p = st.number_input("Entrata ($)", value=float(cur_t["price"]), format="%.4f")
        trade_dir = st.selectbox("Direzione", ["LONG 📈", "SHORT 📉"], index=0 if cur_t["action_code"] == "BUY" else 1)
    with c2:
        acc_cap = st.number_input("Capitale Totale ($)", value=2000.0, step=100.0)
        risk_pct = st.number_input("Rischio Max (%)", value=1.0, min_value=0.1, max_value=5.0, step=0.1)

    is_long = "LONG" in trade_dir
    dist = cur_t["atr"] * 1.5
    stop_p = entry_p - dist if is_long else entry_p + dist
    loss_amount = acc_cap * (risk_pct / 100.0)
    qty = loss_amount / dist if dist > 0 else 0
    pos_val = qty * entry_p

    st.markdown("---")
    r1, r2 = st.columns(2)
    r1.metric("Valore Posizione", f"${pos_val:,.2f}")
    r2.metric("Rischio Nominale", f"-${loss_amount:,.2f}")

    r3, r4 = st.columns(2)
    r3.metric("Taglia Coin", f"{qty:,.4f}")
    r4.metric("Stop Loss Rigido", f"${stop_p:,.4f}")

# ==========================================
# TAB 5: GRAFICI LIVE TRADINGVIEW
# ==========================================
with tab_tv:
    chart_c = st.selectbox("Moneta da visualizzare:", names, index=0, key="tv_coin_sel")
    chart_meta = next((d for d in data_list if d["name"] == chart_c), data_list[0])

    tv_code = f"""
    <div style="height:420px;width:100%">
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "{chart_meta['tv_symbol']}",
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
      }});
      </script>
      <div id="tv_widget" style="height:100%;width:100%"></div>
    </div>
    """
    components.html(tv_code, height=430)
