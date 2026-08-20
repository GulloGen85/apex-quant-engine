import datetime
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# --- CONFIGURAZIONE ---
st.set_page_config(
    page_title="Apex Institutional Terminal Pro",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed"
)

# --- CSS DARK THEME ---
st.markdown("""
<style>
    .stApp { background-color: #080c14; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .block-container { padding-top: 0.8rem !important; padding-bottom: 2rem !important; padding-left: 0.8rem !important; padding-right: 0.8rem !important; }
    div[data-testid="stMetricValue"] { font-size: 1.15rem !important; color: #00f2fe !important; font-weight: 800; }
    div[data-testid="stMetricLabel"] { font-size: 0.75rem !important; color: #94a3b8 !important; font-weight: 600; }
    .stTabs [data-baseweb="tab-list"] { display: flex; overflow-x: auto; white-space: nowrap; gap: 6px; padding-bottom: 6px; border-bottom: 1px solid #1e293b; }
    .stTabs [data-baseweb="tab"] { background-color: #0d1527; border-radius: 6px; color: #94a3b8; padding: 6px 14px; font-size: 0.82rem; font-weight: 700; border: 1px solid #1e293b; }
    .stTabs [aria-selected="true"] { background-color: #1e293b !important; color: #00f2fe !important; border: 1px solid #00f2fe !important; }
    .card-asset { background: #0d1527; border: 1px solid #1e293b; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
    .sync-badge { font-size: 0.72rem; color: #64748b; text-align: right; margin-top: -10px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- MATRICE ASSET ISTITUZIONALE ---
BASE_ASSETS = [
    {"name": "BTC", "tv": "BINANCE:BTCUSDT", "price": 68450.0, "pct": 1.45, "rsi_1h": 58.2, "rsi_4h": 62.0, "rsi_1d": 54.0, "squeeze": True, "score": 75},
    {"name": "ETH", "tv": "BINANCE:ETHUSDT", "price": 2240.0, "pct": -0.80, "rsi_1h": 46.5, "rsi_4h": 48.0, "rsi_1d": 42.0, "squeeze": False, "score": 44},
    {"name": "SOL", "tv": "BINANCE:SOLUSDT", "price": 87.5, "pct": 3.20, "rsi_1h": 66.0, "rsi_4h": 69.5, "rsi_1d": 59.0, "squeeze": True, "score": 82},
    {"name": "NEAR", "tv": "BINANCE:NEARUSDT", "price": 1.72, "pct": 0.50, "rsi_1h": 51.0, "rsi_4h": 52.0, "rsi_1d": 49.0, "squeeze": False, "score": 52},
    {"name": "TAO", "tv": "BINANCE:TAOUSDT", "price": 208.5, "pct": 4.10, "rsi_1h": 72.0, "rsi_4h": 74.0, "rsi_1d": 65.0, "squeeze": False, "score": 78},
    {"name": "WLD", "tv": "BINANCE:WLDUSDT", "price": 1.22, "pct": -2.10, "rsi_1h": 36.0, "rsi_4h": 39.0, "rsi_1d": 33.0, "squeeze": False, "score": 28},
    {"name": "ONDO", "tv": "BINANCE:ONDOUSDT", "price": 0.66, "pct": 1.10, "rsi_1h": 55.0, "rsi_4h": 58.0, "rsi_1d": 51.0, "squeeze": True, "score": 68},
    {"name": "ZEC", "tv": "BINANCE:ZECUSDT", "price": 31.2, "pct": -0.30, "rsi_1h": 48.0, "rsi_4h": 45.0, "rsi_1d": 40.0, "squeeze": False, "score": 46}
]

def fmt_price(p: float) -> str:
    if p >= 1000:
        return f"${p:,.0f}"
    elif p >= 1:
        return f"${p:,.2f}"
    else:
        return f"${p:.4f}"

# Elaborazione analitica locale istantanea
data_market = []
for a in BASE_ASSETS:
    p = a["price"]
    atr = p * 0.022
    score = a["score"]
    
    if a["rsi_1h"] >= 75 or a["rsi_4h"] >= 78:
        action = "⚠️ PRENDI PROFITTO (IPERCOMPRATO)"
        action_code = "TP"
        badge_col = "#ff9100"
        lvl1_lbl, lvl1_val = "🛡️ Trailing SL", p - (0.8 * atr)
        lvl2_lbl, lvl2_val = "🎯 Dip Buy 1", p - (1.8 * atr)
        lvl3_lbl, lvl3_val = "📉 Supporto Dip", p - (3.2 * atr)
    elif score <= 38:
        action = "🔴 DISTRIBUISCI / SHORT"
        action_code = "SELL"
        badge_col = "#ff1744"
        lvl1_lbl, lvl1_val = "🛑 Stop Loss", p + (1.5 * atr)
        lvl2_lbl, lvl2_val = "🎯 TP1 Short", p - (2.0 * atr)
        lvl3_lbl, lvl3_val = "🚀 TP2 Short", p - (3.8 * atr)
    elif score >= 60:
        action = "🟢 ACCUMULA / LONG"
        action_code = "BUY"
        badge_col = "#00e676"
        lvl1_lbl, lvl1_val = "🛑 Stop Loss", p - (1.5 * atr)
        lvl2_lbl, lvl2_val = "🎯 TP1 Long", p + (2.0 * atr)
        lvl3_lbl, lvl3_val = "🚀 TP2 Long", p + (3.8 * atr)
    else:
        action = "💤 NEUTRALE / ATTENDI RANGE"
        action_code = "NEUTRAL"
        badge_col = "#94a3b8"
        lvl1_lbl, lvl1_val = "🧱 Supporto", p - (1.5 * atr)
        lvl2_lbl, lvl2_val = "🚧 Pivot", p
        lvl3_lbl, lvl3_val = "🧗 Resistenza", p + (1.5 * atr)

    data_market.append({
        **a,
        "atr": atr,
        "action": action,
        "action_code": action_code,
        "badge_col": badge_col,
        "lvl1": (lvl1_lbl, lvl1_val),
        "lvl2": (lvl2_lbl, lvl2_val),
        "lvl3": (lvl3_lbl, lvl3_val)
    })

names_list = [d["name"] for d in data_market]
avg_bias = int(np.mean([x["score"] for x in data_market]))
sqz_count = sum(1 for x in data_market if x["squeeze"])
now_str = datetime.datetime.now().strftime("%H:%M:%S")

# --- HEADER METRICS ---
st.markdown("### ⚡ Apex Terminal Pro")
st.markdown(f"<div class='sync-badge'>Ultra-Fast Execution Engine • Sync: <b>{now_str}</b></div>", unsafe_allow_html=True)

k1, k2, k3 = st.columns(3)
k1.metric("Market Sentiment", "65/100", delta="Greed", delta_color="off")
k2.metric("Institutional Bias", f"{avg_bias}/100", delta="BULLISH" if avg_bias >= 50 else "BEARISH")
k3.metric("Squeeze Attivi", f"{sqz_count} Asset", delta="Compressione" if sqz_count > 0 else "Stabile")

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

        pct_color = "#00e676" if item["pct"] >= 0 else "#ff1744"

        st.markdown(f"""
        <div class="card-asset">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:1.15rem; font-weight:800;">{item['name']}/USDT</span>
                <span style="font-size:1.15rem; font-weight:800; color:#00f2fe;">{fmt_price(item['price'])} 
                    <span style="font-size:0.8rem; color:{pct_color};">({item['pct']:+.2f}%)</span>
                </span>
            </div>
            <div style="margin-top:6px; font-size:0.85rem;">
                <span style="color:{item['badge_col']}; font-weight:700;">{item['action']}</span> 
                <span style="color:#64748b; margin-left:8px;">| Institutional Bias: <b>{item['score']}/100</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if item["squeeze"]:
            st.warning(f"⚡ **TTM Squeeze Attivo su {item['name']}:** Compressione del range. Atteso breakout.")

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
# TAB 2: LIQUIDITY CASCADES
# ==========================================
with t_heat:
    st.markdown("##### 🔥 Liquidity Cascades (Cluster di Liquidazione)")
    c_liq = st.selectbox("Seleziona Moneta:", names_list, index=0, key="liq_c_sel")
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

    t_liq_summary = pd.DataFrame({
        "Leva": df_l["Leva"],
        "Caccia ai Long (Sotto)": [fmt_price(x) for x in df_l["Long_Price"]],
        "Caccia agli Short (Sopra)": [fmt_price(x) for x in df_l["Short_Price"]],
        "Impatto Stimato": [f"${v}M" for v in df_l["Volume"]]
    })
    st.dataframe(t_liq_summary, use_container_width=True, hide_index=True)

# ==========================================
# TAB 3: TAPE BALENE LIVE
# ==========================================
with t_whales:
    st.markdown("##### 🐋 Tape Ordini Istituzionali")
    w_coin = st.selectbox("Asset:", names_list, index=0, key="tape_c_sel")
    w_meta = next(d for d in data_market if d["name"] == w_coin)

    threshold = st.select_slider("Filtro Taglia Minima ($)", options=[2000, 5000, 10000, 25000], value=5000)
    
    # Generazione tape dinamico basato sui livelli dell'asset
    sim_trades = []
    base_val = w_meta["price"]
    for i in range(10):
        side = "BUY" if (i % 2 == 0 or i == 3) else "SELL"
        mult = 1.0 + (0.0005 * (i - 4))
        p_trade = base_val * mult
        amt_usd = float(threshold) * (1.2 + (i * 0.45))
        qty = amt_usd / p_trade
        sim_trades.append({
            "Ora": (datetime.datetime.now() - datetime.timedelta(seconds=i*38)).strftime("%H:%M:%S"),
            "Side": side,
            "Tipo": "BUY 🟢" if side == "BUY" else "SELL 🔴",
            "Prezzo": fmt_price(p_trade),
            "Controvalore": f"${amt_usd:,.0f}",
            "RawVal": amt_usd if side == "BUY" else -amt_usd,
            "Quantità": f"{qty:,.2f}"
        })

    df_tape = pd.DataFrame(sim_trades)
    net_delta = df_tape["RawVal"].sum()
    total_vol = df_tape["RawVal"].abs().sum()
    buy_pct = (df_tape[df_tape["Side"] == "BUY"]["RawVal"].sum() / total_vol * 100) if total_vol > 0 else 50

    c_d1, c_d2 = st.columns(2)
    c_d1.metric("Delta Volumi Balene", f"${net_delta:,.0f}", delta="Pressione BUY" if net_delta > 0 else "Pressione SELL")
    c_d2.metric("Pressione Buyer", f"{buy_pct:.1f}%")

    st.dataframe(df_tape[["Ora", "Tipo", "Prezzo", "Controvalore", "Quantità"]], use_container_width=True, hide_index=True, height=320)

# ==========================================
# TAB 4: RISK & POSITION SIZING
# ==========================================
with t_calc:
    st.markdown("##### 🎯 Dimensionamento Posizione & Rischio")
    calc_c = st.selectbox("Asset Operativo:", names_list, index=0, key="calc_sel_c")
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
    tv_c = st.selectbox("Grafico Live:", names_list, index=0, key="tv_sel_c")
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
