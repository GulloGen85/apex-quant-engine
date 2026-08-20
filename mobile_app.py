import os
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components

# --- CONFIGURAZIONE DASHBOARD ULTRA-MOBILE ---
st.set_page_config(
    page_title="Apex Mobile Terminal",
    layout="wide",
    page_icon="📱",
    initial_sidebar_state="collapsed"
)

# --- CSS RESPONSIVE SPECIALIZZATO PER SMARTPHONE (TOUCH-FIRST UI) ---
st.markdown("""
<style>
    /* Viewport & Reset */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .stApp {
        background-color: #070b11;
        color: #e2e8f0;
    }
    .block-container {
        padding-top: 0.6rem !important;
        padding-bottom: 3.5rem !important;
        padding-left: 0.4rem !important;
        padding-right: 0.4rem !important;
        max-width: 100% !important;
    }
    
    /* Riduzione margini per schermi piccoli */
    div[data-testid="column"] {
        width: 100% !important;
        flex: 1 1 auto !important;
        min-width: 140px !important;
    }

    /* Tabs Touch & Horizontal Scrollable */
    .stTabs [data-baseweb="tab-list"] {
        display: flex;
        overflow-x: auto;
        white-space: nowrap;
        gap: 4px;
        padding-bottom: 4px;
        -webkit-overflow-scrolling: touch;
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

    /* Card Mobile Istituzionale */
    .mobile-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 10px 12px;
        margin-bottom: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    .mobile-card:active {
        border-color: #00e5ff;
    }

    /* Badge Colorati */
    .badge {
        display: inline-block;
        padding: 2px 6px;
        font-size: 0.68rem;
        font-weight: 800;
        border-radius: 4px;
        text-transform: uppercase;
    }
    .badge-bull { background-color: rgba(0, 230, 118, 0.15); color: #00e676; border: 1px solid #00e676; }
    .badge-bear { background-color: rgba(255, 23, 68, 0.15); color: #ff1744; border: 1px solid #ff1744; }
    .badge-alert { background-color: rgba(255, 145, 0, 0.15); color: #ff9100; border: 1px solid #ff9100; }
    .badge-squeeze { background-color: rgba(0, 229, 255, 0.15); color: #00e5ff; border: 1px solid #00e5ff; }

    /* Touch Buttons & Inputs */
    .stButton>button {
        width: 100% !important;
        min-height: 46px !important;
        font-size: 0.9rem !important;
        font-weight: 700 !important;
        border-radius: 10px !important;
        background: linear-gradient(135deg, #00c6ff 0%, #0072ff 100%) !important;
        color: #ffffff !important;
        border: none !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.15rem !important;
        color: #00e5ff !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.72rem !important;
    }
    
    /* Tabelle responsive compatte */
    table { font-size: 0.75rem !important; }
</style>
""", unsafe_allow_html=True)

# --- NOTIFICHE PUSH (NTFY & TELEGRAM) ---
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

# --- FETCH MOTORE DATI ---
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
    closes = df["close"]
    highs = df["high"]
    lows = df["low"]
    vols = df["volumeto"]

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

    # EMAs & Slope
    ema7 = closes.ewm(span=7, adjust=False).mean()
    ema25 = closes.ewm(span=25, adjust=False).mean()
    slope = ((ema7.iloc[-1] - ema7.iloc[-4]) / ema7.iloc[-4]) * 100 if len(df) >= 5 else 0.0
    bull_trend = ema7.iloc[-1] > ema25.iloc[-1]

    # Z-Score Volumi
    vol_mean, vol_std = vols.tail(20).mean(), vols.tail(20).std()
    z_score = (vols.iloc[-1] - vol_mean) / vol_std if vol_std > 0 else 0.0

    # Punteggio Confluenza
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
    action = "⚡ ULTRA LONG" if (score >= 70 and is_squeeze) else ("🟢 LONG" if score >= 58 else ("🚨 ULTRA SHORT" if (score <= 30 and is_squeeze) else ("🔴 SHORT" if score <= 42 else "💤 ATTESA")))

    df["bb_u"], df["bb_l"] = bb_u, bb_l
    df["ema7"], df["ema25"] = ema7, ema25

    return {
        "rsi": rsi_val, "atr": atr_val, "squeeze": is_squeeze,
        "bull": bull_trend, "slope": slope, "vol_z": z_score,
        "score": score, "grade": grade, "action": action,
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
            "squeeze": q["squeeze"],
            "bull": q["bull"],
            "support": q["support"],
            "resistance": q["resistance"],
            "df": q["df"]
        })
    return records

data_records = get_mobile_dataset()
fng_val, fng_text = get_fng_index()

# --- BARRA KPI SUPERIORE MOBILE ---
avg_market_score = int(np.mean([x["score"] for x in data_records])) if data_records else 50
kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
with kpi_col1:
    st.metric("F&G Index", f"{fng_val}/100", delta=fng_text, delta_color="off")
