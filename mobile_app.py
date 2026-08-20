import datetime
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

# --- DARK THEME OTTIMIZZATO ---
st.markdown("""
<style>
    .stApp { background-color: #080c14; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .block-container { padding-top: 0.6rem !important; padding-bottom: 2rem !important; padding-left: 0.6rem !important; padding-right: 0.6rem !important; }
    div[data-testid="stMetricValue"] { font-size: 1.15rem !important; color: #00f2fe !important; font-weight: 800; }
    div[data-testid="stMetricLabel"] { font-size: 0.72rem !important; color: #94a3b8 !important; font-weight: 600; }
    .stTabs [data-baseweb="tab-list"] { display: flex; overflow-x: auto; white-space: nowrap; gap: 6px; padding-bottom: 6px; border-bottom: 1px solid #1e293b; }
    .stTabs [data-baseweb="tab"] { background-color: #0d1527; border-radius: 6px; color: #94a3b8; padding: 6px 12px; font-size: 0.8rem; font-weight: 700; border: 1px solid #1e293b; }
    .stTabs [aria-selected="true"] { background-color: #1e293b !important; color: #00f2fe !important; border: 1px solid #00f2fe !important; }
    .card-asset { background: #0d1527; border: 1px solid #1e293b; border-radius: 10px; padding: 12px; margin-bottom: 10px; }
    .sync-badge { font-size: 0.70rem; color: #64748b; text-align: right; margin-top: -12px; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# --- ASSET TRACKER ---
ASSETS = [
    {"name": "BTC", "okx": "BTC-USDT", "tv": "BINANCE:BTCUSDT", "base_price": 71800.0},
    {"name": "ETH", "okx": "ETH-USDT", "tv": "BINANCE:ETHUSDT", "base_price": 2300.0},
    {"name": "SOL", "okx": "SOL-USDT", "tv": "BINANCE:SOLUSDT", "base_price": 88.0},
    {"name": "NEAR", "okx": "NEAR-USDT", "tv": "BINANCE:NEARUSDT", "base_price": 1.73},
    {"name": "TAO", "okx": "TAO-USDT", "tv": "BINANCE:TAOUSDT", "base_price": 208.0},
    {"name": "WLD", "okx": "WLD-USDT", "tv": "BINANCE:WLDUSDT", "base_price": 1.25},
    {"name": "ONDO", "okx": "ONDO-USDT", "tv": "BINANCE:ONDOUSDT", "base_price": 0.67},
    {"name": "ZEC", "okx": "ZEC-USDT", "tv": "BINANCE:ZECUSDT", "base_price": 31.0}
]

# Sessione HTTP globale riutilizzabile
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
})

def fmt_price(p: float) -> str:
    if p >= 1000:
        return f"${p:,.0f}"
    elif p >= 1:
        return f"${p:,.2f}"
    else:
        return f"${p:.4f}"

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

def fetch_asset_single_call(asset: dict):
    inst = asset["okx"]
    curr_p = asset["base_price"]
    pct_24h = 0.5
    rsi_1h, rsi_4h, rsi_1d = 50.0, 50.0, 50.0
    atr = curr_p * 0.018
    squeeze = False
    trend_bull = True

    try:
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst}&bar=1H&limit=80"
        r = SESSION.get(url, timeout=1.2)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data and len(data) >= 20:
                df = pd.DataFrame(data, columns=["ts", "open", "high", "low", "close", "vol", "volCcy", "volCcyQuote", "confirm"])
                for c in ["open", "high", "low", "close", "vol"]:
                    df[c] = df[c].astype(float)
                df["ts"] = pd.to_numeric(df["ts"])
                df = df.sort_values("ts").reset_index(drop=True)

                curr_p = float(df["close"].iloc[-1])
                rsi_1h = compute_rsi(df["close"], 14)
                
                # Derivazione 4H e 1D da campionamento orario per azzerare chiamate HTTP
                c_4h = df["close"].iloc[::4]
                rsi_4h = compute_rsi(c_4h, 10) if len(c_4h) >= 11 else rsi_1h
                
                c_1d = df["close"].iloc[::24]
                rsi_1d = compute_rsi(c_1d, 5) if len(c_1d) >= 6 else rsi_4h

                h, l, c = df["high"], df["low"], df["close"]
                tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
                atr_calc = float(tr.rolling(14).mean().iloc[-1])
                if not np.isnan(atr_calc) and atr_calc > 0:
                    atr = atr_calc

                # TTM Squeeze
                sma20 = c.rolling(20).mean()
                std20 = c.rolling(20).std()
                bb_u, bb_l = sma20 + (2.0 * std20), sma20 - (2.0 * std20)
                kc_u, kc_l = sma20 + (1.5 * atr), sma20 - (1.5 * atr)
                squeeze = bool((bb_l.iloc[-1] > kc_l.iloc[-1]) and (bb_u.iloc[-1] < kc_u.iloc[-1])) if len(df) >= 20 else False

                ema9 = c.ewm(span=9, adjust=False).mean().iloc[-1]
                ema21 = c.ewm(span=21, adjust=False).mean().iloc[-1]
                trend_bull = bool(ema9 >= ema21)

                open_ref = df["open"].iloc[0]
                pct_24h = ((curr_p - open_ref) / open_ref) * 100
    except Exception:
        pass

    # Score Istituzionale (0-100)
    score = 50
    score += 18 if trend_bull else -18
    score += 10 if squeeze else 0
    if rsi_1h <= 35: score += 20
    elif rsi_1h >= 75: score -= 25
    elif 45 <= rsi_1h <= 62 and trend_bull: score += 12
    score = max(5, min(95, score))

    if rsi_1h >= 75 or rsi_4h >= 80:
        action = "⚠️ PRENDI PROFITTO (IPERCOMPRATO)"
        action_code = "TP"
        badge_col = "#ff9100"
        lvl1_lbl, lvl1_val = "🛡️ Trailing SL", curr_p - (0.8 * atr)
        lvl2_lbl, lvl2_val = "🎯 Dip Buy 1", curr_p - (1.8 * atr)
        lvl3_lbl, lvl3_val = "📉 Supporto Dip", curr_p - (3.2 * atr)
    elif score <= 38:
        action = "🔴 DISTRIBUISCI / SHORT"
        action_code = "SELL"
        badge_col = "#ff1744"
        lvl1_lbl, lvl1_val = "🛑 Stop Loss", curr_p + (1.5 * atr)
        lvl2_lbl, lvl2_val = "🎯 TP1 Short", curr_p - (2.0 * atr)
        lvl3_lbl, lvl3_val = "🚀 TP2 Short", curr_p - (3.8 * atr)
    elif score >= 62:
        action = "🟢 ACCUMULA / LONG"
        action_code = "BUY"
        badge_col = "#00e676"
        lvl1_lbl, lvl1_val = "🛑 Stop Loss", curr_p - (1.5 * atr)
        lvl2_lbl, lvl2_val = "🎯 TP1 Long", curr_p + (2.0 * atr)
        lvl3_lbl, lvl3_val = "🚀 TP2 Long", curr_p + (3.8 * atr)
    else:
        action = "💤 NEUTRALE / ATTENDI RANGE"
        action_code = "NEUTRAL"
        badge_col = "#94a3b8"
        lvl1_lbl, lvl1_val = "🧱 Supporto", curr_p - (1.5 * atr)
        lvl2_lbl, lvl2_val = "🚧 Pivot Range", curr_p
        lvl3_lbl, lvl3_val = "🧗 Resistenza", curr_p + (1.5 * atr)

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
        "badge_col": badge_col,
        "lvl1": (lvl1_lbl, lvl1_val),
        "lvl2": (lvl2_lbl, lvl2_val),
        "lvl3": (lvl3_lbl, lvl3_val)
    }

def fetch_okx_whale_trades(inst_id: str, min_usd: float = 3000.0):
    trades = []
    try:
        url = f"https://www.okx.com/api/v5/market/trades?instId={inst_id}&limit=80"
        res = SESSION.get(url, timeout=1.0).json()
        items = res.get("data", [])
        if isinstance(items, list):
            for t in items:
                p = float(t.get("px", 0.0))
                q = float(t.get("sz", 0.0))
                val = p * q
                if val >= min_usd:
                    trades.append({
                        "Ora": pd.to_datetime(int(t.get("ts", 0)), unit="ms").strftime("%H:%M:%S"),
                        "Side": "BUY" if t.get("side") == "buy" else "SELL",
                        "Tipo": "BUY 🟢" if t.get("side") == "buy" else "SELL 🔴",
                        "Prezzo": fmt_price(p),
                        "Controvalore": f"${val:,.0f}",
                        "RawVal": val if t.get("side") == "buy" else -val,
                        "Quantità": f"{q:,.2f}"
                    })
    except Exception:
        pass
    return pd.DataFrame(trades)

@st.cache_data(ttl=600)
def fetch_fear_and_greed():
    try:
        res = SESSION.get("https://api.alternative.me/fng/?limit=1", timeout=1.0).json()
        item = res["data"][0]
        return int(item["value"]), item["value_classification"]
    except Exception:
        return 65, "Greed"

@st.cache_data(ttl=45)
def load_all_market_intelligence():
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(fetch_asset_single_call, ASSETS))
    return [r for r in results if r is not None]

# --- ESECUZIONE VELOCE ---
data_market = load_all_market_intelligence()
fng_val, fng_label = fetch_fear_and_greed()
avg_bias = int(np.mean([x["score"] for x in data_market])) if data_market else 50
names_list = [d["name"] for d in data_market]
now_str = datetime.datetime.now().strftime("%H:%M:%S")

# --- HEADER STATS ---
st.markdown("### ⚡ Apex Terminal Pro")
st.markdown(f"<div class='sync-badge'>Live Feed OKX Core • Sync: <b>{now_str}</b></div>", unsafe_allow_html=True)

k1, k2, k3 = st.columns(3)
k1.metric("Fear & Greed", f"{fng_val}/100", delta=fng_label, delta_color="off")
k2.metric("Market Bias", f"{avg_bias}/100", delta="BULLISH" if avg_bias >= 50 else "BEARISH")
sqz_total = sum(1 for x in data_market if x["squeeze"])
k3.metric("Squeeze 1H", f"{sqz_total} Attivi", delta="Espansione" if sqz_total > 0 else "Stabile")

# --- NAVIGATION TABS ---
t_signals, t_heat, t_whales, t_calc, t_tv = st.tabs([
    "⚡ Segnali & Multi-TF",
    "🔥 Liquidity Cascades",
    "🐋 Tape Balene Live",
    "🎯 Risk & Position",
    "📈 TradingView Live"
])

# ==========================================
# TAB 1: SEGNALI & MULTI-TIMEFRAME
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
            <div style="margin-top:5px; font-size:0.85rem;">
                <span style="color:{item['badge_col']}; font-weight:700;">{item['action']}</span> 
                <span style="color:#64748b; margin-left:8px;">| Institutional Bias: <b>{item['score']}/100</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if item["squeeze"]:
            st.warning(f"⚡ **TTM Squeeze Attivo su {item['name']}:** Compressione 1H. Atteso breakout.")

        m1, m2, m3 = st.columns(3)
        m1.metric("RSI 1H", f"{item['rsi_1h']}")
        m2.metric("RSI 4H", f"{item['rsi_4h']}")
        m3.metric("RSI 1D", f"{item['rsi_1d']}")

        l1, l2, l3 = st.columns(3)
        l1.markdown(f"**{item['lvl1'][0]}:** `{fmt_price(item['lvl1'][1])}`")
        l2.markdown(f"**{item['lvl2'][0]}:** `{fmt_price(item['lvl2'][1])}`")
        l3.markdown(f"**{item['lvl3'][0]}:** `{fmt_price(item['lvl3'][1])}`")
        st.markdown("---")

# ==========================================
# TAB 2: LIQUIDITY CASCADES + TABLE
# ==========================================
with t_heat:
    st.markdown("##### 🔥 Liquidity Cascades (Cluster di Liquidità)")
    c_liq = st.selectbox("Seleziona Moneta:", names_list, index=0, key="liq_coin_select")
    m_liq = next(d for d in data_market if d["name"] == c_liq)

    p_liq = m_liq["price"]
    levs = [100, 50, 25, 10]
    liq_records = []

    for lev in levs:
        long_liq = p_liq * (1.0 - (0.90 / lev))
        short_liq = p_liq * (1.0 + (0.90 / lev))
        depth = round((100 / lev) * 2.5, 1)
        liq_records.append({"Leva": f"{lev}x", "Long_Price": long_liq, "Short_Price": short_liq, "Volume": depth})

    df_l = pd.DataFrame(liq_records)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df_l["Leva"],
        x=df_l["Volume"],
        orientation='h',
        name='Short Liq (Sopra)',
        marker=dict(color='#ff1744'),
        text=[fmt_price(x) for x in df_l["Short_Price"]],
        textposition='inside'
    ))
    fig.add_trace(go.Bar(
        y=df_l["Leva"],
        x=[-v for v in df_l["Volume"]],
        orientation='h',
        name='Long Liq (Sotto)',
        marker=dict(color='#00e676'),
        text=[fmt_price(x) for x in df_l["Long_Price"]],
        textposition='inside'
    ))

    fig.update_layout(
        barmode='overlay',
        paper_bgcolor='#080c14',
        plot_bgcolor='#0d1527',
        font=dict(color='#f1f5f9', size=11),
        height=260,
        margin=dict(l=5, r=5, t=10, b=5),
        xaxis=dict(showgrid=False, title="Rischio Cascade ($M)"),
        yaxis=dict(autorange="reversed"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    st.markdown("###### 📊 Trigger Target di Liquidazione")
    t_liq_summary = pd.DataFrame({
        "Leva": df_l["Leva"],
        "Caccia ai Long (Sotto)": [fmt_price(x) for x in df_l["Long_Price"]],
        "Caccia agli Short (Sopra)": [fmt_price(x) for x in df_l["Short_Price"]],
        "Impatto Stimato": [f"${v}M" for v in df_l["Volume"]]
    })
    st.dataframe(t_liq_summary, use_container_width=True, hide_index=True)

# ==========================================
# TAB 3: TAPE BALENE LIVE CON DELTA
# ==========================================
with t_whales:
    st.markdown("##### 🐋 Tape Ordini Istituzionali Live")
    w_coin = st.selectbox("Asset:", names_list, index=0, key="tape_coin_sel")
    w_meta = next(d for d in data_market if d["name"] == w_coin)

    threshold = st.select_slider("Filtro Taglia Minima ($)", options=[2000, 3000, 5000, 10000], value=3000)
    df_tape = fetch_okx_whale_trades(w_meta["inst"], min_usd=float(threshold))

    if not df_tape.empty:
        net_delta = df_tape["RawVal"].sum()
        total_vol = df_tape["RawVal"].abs().sum()
        buy_pct = (df_tape[df_tape["Side"] == "BUY"]["RawVal"].sum() / total_vol * 100) if total_vol > 0 else 50

        c_d1, c_d2 = st.columns(2)
        c_d1.metric("Delta Volumi Balene", f"${net_delta:,.0f}", delta="Pressione BUY" if net_delta > 0 else "Pressione SELL")
        c_d2.metric("Pressione Buyer", f"{buy_pct:.1f}%")

        display_df = df_tape[["Ora", "Tipo", "Prezzo", "Controvalore", "Quantità"]]
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=320)
    else:
        st.info(f"Nessun blocco > ${threshold:,} registrato su {w_coin} nell'ultimo blocco. Diminuisci la soglia.")

# ==========================================
# TAB 4: RISK & POSITION SIZING
# ==========================================
with t_calc:
    st.markdown("##### 🎯 Dimensionamento Posizione & Rischio")
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

    r1, r2 = st.columns(2)
    r1.metric("Valore Nominale", f"${total_pos_value:,.2f}")
    r2.metric("Rischio Max", f"-${max_loss_usd:,.2f}")

    r3, r4 = st.columns(2)
    r3.metric("Quantità Coin", f"{position_coins:,.4f} {calc_c}")
    r4.metric("Stop Loss ATR", fmt_price(stop_calc))

    st.markdown("###### 📋 Matrice Target Profit & Risk/Reward")
    rr_data = []
    for rr in [1.5, 2.0, 3.0, 4.0]:
        target_p = entry + (dist_sl * rr) if "LONG" in direction else entry - (dist_sl * rr)
        gain_usd = max_loss_usd * rr
        rr_data.append({
            "Rapporto R:R": f"1:{rr:.1f}",
            "Prezzo Target": fmt_price(target_p),
            "Profitto Lordo": f"+${gain_usd:,.2f}"
        })
    st.dataframe(pd.DataFrame(rr_data), use_container_width=True, hide_index=True)

# ==========================================
# TAB 5: TRADINGVIEW LIVE PRO
# ==========================================
with t_tv:
    tv_c = st.selectbox("Grafico Live:", names_list, index=0, key="tv_select")
    tv_meta = next(d for d in data_market if d["name"] == tv_c)

    tv_widget_html = f"""
    <div style="height:520px;width:100%">
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
        "hide_side_toolbar": false,
        "save_image": false,
        "container_id": "tv_chart"
      }});
      </script>
      <div id="tv_chart" style="height:100%;width:100%"></div>
    </div>
    """
    components.html(tv_widget_html, height=530)
