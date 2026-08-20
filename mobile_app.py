import datetime
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components

# --- CONFIGURAZIONE STREAMLIT ---
st.set_page_config(
    page_title="Apex Terminal Pro",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed"
)

# --- CSS DARK ENGINE & MOBILE RESPONSIVE ---
st.markdown("""
<style>
    .stApp { 
        background-color: #06090e; 
        color: #f1f5f9; 
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
    }
    .block-container { 
        padding-top: 0.5rem !important; 
        padding-bottom: 2rem !important; 
        padding-left: 0.6rem !important; 
        padding-right: 0.6rem !important; 
    }
    
    /* Metriche & Header */
    div[data-testid="stMetricValue"] { 
        font-size: 1.15rem !important; 
        color: #00f2fe !important; 
        font-weight: 800; 
    }
    div[data-testid="stMetricLabel"] { 
        font-size: 0.72rem !important; 
        color: #94a3b8 !important; 
        font-weight: 600; 
        text-transform: uppercase; 
    }
    div[data-testid="stMetricDelta"] {
        font-size: 0.72rem !important;
        font-weight: 700 !important;
    }
    
    /* Tabs Orizzontali Touch */
    .stTabs [data-baseweb="tab-list"] { 
        display: flex; 
        overflow-x: auto; 
        white-space: nowrap; 
        gap: 6px; 
        padding-bottom: 6px; 
        border-bottom: 1px solid #1e293b; 
    }
    .stTabs [data-baseweb="tab"] { 
        background-color: #0b111e; 
        border-radius: 6px; 
        color: #94a3b8; 
        padding: 6px 12px; 
        font-size: 0.80rem; 
        font-weight: 700; 
        border: 1px solid #1e293b; 
    }
    .stTabs [aria-selected="true"] { 
        background-color: #162238 !important; 
        color: #00f2fe !important; 
        border: 1px solid #00f2fe !important; 
    }
    
    /* Card Asset */
    .card-asset { 
        background: #0b111e; 
        border: 1px solid #1e293b; 
        border-radius: 10px; 
        padding: 12px; 
        margin-bottom: 8px; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .sync-bar { 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        font-size: 0.75rem; 
        color: #64748b; 
        margin-bottom: 10px; 
        border-bottom: 1px solid #1e293b;
        padding-bottom: 6px;
    }
    
    /* Badge Operativi */
    .badge-buy { background: rgba(0, 230, 118, 0.15); color: #00e676; padding: 3px 8px; border-radius: 4px; font-weight: 700; border: 1px solid #00e676; font-size: 0.72rem; }
    .badge-tp { background: rgba(255, 145, 0, 0.15); color: #ff9100; padding: 3px 8px; border-radius: 4px; font-weight: 700; border: 1px solid #ff9100; font-size: 0.72rem; }
    .badge-sell { background: rgba(255, 23, 68, 0.15); color: #ff1744; padding: 3px 8px; border-radius: 4px; font-weight: 700; border: 1px solid #ff1744; font-size: 0.72rem; }
    .badge-neutral { background: rgba(148, 163, 184, 0.15); color: #94a3b8; padding: 3px 8px; border-radius: 4px; font-weight: 700; border: 1px solid #94a3b8; font-size: 0.72rem; }

    /* Tabelle Native Dark Custom */
    .dark-table { 
        width: 100%; 
        border-collapse: collapse; 
        font-size: 0.78rem; 
        margin-top: 8px; 
        margin-bottom: 8px;
        background: #0b111e; 
        border-radius: 8px; 
        overflow: hidden; 
        border: 1px solid #1e293b; 
    }
    .dark-table th { 
        background: #162238; 
        color: #94a3b8; 
        text-align: left; 
        padding: 8px 10px; 
        font-weight: 700; 
        border-bottom: 1px solid #1e293b; 
    }
    .dark-table td { 
        padding: 8px 10px; 
        border-bottom: 1px solid #131d2e; 
        color: #f1f5f9; 
    }
    .dark-table tr:last-child td { border-bottom: none; }
</style>
""", unsafe_allow_html=True)

