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

# --- CSS DARK INSTITUTIONAL OTTIMIZZATO ---
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

# --- LISTA ASSET TRACCIATI ---
ASSETS = [
    {"name": "BTC", "symbol": "BTCUSDT", "tv_symbol": "BINANCE:BTCUSDT"},
    {"name": "ETH", "symbol": "ETHUSDT", "tv_symbol": "BINANCE:ETHUSDT"},
    {"name": "SOL", "symbol": "SOLUSDT", "tv_symbol": "BINANCE:SOLUSDT"},
    {"name": "NEAR", "symbol": "NEARUSDT", "tv_symbol": "BINANCE:NEARUSDT"},
    {"name": "TAO", "symbol": "TAOUSDT", "tv_symbol": "BINANCE:TAOUSDT"},
    {"name": "WLD", "symbol": "WLDUSDT", "tv_symbol": "BINANCE:WLDUSDT"},
    {"name": "ONDO", "symbol": "ONDOUSDT", "tv_symbol": "BINANCE:ONDOUSDT"},
    {"name": "ZEC", "symbol": "ZECUSDT", "tv_symbol": "BINANCE:ZECUSDT"}
]

HEADERS = {"User-Agent": "Mozilla/5.0"}

# --- INGESTION FEED SPOT & FUTURES IN TEMPO REALE ---
def fetch_binance_klines(symbol: str, interval: str, limit: int = 50):
    """Estrae candele indipendenti per 1h, 4h o 1d direttamente da Binance Spot"""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=2.5).json()
        if isinstance(res, list) and len(res) >= 20:
            df = pd.DataFrame(res, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "number_of_trades",
                "taker_buy_base", "taker_buy_quote", "ignore"
            ])
            for col in ["open", "high", "low", "close", "volume", "quote_asset_volume"]:
                df[col] = df[col].astype(float)
            return df
    except Exception:
        pass
    return None

def fetch_derivatives_data(symbol: str):
    """Recupera Open Interest, Long/Short Ratio e Funding Rate reali dai Futures Binance"""
    data = {"open_interest": 0.0, "long_short_ratio": 1.0, "funding_rate": 0.0}
    try:
        # Open Interest
        oi_res = requests.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}", timeout=2.0).json()
        data["open_interest"] = float(oi_res.get("openInterest", 0.0))
        
        # Funding Rate
        fr_res = requests.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}", timeout=2.0).json()
        data["funding_rate"] = float(fr_res.get("lastFundingRate", 0.0)) * 100

        # Long/Short Account Ratio
        ls_res = requests.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=1h&limit=1", timeout=2.0).json()
        if isinstance(ls_res, list) and len(ls_res) > 0:
            data["long_short_ratio"] = float(ls_res[0].get("longShortRatio", 1.0))
    except Exception:
        pass
    return data

