import os
import textwrap
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# --- CONFIGURAZIONE ULTRA-MOBILE ---
st.set_page_config(
    page_title="Apex Mobile Terminal",
    layout="wide",
    page_icon="📱",
    initial_sidebar_state="collapsed"
)

# --- CSS RESPONSIVE SPECIALIZZATO PER SMARTPHONE ---
st.markdown("""
<style>
    .stApp { background-color: #070b11; color: #e2e8f0; }
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 3.5rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100% !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        display: flex;
        overflow-x: auto;
        white-space: nowrap;
        gap: 6px;
        padding-bottom: 6px;
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
    div[data-testid="stMetricValue"] {
        font-size: 1.15rem !important;
        color: #00e5ff !important;
    }
    div[data-testid="stMetricLabel"] { font-size: 0.72rem !important; }
    .stButton>button {
        width: 100% !important;
        min-height: 44px !important;
        font-weight: bold;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- GESTIONE NOTIFICHE (NTFY & TELEGRAM) ---
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

# --- LISTA ASSET ---
ASSETS = [
    {"name": "BTC", "pair_full": "BTC/USDC", "cb_pair": "BTC-USD", "tv_symbol": "BINANCE:BTCUSDT"},
    {"name": "ETH", "pair_full": "ETH/USDC", "cb_pair": "ETH-USD", "tv_symbol": "BINANCE:ETHUSDT"},
    {"name": "SOL", "pair_full": "SOL/USDC", "cb_pair": "SOL-USD", "tv_symbol": "BINANCE:SOLUSDT"},
    {"name": "NEAR", "pair_full": "NEAR/USDC", "cb_pair": "NEAR-USD", "tv_symbol": "BINANCE:NEARUSDT"},
    {"name": "TAO", "pair_full": "TAO/USDT", "cb_pair": "TAO-USD", "tv_symbol": "BINANCE:TAOUSDT"},
    {"name": "WLD", "pair_full": "WLD/USDC", "cb_pair": "WLD-USD", "tv_symbol": "BINANCE:WLDUSDT"},
    {"name": "ONDO", "pair_full": "ONDO/USDT", "cb_pair": "ONDO-USD", "tv_symbol": "BINANCE:ONDOUSDT"},
    {"name": "ZEC", "pair_full": "ZEC/USDT", "cb_pair": "ZEC-USD", "tv_symbol": "BINANCE:ZECUSDT"},
    {"name": "HYPE", "pair_full": "HYPE/USDT", "cb_pair": "HYPE-USD", "tv_symbol": "BYBIT:HYPEUSDT"}
]

HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_crypto_candles(cb_pair: str, symbol: str):
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
def get_fng_index():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=2.0).json()
        d = res["data"][0]
        return int(d["value"]), d["value_classification"]
    except Exception:
        return 50, "Neutral"

# --- ANALISI QUANTITATIVA PREDITTIVA ---
def calculate_quant_signals(df: pd.DataFrame):
    closes, highs, lows, vols = df["close"], df["high"], df["low"], df["volumeto"]

    # RSI (14)
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_val = round(float((100 - (100 / (1 + rs))).iloc[-1]), 1)

    # ATR (14)
    tr = pd.concat([highs - lows, (highs - closes.shift(1)).abs(), (lows - closes.shift(1)).abs()], axis=1).max(axis=1)
    atr_val = float(tr.rolling(14).mean().iloc[-1])

    # Squeeze
    sma20 = closes.rolling(20).mean()
    std20 = closes.rolling(20).std()
    bb_u, bb_l = sma20 + (2.0 * std20), sma20 - (2.0 * std20)
    kc_u, kc_l = sma20 + (1.5 * tr.rolling(14).mean()), sma20 - (1.5 * tr.rolling(14).mean())
    is_squeeze = bool(bb_l.iloc[-1] > kc_l.iloc[-1] and bb_u.iloc[-1] < kc_u.iloc[-1])

    # Trend & Slope
    ema7 = closes.ewm(span=7, adjust=False).mean()
    ema25 = closes.ewm(span=25, adjust=False).mean()
    slope = ((ema7.iloc[-1] - ema7.iloc[-4]) / ema7.iloc[-4]) * 100 if len(df) >= 5 else 0.0
    bull_trend = ema7.iloc[-1] > ema25.iloc[-1]

    # Z-Score
    vol_mean, vol_std = vols.tail(20).mean(), vols.tail(20).std()
    z_score = (vols.iloc[-1] - vol_mean) / vol_std if vol_std > 0 else 0.0

    # Calcolo Confluenza
    score = 50
    if rsi_val < 32: score += 18
    elif rsi_val > 68: score -= 18
    if bull_trend: score += 12
    else: score -= 12
    if is_squeeze: score += 10
    if slope > 0.15: score += 10
    elif slope < -0.15: score -= 10
    score = max(5, min(95, score))

    grade = "GRADE A+" if score >= 75 else ("GRADE A" if score >= 60 else ("GRADE A- (SHORT)" if score <= 25 else "GRADE B"))
    
    # Segnale Operativo
    if score >= 65 or (score >= 55 and bull_trend):
        action = "🟢 BUY / LONG"
        action_type = "LONG"
    elif score <= 35 or (score <= 45 and not bull_trend):
        action = "🔴 SELL / SHORT"
        action_type = "SHORT"
    else:
        action = "💤 ATTESA BREAKOUT"
        action_type = "NEUTRAL"

    df["ema7"], df["ema25"] = ema7, ema25
    return {
        "rsi": rsi_val, "atr": atr_val, "squeeze": is_squeeze,
        "bull": bull_trend, "slope": slope, "vol_z": z_score,
        "score": score, "grade": grade, "action": action, "action_type": action_type,
        "support": float(lows.tail(20).min()),
        "resistance": float(highs.tail(20).max()),
        "df": df
    }

@st.cache_data(ttl=25)
def get_mobile_dataset():
    records = []
    for item in ASSETS:
        raw_df = get_crypto_candles(item["cb_pair"], item["name"])
        if raw_df is None or len(raw_df) < 25:
            continue
        q = calculate_quant_signals(raw_df)
        curr_p = float(q["df"]["close"].iloc[-1])
        records.append({
            "name": item["name"],
            "full_name": item["pair_full"],
            "tv_symbol": item["tv_symbol"],
            "price": curr_p,
            "fmt_price": f"${curr_p:,.2f}" if curr_p >= 1 else f"${curr_p:.4f}",
            "rsi": q["rsi"],
            "atr": q["atr"],
            "slope": q["slope"],
            "vol_z": q["vol_z"],
            "score": q["score"],
            "grade": q["grade"],
            "action": q["action"],
            "action_type": q["action_type"],
            "squeeze": q["squeeze"],
            "bull": q["bull"],
            "support": q["support"],
            "resistance": q["resistance"],
            "df": q["df"]
        })
    return records

data_records = get_mobile_dataset()
fng_val, fng_text = get_fng_index()

# --- BARRA KPI MOBILE ---
avg_score = int(np.mean([x["score"] for x in data_records])) if data_records else 50
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("F&G Index", f"{fng_val}/100")
with col2:
    st.metric("Apex Score", f"{avg_score}/100")
with col3:
    sqz_cnt = sum(1 for x in data_records if x["squeeze"])
    st.metric("Squeeze", f"{sqz_cnt} Attivi")

tab_radar, tab_calc, tab_chart, tab_night = st.tabs([
    "⚡ Segnali & Radar",
    "🎯 Calcola Trade",
    "📈 Grafici TV",
    "🌙 Modulo Notte"
])

# ==========================================
# TAB 1: RADAR & CARTE ASSET SENZA BUG
# ==========================================
with tab_radar:
    filter_choice = st.radio("Filtro:", ["Tutti", "🟢 Solo Buy/Long", "🔴 Solo Sell/Short", "⚡ Solo Squeeze"], horizontal=True)

    for item in data_records:
        if filter_choice == "🟢 Solo Buy/Long" and item["action_type"] != "LONG":
            continue
        if filter_choice == "🔴 Solo Sell/Short" and item["action_type"] != "SHORT":
            continue
        if filter_choice == "⚡ Solo Squeeze" and not item["squeeze"]:
            continue

        trend_color = "#00e676" if item["bull"] else "#ff1744"
        trend_txt = "BULLISH" if item["bull"] else "BEARISH"
        sqz_badge = '<span style="background:rgba(0,229,255,0.15);color:#00e5ff;padding:2px 6px;border-radius:4px;border:1px solid #00e5ff;font-size:0.68rem;font-weight:800;">⚡ SQUEEZE</span>' if item["squeeze"] else ''

        # HTML privo di indentazione spuria per evitare il blocco markdown
        card_html = textwrap.dedent(f"""
        <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:10px;margin-bottom:8px;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:1.05rem;font-weight:800;color:#fff;">{item['full_name']}</span>
                <span style="font-size:1.1rem;font-weight:800;color:#00e5ff;">{item['fmt_price']}</span>
            </div>
            <div style="display:flex;gap:6px;margin:5px 0;">
                <span style="background:{trend_color}22;color:{trend_color};padding:2px 6px;border-radius:4px;border:1px solid {trend_color};font-size:0.68rem;font-weight:800;">{trend_txt}</span>
                <span style="background:rgba(255,145,0,0.15);color:#ff9100;padding:2px 6px;border-radius:4px;border:1px solid #ff9100;font-size:0.68rem;font-weight:800;">{item['grade']}</span>
                {sqz_badge}
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;font-size:0.75rem;color:#94a3b8;background:#070b11;padding:6px;border-radius:6px;margin:6px 0;">
                <div>RSI: <b style="color:#fff;">{item['rsi']}</b></div>
                <div>Slope: <b style="color:#fff;">{item['slope']:+.2f}%</b></div>
                <div>Vol Z: <b style="color:#fff;">{item['vol_z']:+.1f}σ</b></div>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;font-size:0.85rem;margin-top:4px;">
                <span>Segnale: <b>{item['action']}</b></span>
                <span style="color:#00e5ff;font-weight:700;">Score: {item['score']}/100</span>
            </div>
        </div>
        """)
        st.markdown(card_html, unsafe_allow_html=True)

# ==========================================
# TAB 2: CALCOLA TRADE E LIVELLI OPERATIVI
# ==========================================
with tab_calc:
    st.markdown("##### 🎯 Dimensionamento Rischio & Livelli")
    asset_list = [d["name"] for d in data_records]
    chosen_symbol = st.selectbox("Seleziona Moneta:", asset_list, index=0)
    cur = next(d for d in data_records if d["name"] == chosen_symbol)

    c_in1, c_in2 = st.columns(2)
    with c_in1:
        entry_val = st.number_input("Entry Price ($)", value=float(cur["price"]), format="%.4f")
        trade_dir = st.selectbox("Direzione", ["LONG 📈", "SHORT 📉"], index=0 if cur["bull"] else 1)
    with c_in2:
        acc_val = st.number_input("Capitale ($)", value=2000.0, step=250.0)
        risk_p = st.number_input("Rischio Max (%)", value=1.0, min_value=0.2, max_value=5.0, step=0.1)

    is_l = "LONG" in trade_dir
    dist = cur["atr"] * 1.5
    sl_val = entry_val - dist if is_l else entry_val + dist
    loss_usd = acc_val * (risk_p / 100.0)
    pos_qty = loss_usd / dist if dist > 0 else 0
    pos_usd = pos_qty * entry_val

    st.markdown("---")
    r1, r2 = st.columns(2)
    r1.metric("Size Posizione", f"${pos_usd:,.2f}")
    r2.metric("Perdita Max a SL", f"-${loss_usd:,.2f}")

    r3, r4 = st.columns(2)
    r3.metric("Quantità Coin", f"{pos_qty:,.4f}")
    r4.metric("Stop Loss Rigido", f"${sl_val:,.4f}")

    st.markdown("##### 🎯 Target di Uscita Scalettati")
    t1 = entry_val + (dist * 1.5) if is_l else entry_val - (dist * 1.5)
    t2 = entry_val + (dist * 2.5) if is_l else entry_val - (dist * 2.5)
    t3 = entry_val + (dist * 4.0) if is_l else entry_val - (dist * 4.0)

    tp_table = pd.DataFrame([
        {"Target": "🎯 TP1 (50%)", "R:R": "1 : 1.5", "Prezzo": f"${t1:,.4f}", "Profitto": f"+${loss_usd * 1.5:,.2f}"},
        {"Target": "🎯 TP2 (30%)", "R:R": "1 : 2.5", "Prezzo": f"${t2:,.4f}", "Profitto": f"+${loss_usd * 2.5:,.2f}"},
        {"Target": "🚀 TP3 (20%)", "R:R": "1 : 4.0", "Prezzo": f"${t3:,.4f}", "Profitto": f"+${loss_usd * 4.0:,.2f}"}
    ])
    st.dataframe(tp_table, use_container_width=True, hide_index=True)

# ==========================================
# TAB 3: PRO CHART TRADINGVIEW MOBILE
# ==========================================
with tab_chart:
    st.markdown("##### 📈 Grafico Interattivo")
    chosen_chart = st.selectbox("Asset Grafico:", asset_list, index=0, key="chart_picker")
    chart_item = next(d for d in data_records if d["name"] == chosen_chart)

    tv_mobile_html = f"""
    <div style="height:360px;width:100%">
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "autosize": true,
        "symbol": "{chart_item['tv_symbol']}",
        "interval": "60",
        "timezone": "Europe/Rome",
        "theme": "dark",
        "style": "1",
        "locale": "it",
        "toolbar_bg": "#0f172a",
        "enable_publishing": false,
        "hide_top_toolbar": false,
        "hide_side_toolbar": true,
        "save_image": false,
        "container_id": "tv_chart_box"
      }}
      );
      </script>
      <div id="tv_chart_box" style="height:100%;width:100%"></div>
    </div>
    """
    components.html(tv_mobile_html, height=370)

# ==========================================
# TAB 4: MODULO DORMI TRANQUILLO
# ==========================================
with tab_night:
    st.markdown("##### 🌙 Audit Salvacapitale")
    sqz_list = [d["name"] for d in data_records if d["squeeze"]]
    if sqz_list:
        st.warning(f"⚠️ Squeeze attivo su: **{', '.join(sqz_list)}** (possibili spike).")
    else:
        st.success("✅ Mercato in volatilità regolare.")

    st.markdown("---")
    st.checkbox("Stop Loss inserito su TUTTI i trade", value=True)
    st.checkbox("Rischio max 1-2% per trade", value=True)
    st.checkbox("Notifiche Push attive", value=True)

    if st.button("🔔 Invia Test Notifica"):
        send_alert(
            title="🌙 TEST MOBILE APEX TERMINAL",
            message=f"Terminale operativo.\nSentiment: {fng_val}/100\nScore Apex Medio: {avg_score}/100"
        )
        st.info("Notifica inviata con successo!")