# --- ASSET UNIVERSE ---
ASSETS = [
    {"name": "BTC", "okx": "BTC-USDT", "tv": "BINANCE:BTCUSDT", "base_price": 71600.0},
    {"name": "ETH", "okx": "ETH-USDT", "tv": "BINANCE:ETHUSDT", "base_price": 2280.0},
    {"name": "SOL", "okx": "SOL-USDT", "tv": "BINANCE:SOLUSDT", "base_price": 86.5},
    {"name": "NEAR", "okx": "NEAR-USDT", "tv": "BINANCE:NEARUSDT", "base_price": 1.72},
    {"name": "TAO", "okx": "TAO-USDT", "tv": "BINANCE:TAOUSDT", "base_price": 208.0},
    {"name": "WLD", "okx": "WLD-USDT", "tv": "BINANCE:WLDUSDT", "base_price": 0.35},
    {"name": "ONDO", "okx": "ONDO-USDT", "tv": "BINANCE:ONDOUSDT", "base_price": 0.67},
    {"name": "ZEC", "okx": "ZEC-USDT", "tv": "BINANCE:ZECUSDT", "base_price": 31.0}
]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json"
})

def fmt_price(p: float) -> str:
    if p >= 1000:
        return f"${p:,.0f}"
    elif p >= 1:
        return f"${p:,.2f}"
    else:
        return f"${p:.4f}"

def render_table_html(headers, rows):
    th_html = "".join([f"<th>{h}</th>" for h in headers])
    tr_html = "".join([f"<tr>{''.join([f'<td>{cell}</td>' for cell in r])}</tr>" for r in rows])
    return f'<table class="dark-table"><thead><tr>{th_html}</tr></thead><tbody>{tr_html}</tbody></table>'