def fetch_real_whale_trades(symbol: str, min_usd: float = 100000.0):
    """Cattura ordini a mercato istituzionali reali (> $100k) dai Futures"""
    trades = []
    try:
        url = f"https://fapi.binance.com/fapi/v1/trades?symbol={symbol}&limit=100"
        res = requests.get(url, headers=HEADERS, timeout=2.5).json()
        if isinstance(res, list):
            for t in res:
                usd_val = float(t["price"]) * float(t["qty"])
                if usd_val >= min_usd:
                    trades.append({
                        "Orario": pd.to_datetime(t["time"], unit="ms").strftime("%H:%M:%S"),
                        "Asset": symbol.replace("USDT", ""),
                        "Tipo": "BUY 🟢" if not t["isBuyerMaker"] else "SELL 🔴",
                        "Prezzo": f"${float(t['price']):,.2f}",
                        "Valore ($)": f"${usd_val:,.0f}",
                        "Taglia": f"{float(t['qty']):,.2f}"
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

def analyze_asset_confluence(item: dict):
    df_1h = fetch_binance_klines(item["symbol"], "1h", 60)
    df_4h = fetch_binance_klines(item["symbol"], "4h", 60)
    df_1d = fetch_binance_klines(item["symbol"], "1d", 60)

    if df_1h is None or len(df_1h) < 25:
        return None

    # Calcolo Multi-TF RSI reale
    rsi_1h = calculate_rsi_series(df_1h["close"])
    rsi_4h = calculate_rsi_series(df_4h["close"]) if df_4h is not None else rsi_1h
    rsi_1d = calculate_rsi_series(df_1d["close"]) if df_1d is not None else rsi_1h

    closes, highs, lows = df_1h["close"], df_1h["high"], df_1h["low"]

    # ATR (14)
    tr = pd.concat([highs - lows, (highs - closes.shift(1)).abs(), (lows - closes.shift(1)).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])

    # Squeeze Indicator
    sma20 = closes.rolling(20).mean()
    std20 = closes.rolling(20).std()
    squeeze_on = bool((sma20 - 2*std20).iloc[-1] > (sma20 - 1.5*atr).iloc[-1] and (sma20 + 2*std20).iloc[-1] < (sma20 + 1.5*atr).iloc[-1])

    # Trend & Slope
    ema7 = closes.ewm(span=7, adjust=False).mean()
    ema25 = closes.ewm(span=25, adjust=False).mean()
    slope = ((ema7.iloc[-1] - ema7.iloc[-4]) / ema7.iloc[-4]) * 100 if len(df_1h) >= 5 else 0.0
    bullish = ema7.iloc[-1] >= ema25.iloc[-1]

    # Dati derivati reali
    derivs = fetch_derivatives_data(item["symbol"])

    # Punteggio Confluenza
    score = 50
    score += 15 if bullish else -15
    score += 10 if slope > 0.4 else (-10 if slope < -0.4 else 0)
    if squeeze_on: score += 10

    # Filtri di salvaguardia Multi-TF & Anti-FOMO
    if rsi_1h >= 75 or rsi_4h >= 75:
        score -= 25  # Blocco categorico per iperestensione
    elif rsi_1h <= 30 and rsi_4h <= 35:
        score += 25
    elif 42 <= rsi_1h <= 60 and bullish:
        score += 15

    score = max(5, min(95, score))

    # Definizione univoca del segnale
    if rsi_1h >= 76:
        action = "⚠️ PRENDI PROFITTO (RSI Esteso)"
        action_code = "TP"
    elif score >= 65 and rsi_1h < 70:
        action = "🟢 ACCUMULA / LONG (Pullback)"
        action_code = "BUY"
    elif score <= 35 and rsi_1h > 30:
        action = "🔴 VENDI / SHORT"
        action_code = "SELL"
    else:
        action = "💤 NEUTRALE / ATTENDI"
        action_code = "NEUTRAL"

    curr_p = float(closes.iloc[-1])

    # Calcolo SL e TP logici in base alla direzione
    if action_code == "SELL":
        sl = curr_p + (1.5 * atr)
        tp1 = curr_p - (2.0 * atr)
        tp2 = curr_p - (3.5 * atr)
    else:  # BUY, TP o NEUTRAL (assumendo bias principale)
        sl = curr_p - (1.5 * atr)
        tp1 = curr_p + (2.0 * atr)
        tp2 = curr_p + (3.5 * atr)

    return {
        "name": item["name"],
        "symbol": item["symbol"],
        "tv_symbol": item["tv_symbol"],
        "price": curr_p,
        "fmt_price": f"${curr_p:,.2f}" if curr_p >= 1 else f"${curr_p:.4f}",
        "rsi_1h": rsi_1h,
        "rsi_4h": rsi_4h,
        "rsi_1d": rsi_1d,
        "atr": atr,
        "slope": slope,
        "squeeze": squeeze_on,
        "score": score,
        "action": action,
        "action_code": action_code,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "support": float(lows.tail(20).min()),
        "resistance": float(highs.tail(20).max()),
        "open_interest": derivs["open_interest"],
        "long_short_ratio": derivs["long_short_ratio"],
        "funding_rate": derivs["funding_rate"],
        "df": df_1h
    }

# --- GENERATORE MAPPA DI LIQUIDAZIONE PONDERATA SULL'OPEN INTEREST ---
def build_oi_liquidation_clusters(current_price: float, atr: float, oi_contracts: float, ls_ratio: float):
    leverages = [100, 50, 25, 10]
    clusters = []
    
    # Ripartizione dell'Open Interest totale su Long e Short in base al ratio
    total_oi_usd = (oi_contracts * current_price) if oi_contracts > 0 else (current_price * 50000)
    long_share = ls_ratio / (1 + ls_ratio)
    short_share = 1.0 - long_share

    for lev in leverages:
        long_liq_price = current_price * (1.0 - (0.90 / lev))
        short_liq_price = current_price * (1.0 + (0.90 / lev))
        
        # Volume stimato esposto a quella determinata fascia di leva
        weight = (100 / lev) / 185.0
        long_vol = (total_oi_usd * long_share * weight) / 1_000_000.0
        short_vol = (total_oi_usd * short_share * weight) / 1_000_000.0

        clusters.append({
            "Leva": f"{lev}x",
            "Long Liq ($)": long_liq_price,
            "Long Vol (M$)": round(long_vol, 2),
            "Short Liq ($)": short_liq_price,
            "Short Vol (M$)": round(short_vol, 2)
        })

    return pd.DataFrame(clusters)

# --- CARICAMENTO GLOBALE ---
@st.cache_data(ttl=20)
def load_all_market_data():
    results = []
    for asset in ASSETS:
        res = analyze_asset_confluence(asset)
        if res is not None:
            results.append(res)
    return results

data_list = load_all_market_data()
fng_score, fng_sentiment = fetch_fear_and_greed()
avg_score = int(np.mean([x["score"] for x in data_list])) if data_list else 50

# --- HEADER STATS ---
st.markdown("### ⚡ Apex Terminal Pro")
k1, k2, k3 = st.columns(3)
k1.metric("Fear & Greed", f"{fng_score}/100", delta=fng_sentiment, delta_color="off")
k2.metric("Market Bias", f"{avg_score}/100", delta="BULLISH" if avg_score >= 50 else "BEARISH")
sqz_count = sum(1 for x in data_list if x["squeeze"])
k3.metric("Squeeze 1h", f"{sqz_count} Attivi", delta="Espansione Imminente" if sqz_count > 0 else "Neutro", delta_color="inverse" if sqz_count > 0 else "normal")

# --- TAB TOUCH-FRIENDLY ---
tab_radar, tab_heat, tab_whales, tab_calc, tab_tv = st.tabs([
    "⚡ Segnali & Multi-TF",
    "🔥 Mappe Liquidazione",
    "🐋 Scanner Balene (Live)",
    "🎯 Calcola Trade",
    "📈 TradingView Live"
])

# ==========================================
# TAB 1: RADAR MULTI-TIMEFRAME REALE
# ==========================================
with tab_radar:
    col_filter = st.radio("Filtra per:", ["Tutti", "🟢 Long Setup", "⚠️ Prendi Profitto / Short"], horizontal=True)

    for item in data_list:
        if col_filter == "🟢 Long Setup" and item["action_code"] != "BUY":
            continue
        if col_filter == "⚠️ Prendi Profitto / Short" and item["action_code"] not in ["TP", "SELL"]:
            continue

        with st.container(border=True):
            h1, h2 = st.columns([3, 2])
            h1.markdown(f"### {item['name']}/USDT")
            h2.markdown(f"<h3 style='text-align:right;color:#00e5ff;'>{item['fmt_price']}</h3>", unsafe_allow_html=True)

            st.markdown(f"**Segnale:** `{item['action']}` | **Score:** `{item['score']}/100`")
            if item["squeeze"]:
                st.warning("⚡ **Squeeze Attivo:** Compressione Bande/Keltner rilevata su 1H.")

            # Dati RSI 100% indipendenti
            st.markdown("**RSI Multi-Timeframe (Feed Binance):**")
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
# TAB 2: MAPPA LIQUIDAZIONI BASATA SU OPEN INTEREST
# ==========================================
with tab_heat:
    st.markdown("##### 🔥 Liquidation Pools & Open Interest Heatmap")
    names = [d["name"] for d in data_list]
    chosen_asset = st.selectbox("Seleziona Moneta:", names, index=0)
    asset_data = next(d for d in data_list if d["name"] == chosen_asset)

    m1, m2, m3 = st.columns(3)
    m1.metric("Long/Short Ratio", f"{asset_data['long_short_ratio']:.2f}")
    m2.metric("Funding Rate 8h", f"{asset_data['funding_rate']:.4f}%")
    m3.metric("Open Interest", f"{asset_data['open_interest']:,.0f} Contratti")

    df_liq = build_oi_liquidation_clusters(
        asset_data["price"], 
        asset_data["atr"], 
        asset_data["open_interest"], 
        asset_data["long_short_ratio"]
    )

    fig_liq = go.Figure()
    fig_liq.add_trace(go.Bar(
        y=df_liq["Leva"],
        x=df_liq["Short Vol (M$)"],
        orientation='h',
        name='Short Liquidation (Sopra)',
        marker=dict(color='#ff1744'),
        text=[f"${p:,.2f}" if p >= 1 else f"${p:.4f}" for p in df_liq["Short Liq ($)"]],
        textposition='inside'
    ))
    fig_liq.add_trace(go.Bar(
        y=df_liq["Leva"],
        x=[-v for v in df_liq["Long Vol (M$)"]],
        orientation='h',
        name='Long Liquidation (Sotto)',
        marker=dict(color='#00e676'),
        text=[f"${p:,.2f}" if p >= 1 else f"${p:.4f}" for p in df_liq["Long Liq ($)"]],
        textposition='inside'
    ))

    fig_liq.update_layout(
        title=f"Zone di Caccia alla Liquidità ({chosen_asset})",
        barmode='overlay',
        paper_bgcolor='#06090e',
        plot_bgcolor='#0d131d',
        font=dict(color='#e2e8f0', size=11),
        height=320,
        margin=dict(l=10, r=10, t=35, b=15),
        xaxis=dict(showgrid=False, title="Volume Stimato Liquidabile (M$)"),
        yaxis=dict(autorange="reversed"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_liq, use_container_width=True, config={'displayModeBar': False})

# ==========================================
# TAB 3: SCANNER ORDINI BALENE IN TEMPO REALE
# ==========================================
with tab_whales:
    st.markdown("##### 🐋 Tape Scanner Grandi Contratti (> $100,000)")
    whale_coin = st.selectbox("Filtra per asset:", names, index=0, key="whale_sel")
    w_sym = next(d["symbol"] for d in data_list if d["name"] == whale_coin)
    
    df_whales = fetch_real_whale_trades(w_sym, min_usd=100000.0)
    if not df_whales.empty:
        st.dataframe(df_whales, use_container_width=True, hide_index=True)
    else:
        st.info("Nessun singolo ordine istituzionale > $100k registrato negli ultimi blocchi.")

# ==========================================
# TAB 4: CALCOLATORE DI POSIZIONE
# ==========================================
with tab_calc:
    st.markdown("##### 🎯 Dimensionamento Rischio Professionale")
    trade_coin = st.selectbox("Seleziona Moneta:", names, index=0, key="calc_select")
    cur_t = next(d for d in data_list if d["name"] == trade_coin)

    c1, c2 = st.columns(2)
    with c1:
        entry_p = st.number_input("Prezzo Entrata ($)", value=float(cur_t["price"]), format="%.4f")
        trade_dir = st.selectbox("Direzione", ["LONG 📈", "SHORT 📉"], index=0 if cur_t["action_code"] == "BUY" else 1)
    with c2:
        acc_cap = st.number_input("Capitale Totale ($)", value=2000.0, step=100.0)
        risk_pct = st.number_input("Rischio Max per Trade (%)", value=1.0, min_value=0.1, max_value=5.0, step=0.1)

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
    r3.metric("Quantità Coin", f"{qty:,.4f}")
    r4.metric("Stop Loss Rigido", f"${stop_p:,.4f}")

# ==========================================
# TAB 5: GRAFICI LIVE TRADINGVIEW
# ==========================================
with tab_tv:
    chart_c = st.selectbox("Visualizza Grafico:", names, index=0, key="tv_select")
    chart_meta = next(d for d in data_list if d["name"] == chart_c)

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
