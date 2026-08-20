import time
import requests
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# --- CONFIGURAZIONE STREAMLIT ---
st.set_page_config(
    page_title="Apex Institutional Terminal Pro",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed"
)

# --- CSS DARK INSTITUTIONAL OTTIMIZZATO SMARTPHONE ---
st.markdown("""
<style>
    .stApp { background-color: #080c14; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .block-container {
        padding-top: 0.6rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.1rem !important;
        color: #00f2fe !important;
        font-weight: 800;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.72rem !important;
        color: #94a3b8 !important;
        font-weight: 600;
    }
    .stTabs [data-baseweb="tab-list"] {
        display: flex;
        overflow-x: auto;
        white-space: nowrap;
        gap: 6px;
        padding-bottom: 8px;
        border-bottom: 1px solid #1e293b;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #0f172a;
        border-radius: 6px;
        color: #94a3b8;
        padding: 6px 10px;
        font-size: 0.78rem;
        font-weight: 700;
        border: 1px solid #1e293b;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e293b !important;
        color: #00f2fe !important;
        border: 1px solid #00f2fe !important;
    }
    .card-asset {
        background: linear-gradient(145deg, #0d1527, #090e1a);
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# --- ASSET TRACKER BINANCE PAIRS ---
ASSETS = [
    {"name": "BTC", "pair": "BTCUSDT", "tv": "BINANCE:BTCUSDT"},
    {"name": "ETH", "pair": "ETHUSDT", "tv": "BINANCE:ETHUSDT"},
    {"name": "SOL", "pair": "SOLUSDT", "tv": "BINANCE:SOLUSDT"},
    {"name": "NEAR", "pair": "NEARUSDT", "tv": "BINANCE:NEARUSDT"},
    {"name": "TAO", "pair": "TAOUSDT", "tv": "BINANCE:TAOUSDT"},
    {"name": "WLD", "pair": "WLDUSDT", "tv": "BINANCE:WLDUSDT"},
    {"name": "ONDO", "pair": "ONDOUSDT", "tv": "BINANCE:ONDOUSDT"},
    {"name": "ZEC", "pair": "ZECUSDT", "tv": "BINANCE:ZECUSDT"}
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# --- FUNZIONI FORMATTAZIONE INTELLIGENTE ---
def fmt_price(p: float) -> str:
    if p >= 1000:
        return f"${p:,.0f}"
    elif p >= 1:
        return f"${p:,.2f}"
    else:
        return f"${p:.4f}"

# --- MOTORE DI CALCOLO INDICATORI ---
def compute_rsi(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 1:
        return 50.0
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = float(rsi.iloc[-1])
    return round(val, 1) if not np.isnan(val) else 50.0

def fetch_binance_klines(symbol: str, interval: str, limit: int = 40) -> pd.DataFrame:
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        r = requests.get(url, headers=HEADERS, timeout=2.0)
        if r.status_code == 200:
            raw = r.json()
            df = pd.DataFrame(raw, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "trades", "tb_base", "tb_quote", "ignore"
            ])
            for c in ["open", "high", "low", "close", "volume"]:
                df[c] = df[c].astype(float)
            return df
    except Exception:
        pass
    return pd.DataFrame()

def analyze_asset_complete(asset: dict):
    pair = asset["pair"]
    
    # Download parallelo 1H, 4H, 1D da Binance
    df_1h = fetch_binance_klines(pair, "1h", 45)
    df_4h = fetch_binance_klines(pair, "4h", 30)
    df_1d = fetch_binance_klines(pair, "1d", 30)

    if df_1h.empty:
        return None

    curr_price = float(df_1h["close"].iloc[-1])
    
    # RSI Multi-Timeframe reali
    rsi_1h = compute_rsi(df_1h["close"])
    rsi_4h = compute_rsi(df_4h["close"]) if not df_4h.empty else rsi_1h
    rsi_1d = compute_rsi(df_1d["close"]) if not df_1d.empty else rsi_4h

    # ATR (14) su 1H
    highs, lows, closes = df_1h["high"], df_1h["low"], df_1h["close"]
    tr = pd.concat([highs - lows, (highs - closes.shift(1)).abs(), (lows - closes.shift(1)).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1]) if len(df_1h) >= 14 else float(curr_price * 0.015)
    if np.isnan(atr) or atr <= 0:
        atr = curr_price * 0.015

    # TTM Squeeze Momentum (Bollinger Bands vs Keltner Channels)
    sma20 = closes.rolling(20).mean()
    std20 = closes.rolling(20).std()
    bb_upper = sma20 + (2.0 * std20)
    bb_lower = sma20 - (2.0 * std20)
    
    kc_upper = sma20 + (1.5 * atr)
    kc_lower = sma20 - (1.5 * atr)

    squeeze_active = bool((bb_lower.iloc[-1] > kc_lower.iloc[-1]) and (bb_upper.iloc[-1] < kc_upper.iloc[-1])) if len(df_1h) >= 20 else False

    # Trend Direction (EMA 9 vs EMA 21)
    ema9 = closes.ewm(span=9, adjust=False).mean().iloc[-1]
    ema21 = closes.ewm(span=21, adjust=False).mean().iloc[-1]
    trend_bull = ema9 >= ema21

    # 24h Change stimata da 1D o 1H
    open_24h = df_1d["open"].iloc[-1] if not df_1d.empty else df_1h["open"].iloc[0]
    pct_24h = ((curr_price - open_24h) / open_24h) * 100

    # Algoritmo Scoring Istituzionale (0-100)
    score = 50
    score += 18 if trend_bull else -18
    score += 10 if squeeze_active else 0
    if rsi_1h <= 35: score += 20
    elif rsi_1h >= 75: score -= 25
    elif 45 <= rsi_1h <= 62 and trend_bull: score += 12
    score = max(5, min(95, score))

    if rsi_1h >= 75:
        action = "⚠️ PRENDI PROFITTO"
        action_code = "TP"
        badge_color = "#ff9100"
    elif score >= 62 and rsi_1h < 70:
        action = "🟢 ACCUMULA / LONG"
        action_code = "BUY"
        badge_color = "#00e676"
    elif score <= 38 and rsi_1h > 30:
        action = "🔴 DISTRIBUISCI / SHORT"
        action_code = "SELL"
        badge_color = "#ff1744"
    else:
        action = "💤 NEUTRALE / ATTENDI"
        action_code = "NEUTRAL"
        badge_color = "#94a3b8"

    # Livelli Operativi Calcolati con ATR
    if action_code == "SELL":
        sl = curr_price + (1.5 * atr)
        tp1 = curr_price - (2.0 * atr)
        tp2 = curr_price - (3.8 * atr)
    else:
        sl = curr_price - (1.5 * atr)
        tp1 = curr_price + (2.0 * atr)
        tp2 = curr_price + (3.8 * atr)

    return {
        "name": asset["name"],
        "pair": asset["pair"],
        "tv": asset["tv"],
        "price": curr_price,
        "pct_24h": pct_24h,
        "rsi_1h": rsi_1h,
        "rsi_4h": rsi_4h,
        "rsi_1d": rsi_1d,
        "atr": atr,
        "squeeze": squeeze_active,
        "score": score,
        "action": action,
        "action_code": action_code,
        "badge_color": badge_color,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2
    }

# --- TAPE REALE ORDINI ISTITUZIONALI BINANCE ---
def fetch_binance_whale_trades(pair: str, min_usd: float = 15000.0):
    try:
        url = f"https://api.binance.com/api/v3/aggTrades?symbol={pair}&limit=80"
        res = requests.get(url, headers=HEADERS, timeout=2.0).json()
        trades = []
        if isinstance(res, list):
            for t in reversed(res):
                p = float(t["p"])
                q = float(t["q"])
                val = p * q
                if val >= min_usd:
                    trades.append({
                        "Ora": pd.to_datetime(t["T"], unit="ms").strftime("%H:%M:%S"),
                        "Tipo": "BUY 🟢" if not t["m"] else "SELL 🔴",
                        "Prezzo": fmt_price(p),
                        "Controvalore": f"${val:,.0f}",
                        "Quantità": f"{q:,.2f}"
                    })
        return pd.DataFrame(trades)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_fear_and_greed():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=2.0).json()
        item = res["data"][0]
        return int(item["value"]), item["value_classification"]
    except Exception:
        return 50, "Neutral"

# --- ESECUZIONE MULTI-THREADING DATI ---
@st.cache_data(ttl=15)
def load_all_market_intelligence():
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(analyze_asset_complete, ASSETS))
    return [r for r in results if r is not None]

data_market = load_all_market_intelligence()
fng_val, fng_label = fetch_fear_and_greed()

if not data_market:
    st.error("Connessione ai nodi Binance in corso... Ricarica tra qualche secondo.")
    st.stop()

avg_bias = int(np.mean([x["score"] for x in data_market]))
names_list = [d["name"] for d in data_market]

# --- TOP SUMMARY BAR ---
st.markdown("### ⚡ Apex Terminal Pro")
k1, k2, k3 = st.columns(3)
k1.metric("Fear & Greed", f"{fng_val}/100", delta=fng_label, delta_color="off")
k2.metric("Market Bias", f"{avg_bias}/100", delta="BULLISH" if avg_bias >= 50 else "BEARISH")
sqz_total = sum(1 for x in data_market if x["squeeze"])
k3.metric("Squeeze 1H", f"{sqz_total} Attivi", delta="Espansione" if sqz_total > 0 else "Neutro")

# --- NAVIGAZIONE SCHEDE ---
t_signals, t_heat, t_whales, t_calc, t_tv = st.tabs([
    "⚡ Segnali & Multi-TF",
    "🔥 Liquidity Cascades",
    "🐋 Tape Balene Live",
    "🎯 Risk & Position",
    "📈 TradingView Live"
])

# ==========================================
# TAB 1: RADAR SEGNALI MULTI-TF
# ==========================================
with t_signals:
    filter_choice = st.radio("Filtra per:", ["Tutti", "🟢 Solo Long", "⚠️ Solo TP/Short"], horizontal=True)

    for item in data_market:
        if filter_choice == "🟢 Solo Long" and item["action_code"] != "BUY":
            continue
        if filter_choice == "⚠️ Solo TP/Short" and item["action_code"] not in ["TP", "SELL"]:
            continue

        pct_color = "#00e676" if item["pct_24h"] >= 0 else "#ff1744"

        st.markdown(f"""
        <div class="card-asset">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:1.1rem; font-weight:800;">{item['name']}/USDT</span>
                <span style="font-size:1.1rem; font-weight:800; color:#00f2fe;">{fmt_price(item['price'])} 
                    <span style="font-size:0.75rem; color:{pct_color};">({item['pct_24h']:+.2f}%)</span>
                </span>
            </div>
            <div style="margin-top:6px; font-size:0.85rem;">
                <span style="color:{item['badge_color']}; font-weight:700;">{item['action']}</span> 
                <span style="color:#64748b; margin-left:8px;">| Institutional Score: <b>{item['score']}/100</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if item["squeeze"]:
            st.warning(f"⚡ **TTM Squeeze 1H Attivo su {item['name']}:** Compressione bande rilevata. Movimento direzionale imminente.")

        # Metriche RSI Multi-Timeframe
        m1, m2, m3 = st.columns(3)
        m1.metric("RSI 1H", f"{item['rsi_1h']}")
        m2.metric("RSI 4H", f"{item['rsi_4h']}")
        m3.metric("RSI 1D", f"{item['rsi_1d']}")

        # Livelli Operativi
        l1, l2, l3 = st.columns(3)
        l1.markdown(f"🛑 **SL:** `{fmt_price(item['sl'])}`")
        l2.markdown(f"🎯 **TP1:** `{fmt_price(item['tp1'])}`")
        l3.markdown(f"🚀 **TP2:** `{fmt_price(item['tp2'])}`")
        st.markdown("---")

# ==========================================
# TAB 2: MAPPA LIQUIDAZIONI & CASCADE
# ==========================================
with t_heat:
    st.markdown("##### 🔥 Liquidation Cascades (Dinamica su Prezzo Spot)")
    c_liq = st.selectbox("Seleziona Moneta:", names_list, index=0, key="liq_coin_select")
    m_liq = next(d for d in data_market if d["name"] == c_liq)

    p_liq = m_liq["price"]
    levs = [100, 50, 25, 10]
    liq_records = []

    for lev in levs:
        long_liq = p_liq * (1.0 - (0.90 / lev))
        short_liq = p_liq * (1.0 + (0.90 / lev))
        depth = round((100 / lev) * 2.2, 1)
        liq_records.append({"Leva": f"{lev}x", "Long_Price": long_liq, "Short_Price": short_liq, "Volume": depth})

    df_l = pd.DataFrame(liq_records)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df_l["Leva"],
        x=df_l["Volume"],
        orientation='h',
        name='Short Liquidations (Sopra)',
        marker=dict(color='#ff1744'),
        text=[fmt_price(x) for x in df_l["Short_Price"]],
        textposition='inside'
    ))
    fig.add_trace(go.Bar(
        y=df_l["Leva"],
        x=[-v for v in df_l["Volume"]],
        orientation='h',
        name='Long Liquidations (Sotto)',
        marker=dict(color='#00e676'),
        text=[fmt_price(x) for x in df_l["Long_Price"]],
        textposition='inside'
    ))

    fig.update_layout(
        barmode='overlay',
        paper_bgcolor='#080c14',
        plot_bgcolor='#0f172a',
        font=dict(color='#f1f5f9', size=11),
        height=280,
        margin=dict(l=5, r=5, t=15, b=5),
        xaxis=dict(showgrid=False, title="Volatilità / Rischio Cascade (M$)"),
        yaxis=dict(autorange="reversed"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# ==========================================
# TAB 3: TAPE LIVE ORDINI GRANDI (> $15k)
# ==========================================
with t_whales:
    st.markdown("##### 🐋 Whale Order Tape (Esecuzioni Binance Live > $15,000)")
    w_coin = st.selectbox("Asset:", names_list, index=0, key="tape_coin_sel")
    w_meta = next(d for d in data_market if d["name"] == w_coin)

    df_tape = fetch_binance_whale_trades(w_meta["pair"], min_usd=15000.0)
    if not df_tape.empty:
        st.dataframe(df_tape, use_container_width=True, hide_index=True)
    else:
        st.info(f"Nessun singolo blocco istituzionale > $15k scambiato negli ultimissimi secondi su {w_coin}.")

# ==========================================
# TAB 4: POSITION SIZING INTELLIGENTE
# ==========================================
with t_calc:
    st.markdown("##### 🎯 Calcolo Rischio e Taglia Posizione")
    calc_c = st.selectbox("Asset Operativo:", names_list, index=0, key="calc_select_c")
    calc_meta = next(d for d in data_market if d["name"] == calc_c)

    c_cap, c_risk = st.columns(2)
    with c_cap:
        capital = st.number_input("Capitale Conto ($)", min_value=100.0, value=2000.0, step=250.0)
    with c_risk:
        risk_percent = st.slider("Rischio % per Trade", min_value=0.5, max_value=5.0, value=1.0, step=0.5)

    direction = st.radio("Direzione:", ["LONG 📈", "SHORT 📉"], horizontal=True, index=0 if calc_meta["action_code"] == "BUY" else 1)

    entry = calc_meta["price"]
    dist_sl = calc_meta["atr"] * 1.5
    stop_calc = entry - dist_sl if "LONG" in direction else entry + dist_sl

    max_loss_usd = capital * (risk_percent / 100.0)
    position_coins = max_loss_usd / dist_sl if dist_sl > 0 else 0
    total_pos_value = position_coins * entry

    st.markdown("---")
    r1, r2 = st.columns(2)
    r1.metric("Valore Posizione Nominale", f"${total_pos_value:,.2f}")
    r2.metric("Rischio Max Accettato", f"-${max_loss_usd:,.2f}")

    r3, r4 = st.columns(2)
    r3.metric("Quantità Coin", f"{position_coins:,.4f} {calc_c}")
    r4.metric("Stop Loss Consigliato", fmt_price(stop_calc))

# ==========================================
# TAB 5: TRADINGVIEW LIVE
# ==========================================
with t_tv:
    tv_c = st.selectbox("Grafico Live da Aprire:", names_list, index=0, key="tv_select")
    tv_meta = next(d for d in data_market if d["name"] == tv_c)

    tv_widget_html = f"""
    <div style="height:440px;width:100%">
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "{tv_meta['tv']}",
        "interval": "60",
        "timezone": "Europe/Rome",
        "theme": "dark",
        "style": "1",
        "locale": "it",
        "toolbar_bg": "#080c14",
        "enable_publishing": false,
        "hide_top_toolbar": false,
        "hide_side_toolbar": true,
        "save_image": false,
        "container_id": "tv_chart"
      }});
      </script>
      <div id="tv_chart" style="height:100%;width:100%"></div>
    </div>
    """
    components.html(tv_widget_html, height=450)