def compute_rsi_series(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 1:
        return 50.0
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = float(rsi.iloc[-1])
    return round(val, 1) if not np.isnan(val) else 50.0

def fetch_candles(inst_id: str, bar: str, limit: int = 35):
    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar={bar}&limit={limit}"
        res = SESSION.get(url, timeout=1.2).json()
        data = res.get("data", [])
        if data:
            df = pd.DataFrame(data, columns=["ts", "open", "high", "low", "close", "vol", "volCcy", "volCcyQuote", "confirm"])
            for col in ["open", "high", "low", "close", "vol"]:
                df[col] = df[col].astype(float)
            df["ts"] = pd.to_numeric(df["ts"])
            return df.sort_values("ts").reset_index(drop=True)
    except Exception:
        pass
    return None

def fetch_asset_single_call(asset: dict):
    inst = asset["okx"]
    curr_p = asset["base_price"]
    pct_24h = 0.0
    rsi_1h, rsi_4h, rsi_1d = 50.0, 50.0, 50.0
    atr = curr_p * 0.018
    squeeze = False
    trend_bull = True

    df_1h = fetch_candles(inst, "1H", 60)
    df_4h = fetch_candles(inst, "4H", 35)
    df_1d = fetch_candles(inst, "1D", 35)

    if df_1h is not None and len(df_1h) >= 20:
        curr_p = float(df_1h["close"].iloc[-1])
        rsi_1h = compute_rsi_series(df_1h["close"], 14)
        
        h, l, c = df_1h["high"], df_1h["low"], df_1h["close"]
        tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
        atr_calc = float(tr.rolling(14).mean().iloc[-1])
        if not np.isnan(atr_calc) and atr_calc > 0:
            atr = atr_calc

        sma20 = c.rolling(20).mean()
        std20 = c.rolling(20).std()
        bb_u, bb_l = sma20 + (2.0 * std20), sma20 - (2.0 * std20)
        kc_u, kc_l = sma20 + (1.5 * atr), sma20 - (1.5 * atr)
        squeeze = bool((bb_l.iloc[-1] > kc_l.iloc[-1]) and (bb_u.iloc[-1] < kc_u.iloc[-1]))

        ema9 = c.ewm(span=9, adjust=False).mean().iloc[-1]
        ema21 = c.ewm(span=21, adjust=False).mean().iloc[-1]
        trend_bull = bool(ema9 >= ema21)

        open_24h = df_1h["open"].iloc[-24] if len(df_1h) >= 24 else df_1h["open"].iloc[0]
        pct_24h = ((curr_p - open_24h) / open_24h) * 100

    if df_4h is not None and len(df_4h) >= 15:
        rsi_4h = compute_rsi_series(df_4h["close"], 14)

    if df_1d is not None and len(df_1d) >= 15:
        rsi_1d = compute_rsi_series(df_1d["close"], 14)

    # Scoring Istituzionale Calibrato
    score = 50
    score += 15 if trend_bull else -15
    score += 10 if squeeze else 0
    if rsi_1h <= 35: score += 15
    elif rsi_1h >= 70: score -= 15
    if rsi_4h >= 75: score -= 10
    score = max(10, min(90, score))

    if rsi_1h >= 70 or rsi_4h >= 75:
        action = "PRENDI PROFITTO (IPERCOMPRATO)"
        action_code = "TP"
        badge_cls = "badge-tp"
        lvl1_lbl, lvl1_val, lvl1_col = "🛡️ Trailing SL", curr_p - (0.8 * atr), "#ff9100"
        lvl2_lbl, lvl2_val, lvl2_col = "🎯 Dip Buy 1", curr_p - (1.8 * atr), "#00f2fe"
        lvl3_lbl, lvl3_val, lvl3_col = "📉 Supporto Dip", curr_p - (3.2 * atr), "#94a3b8"
    elif score <= 40:
        action = "DISTRIBUISCI / SHORT"
        action_code = "SELL"
        badge_cls = "badge-sell"
        lvl1_lbl, lvl1_val, lvl1_col = "🛑 Stop Loss", curr_p + (1.5 * atr), "#ff1744"
        lvl2_lbl, lvl2_val, lvl2_col = "🎯 TP1 Short", curr_p - (2.0 * atr), "#00e676"
        lvl3_lbl, lvl3_val, lvl3_col = "🚀 TP2 Short", curr_p - (3.8 * atr), "#00e676"
    elif score >= 60:
        action = "ACCUMULA / LONG"
        action_code = "BUY"
        badge_cls = "badge-buy"
        lvl1_lbl, lvl1_val, lvl1_col = "🛑 Stop Loss", curr_p - (1.5 * atr), "#ff1744"
        lvl2_lbl, lvl2_val, lvl2_col = "🎯 TP1 Long", curr_p + (2.0 * atr), "#00e676"
        lvl3_lbl, lvl3_val, lvl3_col = "🚀 TP2 Long", curr_p + (3.8 * atr), "#00e676"
    else:
        action = "NEUTRALE / RANGE"
        action_code = "NEUTRAL"
        badge_cls = "badge-neutral"
        lvl1_lbl, lvl1_val, lvl1_col = "🧱 Supporto", curr_p - (1.5 * atr), "#94a3b8"
        lvl2_lbl, lvl2_val, lvl2_col = "🚧 Pivot Range", curr_p, "#00f2fe"
        lvl3_lbl, lvl3_val, lvl3_col = "🧗 Resistenza", curr_p + (1.5 * atr), "#94a3b8"

    return {
        "name": asset["name"],
        "inst": inst,
        "tv": asset["tv"],
        "price": curr_p,
        "pct_24h": pct_24h,
        "rsi_1h": rsi_1h,
        "rsi_4h": rsi_4h,
        "rsi_1d": rsi_1d,
        "atr": atr,
        "squeeze": squeeze,
        "score": score,
        "action": action,
        "action_code": action_code,
        "badge_cls": badge_cls,
        "lvl1": (lvl1_lbl, lvl1_val, lvl1_col),
        "lvl2": (lvl2_lbl, lvl2_val, lvl2_col),
        "lvl3": (lvl3_lbl, lvl3_val, lvl3_col)
    }

def fetch_okx_whale_trades(inst_id: str, min_usd: float = 1000.0):
    trades = []
    try:
        url = f"https://www.okx.com/api/v5/market/trades?instId={inst_id}&limit=100"
        res = SESSION.get(url, timeout=1.0).json()
        items = res.get("data", [])
        if isinstance(items, list):
            for t in items:
                p = float(t.get("px", 0.0))
                q = float(t.get("sz", 0.0))
                val = p * q
                trades.append({
                    "ts": int(t.get("ts", 0)),
                    "Ora": pd.to_datetime(int(t.get("ts", 0)), unit="ms").strftime("%H:%M:%S"),
                    "Side": t.get("side", "").upper(),
                    "Prezzo": fmt_price(p),
                    "ValoreRaw": val,
                    "Controvalore": f"${val:,.0f}",
                    "RawDelta": val if t.get("side") == "buy" else -val,
                    "Quantità": f"{q:,.2f}"
                })
        
        df = pd.DataFrame(trades)
        if not df.empty:
            filtered = df[df["ValoreRaw"] >= min_usd]
            return filtered if not filtered.empty else df.sort_values("ValoreRaw", ascending=False).head(15)
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_fear_and_greed():
    try:
        res = SESSION.get("https://api.alternative.me/fng/?limit=1", timeout=1.0).json()
        item = res["data"][0]
        return int(item["value"]), item["value_classification"]
    except Exception:
        return 65, "Greed"

@st.cache_data(ttl=15)
def load_market_data():
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(fetch_asset_single_call, ASSETS))
    return [r for r in results if r is not None]