with kpi_col2:
    st.metric("Apex Score", f"{avg_market_score}/100", delta="BULL" if avg_market_score >= 50 else "BEAR")
with kpi_col3:
    active_sqz = sum(1 for x in data_records if x["squeeze"])
    st.metric("Squeeze", f"{active_sqz} Attivi", delta="Volatilità" if active_sqz > 0 else "Calmo", delta_color="inverse" if active_sqz > 0 else "normal")

# --- TABS TOUCH MOBILE ---
tab_radar, tab_calc, tab_night, tab_chart = st.tabs([
    "⚡ Segnali & Radar",
    "🎯 Calcolatore R:R",
    "🌙 Dormi Tranquillo",
    "📈 Pro Chart TV"
])

# ==========================================
# TAB 1: RADAR & CARTE ASSET PER MOBILE
# ==========================================
with tab_radar:
    st.caption("📱 Tocca un asset per visualizzare i parametri quantitativi immediati.")
    
    # Filtro rapido per mobile
    filter_choice = st.radio("Filtro Rapido:", ["Tutti", "🔥 Breakout & Squeeze", "🟢 Solo Long", "🔴 Solo Short"], horizontal=True)

    for item in data_records:
        if filter_choice == "🔥 Breakout & Squeeze" and not (item["squeeze"] or "ULTRA" in item["action"]):
            continue
        if filter_choice == "🟢 Solo Long" and "LONG" not in item["action"]:
            continue
        if filter_choice == "🔴 Solo Short" and "SHORT" not in item["action"]:
            continue

        badge_trend = "badge-bull" if item["bull"] else "badge-bear"
        trend_text = "BULLISH" if item["bull"] else "BEARISH"
        sqz_html = '<span class="badge badge-squeeze">⚡ SQUEEZE</span>' if item["squeeze"] else ''
        
        st.markdown(f"""
        <div class="mobile-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span style="font-size: 1rem; font-weight: 800; color: #ffffff;">{item['full_name']}</span>
                <span style="font-size: 1.05rem; font-weight: 800; color: #00e5ff;">{item['fmt_price']}</span>
            </div>
            <div style="display: flex; gap: 5px; margin-bottom: 6px;">
                <span class="badge {badge_trend}">{trend_text}</span>
                <span class="badge badge-alert">{item['grade']}</span>
                {sqz_html}
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px; font-size: 0.75rem; color: #94a3b8; background: #070b11; padding: 6px; border-radius: 6px;">
                <div>RSI: <b style="color:#fff;">{item['rsi']}</b></div>
                <div>Slope: <b style="color:#fff;">{item['slope']:+.2f}%</b></div>
                <div>Vol Z: <b style="color:#fff;">{item['vol_z']:+.1f}σ</b></div>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px; font-size: 0.8rem;">
                <span>Segnale: <b>{item['action']}</b></span>
                <span style="color: #00e5ff; font-weight: 700;">Score: {item['score']}/100</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ==========================================
# TAB 2: CALCOLATORE RISCHIO SMARTPHONE
# ==========================================
with tab_calc:
    st.markdown("##### 🎯 Calcolatore Position Sizing & Target")
    
    asset_list = [d["name"] for d in data_records]
    chosen_symbol = st.selectbox("Seleziona Moneta:", asset_list, index=0)
    cur_data = next(d for d in data_records if d["name"] == chosen_symbol)

    col_inp1, col_inp2 = st.columns(2)
    with col_inp1:
        entry_p = st.number_input("Prezzo Entry ($)", value=float(cur_data["price"]), format="%.4f")
        calc_dir = st.selectbox("Direzione", ["LONG 📈", "SHORT 📉"])
    with col_inp2:
        acc_balance = st.number_input("Capitale ($)", value=5000.0, step=500.0)
        risk_percent = st.number_input("Rischio Max (%)", value=1.0, min_value=0.2, max_value=5.0, step=0.1)

    atr_distance = cur_data["atr"] * 1.5
    is_long = "LONG" in calc_dir
    sl_calc = entry_p - atr_distance if is_long else entry_p + atr_distance
    dollar_risk = acc_balance * (risk_percent / 100.0)
    pos_units = dollar_risk / atr_distance if atr_distance > 0 else 0
    pos_usd = pos_units * entry_p

    # Risultati compatti per smartphone
    st.markdown("---")
    res1, res2 = st.columns(2)
    res1.metric("Dimensione Trade", f"${pos_usd:,.2f}")
    res2.metric("Perdita a SL", f"-${dollar_risk:,.2f}")

    res3, res4 = st.columns(2)
    res3.metric("Quantità Coin", f"{pos_units:,.4f}")
    res4.metric("Stop Loss Rigido", f"${sl_calc:,.4f}")

    st.markdown("##### 🎯 Livelli di Uscita Scalettati")
    tp1 = entry_p + (atr_distance * 1.5) if is_long else entry_p - (atr_distance * 1.5)
    tp2 = entry_p + (atr_distance * 2.5) if is_long else entry_p - (atr_distance * 2.5)
    tp3 = entry_p + (atr_distance * 4.0) if is_long else entry_p - (atr_distance * 4.0)

    tp_df = pd.DataFrame([
        {"Target": "TP1 (50%)", "R:R": "1 : 1.5", "Prezzo": f"${tp1:,.4f}", "Profitto": f"+${dollar_risk * 1.5:,.2f}"},
        {"Target": "TP2 (30%)", "R:R": "1 : 2.5", "Prezzo": f"${tp2:,.4f}", "Profitto": f"+${dollar_risk * 2.5:,.2f}"},
        {"Target": "TP3 (20%)", "R:R": "1 : 4.0", "Prezzo": f"${tp3:,.4f}", "Profitto": f"+${dollar_risk * 4.0:,.2f}"}
    ])
    st.dataframe(tp_df, use_container_width=True, hide_index=True)

# ==========================================
# TAB 3: MODULO DORMI TRANQUILLO MOBILE
# ==========================================
with tab_night:
    st.markdown("##### 🌙 Audit Notturno Salvacapitale")
    
    sqz_coins = [d["name"] for d in data_records if d["squeeze"]]
    if sqz_coins:
        st.warning(f"⚠️ **Compressione attiva su:** {', '.join(sqz_coins)}. Possibili spike notturni.")
    else:
        st.success("✅ **Nessun pericolo di spike anomali.** Volatilità nella norma.")

    st.markdown("---")
    c_sl = st.checkbox("Stop Loss inseriti a sistema su TUTTI i trade", value=True)
    c_rk = st.checkbox("Rischio totale sotto controllo (max 1-2% per trade)", value=True)
    c_nt = st.checkbox("Notifiche Push attive sul cellulare", value=True)

    if c_sl and c_rk and c_nt:
        st.success("🛡️ **AUDIT NOTTURNO SUPERATO.** Puoi dormire tranquillo.")
    else:
        st.error("🚨 **RISCHIO PRESENTE:** Non lasciare posizioni scoperte!")

    st.markdown("---")
    if st.button("🔔 Invia Notifica di Test allo Smartphone"):
        send_alert(
            title="🌙 TEST MOBILE APEX TERMINAL",
            message=f"Terminal attivo. Sentiment: {fng_val}/100 | Confluenza media: {avg_market_score}/100"
        )
        st.info("Notifica inviata a ntfy/Telegram!")

# ==========================================
# TAB 4: PRO CHART & TRADINGVIEW MOBILE
# ==========================================
with tab_chart:
    st.markdown("##### 📈 Grafici Mobile-Optimized")
    chart_asset_name = st.selectbox("Scegli Moneta per Grafico:", asset_list, index=0, key="chart_selector")
    c_item = next(d for d in data_records if d["name"] == chart_asset_name)

    # Livelli chiave in formato ultra-compatto
    lvl1, lvl2 = st.columns(2)
    lvl1.metric("Supporto 24h", f"${c_item['support']:,.2f}" if c_item['support'] >= 1 else f"${c_item['support']:.4f}")
    lvl2.metric("Resistenza 24h", f"${c_item['resistance']:,.2f}" if c_item['resistance'] >= 1 else f"${c_item['resistance']:.4f}")

    # Candlestick compatto (Plotly)
    df_p = c_item["df"].tail(30)
    fig = go.Figure(data=[
        go.Candlestick(
            x=np.arange(len(df_p)),
            open=df_p['open'], high=df_p['high'],
            low=df_p['low'], close=df_p['close'],
            name="OHLC"
        ),
        go.Scatter(x=np.arange(len(df_p)), y=df_p['ema7'], line=dict(color='#00e676', width=1.5), name="EMA7"),
        go.Scatter(x=np.arange(len(df_p)), y=df_p['ema25'], line=dict(color='#ff9100', width=1.5), name="EMA25")
    ])
    fig.update_layout(
        height=260,
        margin=dict(l=2, r=2, t=5, b=5),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_rangeslider_visible=False,
        showlegend=False,
        font={'color': 'white'}
    )
    st.plotly_chart(fig, use_container_width=True)

    # Widget Ufficiale TradingView (Modalità Mobile)
    st.markdown("##### 🌐 Live Interactive TradingView")
    tv_mobile_html = f"""
    <div style="height:360px;width:100%">
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "autosize": true,
        "symbol": "{c_item['tv_symbol']}",
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
        "container_id": "tv_chart_mobile"
      }}
      );
      </script>
      <div id="tv_chart_mobile" style="height:100%;width:100%"></div>
    </div>
    """
    components.html(tv_mobile_html, height=370)