# --- ESECUZIONE CARICAMENTO DATI ---
data_market = load_market_data()
fng_val, fng_label = fetch_fear_and_greed()
avg_bias = int(np.mean([x["score"] for x in data_market])) if data_market else 50
names_list = [d["name"] for d in data_market]
now_str = datetime.datetime.now().strftime("%H:%M:%S")

# --- UI HEADER PRINCIPALE ---
st.markdown(f"""
<div class="sync-bar">
    <span style="font-size:1.05rem; font-weight:800; color:#f1f5f9;">⚡ APEX TERMINAL PRO</span>
    <span>Live OKX Core • <b>{now_str}</b></span>
</div>
""", unsafe_allow_html=True)

k1, k2, k3 = st.columns(3)
k1.metric("Fear & Greed", f"{fng_val}/100", delta=fng_label, delta_color="off")
k2.metric("Market Bias", f"{avg_bias}/100", delta="BULLISH" if avg_bias >= 50 else "BEARISH")
sqz_total = sum(1 for x in data_market if x["squeeze"])
k3.metric("Squeeze 1H", f"{sqz_total} Attivi", delta="Espansione" if sqz_total > 0 else "Range")

# --- TABS OPERATIVE TOUCH ---
t_signals, t_heat, t_whales, t_calc, t_tv = st.tabs([
    "⚡ Segnali",
    "🔥 Liquidity",
    "🐋 Whales Tape",
    "🎯 Risk Calc",
    "📈 TV Chart"
])

with t_signals:
    filter_choice = st.radio("Filtro Segnali:", ["Tutti", "🟢 Solo Buy", "⚠️ Alert TP/Short"], horizontal=True)

    for item in data_market:
        if filter_choice == "🟢 Solo Buy" and item["action_code"] != "BUY":
            continue
        if filter_choice == "⚠️ Alert TP/Short" and item["action_code"] not in ["TP", "SELL"]:
            continue

        pct_col = "#00e676" if item["pct_24h"] >= 0 else "#ff1744"

        st.markdown(f"""
        <div class="card-asset">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:1.05rem; font-weight:800;">{item['name']}/USDT</span>
                <span style="font-size:1.05rem; font-weight:800; color:#00f2fe;">{fmt_price(item['price'])} 
                    <span style="font-size:0.75rem; color:{pct_col}; font-weight:700;">({item['pct_24h']:+.2f}%)</span>
                </span>
            </div>
            <div style="margin-top:6px; display:flex; justify-content:space-between; align-items:center;">
                <span class="{item['badge_cls']}">{item['action']}</span> 
                <span style="font-size:0.75rem; color:#64748b;">Score: <b style="color:#f1f5f9;">{item['score']}/100</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if item["squeeze"]:
            st.warning(f"⚡ **TTM Squeeze Attivo su {item['name']}:** Compressione 1H. Imminente breakout di volatilità.")

        r1, r2, r3 = st.columns(3)
        r1.metric("RSI 1H", f"{item['rsi_1h']}")
        r2.metric("RSI 4H", f"{item['rsi_4h']}")
        r3.metric("RSI Daily", f"{item['rsi_1d']}")

        l1, l2, l3 = st.columns(3)
        l1.markdown(f"<div style='font-size:0.70rem; color:#94a3b8;'>{item['lvl1'][0]}</div><div style='font-size:0.85rem; font-weight:700; color:{item['lvl1'][2]};'>{fmt_price(item['lvl1'][1])}</div>", unsafe_allow_html=True)
        l2.markdown(f"<div style='font-size:0.70rem; color:#94a3b8;'>{item['lvl2'][0]}</div><div style='font-size:0.85rem; font-weight:700; color:{item['lvl2'][2]};'>{fmt_price(item['lvl2'][1])}</div>", unsafe_allow_html=True)
        l3.markdown(f"<div style='font-size:0.70rem; color:#94a3b8;'>{item['lvl3'][0]}</div><div style='font-size:0.85rem; font-weight:700; color:{item['lvl3'][2]};'>{fmt_price(item['lvl3'][1])}</div>", unsafe_allow_html=True)
        st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)

with t_heat:
    st.markdown("##### 🔥 Liquidity Cascades (Mappe di Liquidazione)")
    c_liq = st.selectbox("Asset:", names_list, index=0, key="liq_coin_select")
    m_liq = next(d for d in data_market if d["name"] == c_liq)
    p_liq = m_liq["price"]

    levs = [100, 50, 25, 10]
    liq_records = []
    for lev in levs:
        long_liq = p_liq * (1.0 - (0.90 / lev))
        short_liq = p_liq * (1.0 + (0.90 / lev))
        vol_est = round((100 / lev) * 2.5, 1)
        liq_records.append({
            "Leva": f"{lev}x",
            "Long": long_liq,
            "Short": short_liq,
            "Vol": vol_est
        })

    df_l = pd.DataFrame(liq_records)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df_l["Leva"],
        x=df_l["Vol"],
        orientation='h',
        name='Short Liquidation',
        marker=dict(color='#ff1744'),
        hoverinfo='x+name'
    ))
    fig.add_trace(go.Bar(
        y=df_l["Leva"],
        x=[-v for v in df_l["Vol"]],
        orientation='h',
        name='Long Liquidation',
        marker=dict(color='#00e676'),
        hoverinfo='x+name'
    ))

    fig.update_layout(
        barmode='overlay',
        paper_bgcolor='#06090e',
        plot_bgcolor='#0b111e',
        font=dict(color='#94a3b8', size=10),
        height=210,
        margin=dict(l=5, r=5, t=10, b=5),
        xaxis=dict(showgrid=False, title="Volume Stimato ($M)", zeroline=True, zerolinecolor="#334155"),
        yaxis=dict(autorange="reversed"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # Tabella HTML Dark Mode Pulita (senza bug di rendering)
    table_headers = ["Leva", "Caccia ai Long", "Caccia agli Short", "Impatto"]
    table_rows = [
        [
            f"<b>{r['Leva']}</b>",
            f"<span style='color:#00e676;'>{fmt_price(r['Long'])}</span>",
            f"<span style='color:#ff1744;'>{fmt_price(r['Short'])}</span>",
            f"<span style='color:#00f2fe;'>${r['Vol']}M</span>"
        ]
        for _, r in df_l.iterrows()
    ]
    st.markdown(render_table_html(table_headers, table_rows), unsafe_allow_html=True)

with t_whales:
    st.markdown("##### 🐋 Tape Ordini Istituzionali Live")
    w_coin = st.selectbox("Asset Tape:", names_list, index=0, key="tape_coin_sel")
    w_meta = next(d for d in data_market if d["name"] == w_coin)

    threshold = st.select_slider("Filtro Taglia Minima ($)", options=[500, 1000, 2500, 5000], value=1000)
    df_tape = fetch_okx_whale_trades(w_meta["inst"], min_usd=float(threshold))

    if not df_tape.empty:
        net_delta = df_tape["RawDelta"].sum()
        total_vol = df_tape["ValoreRaw"].sum()
        buy_pct = (df_tape[df_tape["Side"] == "BUY"]["ValoreRaw"].sum() / total_vol * 100) if total_vol > 0 else 50.0

        c_d1, c_d2 = st.columns(2)
        c_d1.metric("Delta Volumi", f"${net_delta:,.0f}", delta="Pressione BUY" if net_delta >= 0 else "Pressione SELL")
        c_d2.metric("Dominanza Buyer", f"{buy_pct:.1f}%")

        headers_w = ["Ora", "Side", "Prezzo", "Valore", "Q.tà"]
        rows_w = [
            [
                f"<span style='color:#94a3b8;'>{r['Ora']}</span>",
                f"<span style='color:{'#00e676' if r['Side']=='BUY' else '#ff1744'}; font-weight:700;'>{r['Side']}</span>",
                r['Prezzo'],
                f"<span style='font-weight:700; color:#00f2fe;'>{r['Controvalore']}</span>",
                f"<span style='color:#cbd5e1;'>{r['Quantità']}</span>"
            ]
            for _, r in df_tape.head(15).iterrows()
        ]
        st.markdown(render_table_html(headers_w, rows_w), unsafe_allow_html=True)
    else:
        st.info(f"Nessun trade rilevante su {w_coin} negli ultimi secondi.")

with t_calc:
    st.markdown("##### 🎯 Calcolatore Position Sizing & ATR Risk")
    calc_c = st.selectbox("Asset di Riferimento:", names_list, index=0, key="calc_select_c")
    calc_meta = next(d for d in data_market if d["name"] == calc_c)

    c_cap, c_risk = st.columns(2)
    with c_cap:
        capital = st.number_input("Capitale ($)", min_value=100.0, value=2000.0, step=250.0)
    with c_risk:
        risk_percent = st.slider("Rischio Max %", min_value=0.5, max_value=5.0, value=1.0, step=0.5)

    direction = st.radio("Direzione:", ["LONG 📈", "SHORT 📉"], horizontal=True, index=0 if calc_meta["action_code"] == "BUY" else 1)

    entry = calc_meta["price"]
    dist_sl = calc_meta["atr"] * 1.5
    stop_calc = entry - dist_sl if "LONG" in direction else entry + dist_sl

    max_loss_usd = capital * (risk_percent / 100.0)
    position_coins = max_loss_usd / dist_sl if dist_sl > 0 else 0
    total_pos_value = position_coins * entry

    r1, r2 = st.columns(2)
    r1.metric("Dimensione Ordine", f"${total_pos_value:,.2f}")
    r2.metric("Rischio Monetario", f"-${max_loss_usd:,.2f}")

    r3, r4 = st.columns(2)
    r3.metric("Quantità Coin", f"{position_coins:,.4f} {calc_c}")
    r4.metric("Stop Loss ATR", fmt_price(stop_calc))

    # Matrice Risk-Reward Renderizzata Correttamente
    headers_rr = ["Rapporto R:R", "Prezzo Target", "Profitto Stimato"]
    rows_rr = [
        [
            f"<b>1:{rr:.1f}</b>",
            f"<span style='color:#00f2fe;'>{fmt_price(entry + (dist_sl * rr) if 'LONG' in direction else entry - (dist_sl * rr))}</span>",
            f"<span style='color:#00e676; font-weight:700;'>+${(max_loss_usd * rr):,.2f}</span>"
        ]
        for rr in [1.5, 2.0, 3.0, 4.0]
    ]
    st.markdown(render_table_html(headers_rr, rows_rr), unsafe_allow_html=True)

with t_tv:
    tv_c = st.selectbox("Seleziona Grafico:", names_list, index=0, key="tv_select")
    tv_meta = next(d for d in data_market if d["name"] == tv_c)

    tv_widget_html = f"""
    <div style="height:580px; width:100%; border-radius:8px; overflow:hidden; border:1px solid #1e293b;">
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
        "toolbar_bg": "#06090e",
        "enable_publishing": false,
        "hide_top_toolbar": false,
        "hide_side_toolbar": false,
        "save_image": false,
        "container_id": "tv_chart"
      }});
      </script>
      <div id="tv_chart" style="height:100%;width:100%"></div>
    </div>
    """
    components.html(tv_widget_html, height=590)
