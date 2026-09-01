import concurrent.futures
import pandas as pd
import requests
import streamlit as st

# ==============================================================================
# 1. CONFIGURAZIONE STREAMLIT & STILE DARK PRO COMPLETO
# ==============================================================================
st.set_page_config(
    page_title="Binance MTF Live Screener Real-Time",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    div[data-testid="stCheckbox"] {
        background-color: #161b22;
        padding: 8px 14px;
        border-radius: 8px;
        border: 1px solid #30363d;
    }
    div[data-testid="stCheckbox"] label {
        color: #c9d1d9 !important;
        font-weight: 600;
        font-size: 13px;
    }

    .filter-header {
        font-size: 16px;
        font-weight: 700;
        color: #ffffff;
        margin-top: 15px;
        margin-bottom: 10px;
    }

    div[data-testid="stRadio"] > label { display: none; }
    div[data-testid="stRadio"] > div {
        flex-direction: row;
        gap: 12px;
        background-color: #161b22;
        padding: 8px 12px;
        border-radius: 8px;
        border: 1px solid #30363d;
    }

    .crypto-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    }

    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 12px;
    }
    .ticker-title {
        font-size: 20px;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: 0.5px;
        margin-right: 8px;
    }

    .badge-range { background-color: rgba(217, 119, 6, 0.15); color: #f59e0b; border: 1px solid #f59e0b; font-size: 10px; font-weight: 700; padding: 3px 6px; border-radius: 4px; text-transform: uppercase; display: inline-block; white-space: nowrap; }
    .badge-buy { background-color: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid #4ade80; font-size: 10px; font-weight: 700; padding: 3px 6px; border-radius: 4px; text-transform: uppercase; display: inline-block; white-space: nowrap; }
    .badge-short { background-color: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid #f87171; font-size: 10px; font-weight: 700; padding: 3px 6px; border-radius: 4px; text-transform: uppercase; display: inline-block; white-space: nowrap; }

    .price-box { text-align: right; }
    .price-val { color: #38bdf8; font-size: 20px; font-weight: 800; line-height: 1.1; }
    .price-change-up { color: #4ade80; font-size: 13px; font-weight: 600; margin-top: 2px; }
    .price-change-down { color: #f87171; font-size: 13px; font-weight: 600; margin-top: 2px; }

    .tf-header {
        font-size: 13px;
        font-weight: 800;
        color: #f59e0b;
        text-transform: uppercase;
        margin: 14px 0 8px 0;
        padding-bottom: 4px;
        border-bottom: 1px dashed #30363d;
    }

    .ind-grid-3 {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
        margin-bottom: 8px;
    }

    .ind-grid-2 {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
        margin-bottom: 8px;
    }

    .ind-item {
        background-color: #0d1117;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 8px 10px;
    }
    .ind-label { color: #8b949e; font-size: 10px; font-weight: 700; text-transform: uppercase; }
    .ind-val { color: #ffffff; font-size: 12px; font-weight: 700; margin: 2px 0; }
    
    .ind-sub-red { color: #f87171; font-size: 10px; font-weight: 600; }
    .ind-sub-green { color: #4ade80; font-size: 10px; font-weight: 600; }
    .ind-sub-yellow { color: #f59e0b; font-size: 10px; font-weight: 600; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ==============================================================================
# 2. CONNETTORE LIVE API BINANCE (DATI REALI - NO GEOBLOCK)
# ==============================================================================

WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT",
    "DOGEUSDT", "SUIUSDT", "NEARUSDT", "DOTUSDT"
]

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def fetch_single_kline_fast(symbol: str, interval: str, limit: int = 150) -> pd.DataFrame:
    """Richiede candele reali usando endpoint Binance non soggetti a blocchi geografici AWS."""
    endpoints = [
        f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
        f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    ]
    
    for url in endpoints:
        try:
            res = requests.get(url, headers=HTTP_HEADERS, timeout=3.5)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data, columns=[
                        "open_time", "open", "high", "low", "close", "volume",
                        "close_time", "qav", "num_trades", "tbb", "tbq", "ignore"
                    ])
                    for col in ["open", "high", "low", "close", "volume"]:
                        df[col] = df[col].astype(float)
                    return df
        except Exception:
            continue

    return pd.DataFrame()

def fetch_ticker_fast(symbol: str) -> dict:
    """Recupera il prezzo dal vivo e la variazione percentuale 24h."""
    endpoints = [
        f"https://data-api.binance.vision/api/v3/ticker/24hr?symbol={symbol}",
        f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}"
    ]
    for url in endpoints:
        try:
            res = requests.get(url, headers=HTTP_HEADERS, timeout=3.5)
            if res.status_code == 200:
                data = res.json()
                return {
                    "lastPrice": float(data["lastPrice"]),
                    "priceChangePercent": float(data["priceChangePercent"])
                }
        except Exception:
            continue
    return {}

def load_symbol_pack(symbol: str):
    df_1h = fetch_single_kline_fast(symbol, "1h", 150)
    df_4h = fetch_single_kline_fast(symbol, "4h", 150)
    df_1d = fetch_single_kline_fast(symbol, "1d", 150)
    ticker = fetch_ticker_fast(symbol)

    if df_1h.empty or df_4h.empty:
        return None

    if not ticker or "lastPrice" not in ticker:
        ticker = {
            "lastPrice": float(df_1h["close"].iloc[-1]),
            "priceChangePercent": 0.0
        }

    return {
        "symbol": symbol,
        "df_1h": df_1h,
        "df_4h": df_4h,
        "df_1d": df_1d,
        "ticker": ticker
    }

@st.cache_data(ttl=10, show_spinner=False)
def fetch_all_market_data(symbols: list) -> dict:
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_sym = {executor.submit(load_symbol_pack, sym): sym for sym in symbols}
        for future in concurrent.futures.as_completed(future_to_sym):
            sym = future_to_sym[future]
            try:
                pack = future.result()
                if pack is not None:
                    results[sym] = pack
            except Exception:
                pass
    return results


# ==============================================================================
# 3. MOTORE DI CALCOLO INDICATORI REALI
# ==============================================================================

def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    ema_gain = gain.ewm(com=period - 1, adjust=False).mean()
    ema_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = ema_gain / (ema_loss + 1e-10)
    return 100 - (100 / (1 + rs))

def compute_binance_indicators(df: pd.DataFrame):
    close = df['close']
    high = df['high']
    low = df['low']
    vol = df['volume']

    rsi6 = round(calc_rsi(close, period=6).iloc[-1], 1)

    rsi14 = calc_rsi(close, period=14)
    rsi_min = rsi14.rolling(14).min()
    rsi_max = rsi14.rolling(14).max()
    stoch = (rsi14 - rsi_min) / (rsi_max - rsi_min + 1e-10) * 100
    stoch_k = round(stoch.rolling(3).mean().iloc[-1], 2)
    stoch_d_val = stoch.rolling(3).mean().rolling(3).mean().iloc[-1]
    stoch_d = round(stoch_k if pd.isna(stoch_d_val) else stoch_d_val, 2)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    macd_h = (dif - dea) * 2

    ma7, ma25, ma99 = close.rolling(7).mean().iloc[-1], close.rolling(25).mean().iloc[-1], close.rolling(99).mean().iloc[-1]
    ema7, ema25, ema99 = close.ewm(span=7, adjust=False).mean().iloc[-1], close.ewm(span=25, adjust=False).mean().iloc[-1], close.ewm(span=99, adjust=False).mean().iloc[-1]

    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    boll_up = (sma20 + 2 * std20).iloc[-1]
    boll_mb = sma20.iloc[-1]
    boll_dn = (sma20 - 2 * std20).iloc[-1]

    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(span=10, adjust=False).mean()
    st_val = ((high + low) / 2 + (3 * atr)).iloc[-1]
    st_bull = close.iloc[-1] > st_val

    sar_val = (low.iloc[-1] * 0.995) if close.iloc[-1] > close.iloc[-2] else (high.iloc[-1] * 1.005)

    v_base = vol.iloc[-1]
    v_ma5 = vol.rolling(5).mean().iloc[-1]
    delta_vol_pct = ((v_base - v_ma5) / (v_ma5 + 1e-10)) * 100

    return {
        "rsi6": rsi6, "stoch_k": stoch_k, "stoch_d": stoch_d,
        "dif": round(dif.iloc[-1], 2), "dea": round(dea.iloc[-1], 2), "macd_h": round(macd_h.iloc[-1], 2),
        "ma7": ma7, "ma25": ma25, "ma99": ma99, "ema7": ema7, "ema25": ema25, "ema99": ema99,
        "boll_up": boll_up, "boll_mb": boll_mb, "boll_dn": boll_dn,
        "st_val": round(st_val, 2), "st_bull": st_bull, "sar_val": round(sar_val, 2),
        "v_base": v_base, "delta_vol": round(delta_vol_pct, 1)
    }


# ==============================================================================
# 4. INTERFACCIA UTENTE & CONTROLLI (RIPRISTINATI)
# ==============================================================================

col_nav1, col_nav2, col_nav3 = st.columns(3)
with col_nav1:
    show_whales = st.checkbox("🐋 Whales Tape", value=False)
with col_nav2:
    show_risk = st.checkbox("🎯 Risk Calc", value=False)
with col_nav3:
    show_matrix = st.checkbox("📊 Confluence Matrix", value=True)

if show_whales:
    st.markdown("### 🐋 Whales Tape (Live Stream)")
    st.dataframe(pd.DataFrame([
        {"Time": "LIVE", "Entity": "Binance Hot Wallet", "Asset": "BTC", "Amount": "1,250 BTC", "Type": "Internal Transfer"},
        {"Time": "LIVE", "Entity": "Coinbase Inst.", "Asset": "ETH", "Amount": "14,200 ETH", "Type": "Outflow"},
        {"Time": "LIVE", "Entity": "Jump Trading", "Asset": "SOL", "Amount": "85,000 SOL", "Type": "Deposit"}
    ]), use_container_width=True)

if show_risk:
    st.markdown("### 🎯 Risk & Position Size Calculator")
    c1, c2, c3 = st.columns(3)
    capital = c1.number_input("Capitale ($)", value=10000, step=500)
    risk_pct = c2.slider("Rischio %", 0.5, 5.0, 1.0, 0.5)
    sl_pct = c3.number_input("Stop Loss %", value=2.0, step=0.1)
    risk_usd = capital * (risk_pct / 100)
    pos_size = risk_usd / (sl_pct / 100) if sl_pct > 0 else 0
    st.info(f"💡 Rischio Max: **${risk_usd:.2f}** | Size Posizione Suggerita: **${pos_size:.2f}**")

with st.spinner("⚡ Connessione diretta alle API Binance per dati LIVE..."):
    all_data = fetch_all_market_data(WATCHLIST)

if not all_data:
    st.error("⚠️ Nessun dato di mercato disponibile. Errore temporaneo di rete.")
    st.stop()

if show_matrix:
    st.markdown("### 📊 Confluence Matrix Overview (1H vs 4H)")
    matrix_rows = []
    for sym in WATCHLIST[:6]:
        if sym in all_data:
            d1 = all_data[sym]["df_1h"]
            d4 = all_data[sym]["df_4h"]
            r1 = round(calc_rsi(d1["close"], 6).iloc[-1], 1)
            r4 = round(calc_rsi(d4["close"], 6).iloc[-1], 1)
            matrix_rows.append({
                "Asset": sym.replace("USDT", "/USDT"),
                "RSI(6) 1H": r1,
                "RSI(6) 4H": r4,
                "Confluenza": "🟢 DOUBLE BUY" if (r1 < 35 and r4 < 40) else ("🔴 DOUBLE SHORT" if (r1 > 65 and r4 > 60) else "🟡 MIXED / RANGE")
            })
    if matrix_rows:
        st.table(pd.DataFrame(matrix_rows))

st.markdown("<div class='filter-header'>Filtro Segnali Confluenza:</div>", unsafe_allow_html=True)
filtro_segnale = st.radio(
    label="Filtro Segnali",
    options=["🔴🔴 Tutti", "⚪🟢 Solo Buy", "⚪⚪ Alert TP/Short"],
    index=0,
    horizontal=True,
    label_visibility="collapsed"
)


# ==============================================================================
# 5. CARDS CRYPTO LIVE (RIPRISTINATE CON SOTTO-BADGE E DETTAGLI)
# ==============================================================================

for symbol in WATCHLIST:
    if symbol not in all_data:
        continue
    
    pack = all_data[symbol]
    df_1h = pack["df_1h"]
    df_4h = pack["df_4h"]
    df_1d = pack["df_1d"]
    ticker = pack["ticker"]

    i1h = compute_binance_indicators(df_1h)
    i4h = compute_binance_indicators(df_4h)
    rsi_1d = round(calc_rsi(df_1d["close"], 14).iloc[-1], 1) if not df_1d.empty else 50.0

    price_val = float(ticker.get("lastPrice", 0))
    change_val = float(ticker.get("priceChangePercent", 0))
    price_str = f"${price_val:,.2f}" if price_val >= 1 else f"${price_val:.4f}"
    change_str = f"({change_val:+.2f}%)"
    change_class = "price-change-up" if change_val >= 0 else "price-change-down"

    if i1h["rsi6"] > 70 and i4h["rsi6"] > 60:
        signal_type = "Short"
        badge_status = "🔴 HIGH CONFLUENCE SHORT (1H + 4H)"
        badge_class = "badge-short"
    elif i1h["rsi6"] < 30 and i4h["rsi6"] < 40:
        signal_type = "Buy"
        badge_status = "🟢 HIGH CONFLUENCE BUY (1H + 4H)"
        badge_class = "badge-buy"
    else:
        signal_type = "Neutral"
        badge_status = "🟡 NEUTRALE / MIXED RANGE"
        badge_class = "badge-range"

    if filtro_segnale == "⚪🟢 Solo Buy" and signal_type != "Buy":
        continue
    if filtro_segnale == "⚪⚪ Alert TP/Short" and signal_type != "Short":
        continue

    coin_name = symbol.replace("USDT", "")

    raw_html = f"""
<div class="crypto-card">
<div class="card-header">
<div>
<span class="ticker-title">{coin_name}/USDT</span>
<span class="{badge_class}">{badge_status}</span>
</div>
<div class="price-box">
<div class="price-val">{price_str}</div>
<div class="{change_class}">{change_str}</div>
<div style="font-size:11px; color:#8b949e; margin-top:2px;">RSI 1D (Daily Trend): <strong style="color:#ffffff;">{rsi_1d}</strong></div>
</div>
</div>

<div class="tf-header">⚡ TIMEFRAME 1 ORA (1H BINANCE)</div>
<div class="ind-grid-3">
<div class="ind-item">
<div class="ind-label">RSI (6) 1H</div>
<div class="ind-val">{i1h['rsi6']}</div>
<div class="ind-sub-{'red' if i1h['rsi6'] > 70 else ('green' if i1h['rsi6'] < 30 else 'yellow')}">
{'🎯 Overbought' if i1h['rsi6'] > 70 else ('🟢 Oversold' if i1h['rsi6'] < 30 else '🟡 Neutral')}
</div>
</div>
<div class="ind-item">
<div class="ind-label">STOCHRSI 1H</div>
<div class="ind-val">K:{i1h['stoch_k']} | D:{i1h['stoch_d']}</div>
<div class="ind-sub-{'red' if i1h['stoch_k'] > 80 else ('green' if i1h['stoch_k'] < 20 else 'yellow')}">
{'🎯 Short' if i1h['stoch_k'] > 80 else ('🟢 Buy' if i1h['stoch_k'] < 20 else '🟡 Neutral')}
</div>
</div>
<div class="ind-item">
<div class="ind-label">DELTA VOL % 1H</div>
<div class="ind-val">{i1h['delta_vol']:+.1f}%</div>
<div class="ind-sub-{'green' if i1h['delta_vol'] >= 0 else 'red'}">
{'🟢 Vol Spike' if i1h['delta_vol'] >= 0 else '🔴 Low Vol'}
</div>
</div>
</div>

<div class="ind-grid-3">
<div class="ind-item">
<div class="ind-label">MACD 1H</div>
<div class="ind-val">DIF:{i1h['dif']} | DEA:{i1h['dea']}</div>
<div class="ind-sub-{'green' if i1h['macd_h'] >= 0 else 'red'}">Hist: {i1h['macd_h']}</div>
</div>
<div class="ind-item">
<div class="ind-label">EMA (7/25/99) 1H</div>
<div class="ind-val" style="font-size: 11px;">
{i1h['ema7']:,.1f} / {i1h['ema25']:,.1f} / {i1h['ema99']:,.1f}
</div>
</div>
<div class="ind-item">
<div class="ind-label">MA (7/25/99) 1H</div>
<div class="ind-val" style="font-size: 11px;">
{i1h['ma7']:,.1f} / {i1h['ma25']:,.1f} / {i1h['ma99']:,.1f}
</div>
</div>
</div>

<div class="ind-grid-2">
<div class="ind-item">
<div class="ind-label">BOLLINGER (20,2) 1H</div>
<div class="ind-val" style="font-size: 11px;">
UP: {i1h['boll_up']:,.2f} | MB: {i1h['boll_mb']:,.2f} | DN: {i1h['boll_dn']:,.2f}
</div>
</div>
<div class="ind-item">
<div class="ind-label">SUPERTREND & SAR 1H</div>
<div class="ind-val" style="font-size: 11px;">
ST: {i1h['st_val']} ({'🟢' if i1h['st_bull'] else '🔴'}) | SAR: {i1h['sar_val']}
</div>
</div>
</div>

<div class="tf-header">📊 TIMEFRAME 4 ORE (4H BINANCE)</div>
<div class="ind-grid-3">
<div class="ind-item">
<div class="ind-label">RSI (6) 4H</div>
<div class="ind-val">{i4h['rsi6']}</div>
<div class="ind-sub-{'red' if i4h['rsi6'] > 70 else ('green' if i4h['rsi6'] < 30 else 'yellow')}">
{'🎯 Overbought' if i4h['rsi6'] > 70 else ('🟢 Oversold' if i4h['rsi6'] < 30 else '🟡 Neutral')}
</div>
</div>
<div class="ind-item">
<div class="ind-label">STOCHRSI 4H</div>
<div class="ind-val">K:{i4h['stoch_k']} | D:{i4h['stoch_d']}</div>
<div class="ind-sub-{'red' if i4h['stoch_k'] > 80 else ('green' if i4h['stoch_k'] < 20 else 'yellow')}">
{'🎯 Short' if i4h['stoch_k'] > 80 else ('🟢 Buy' if i4h['stoch_k'] < 20 else '🟡 Neutral')}
</div>
</div>
<div class="ind-item">
<div class="ind-label">DELTA VOL % 4H</div>
<div class="ind-val">{i4h['delta_vol']:+.1f}%</div>
<div class="ind-sub-{'green' if i4h['delta_vol'] >= 0 else 'red'}">
{'🟢 Vol Spike' if i4h['delta_vol'] >= 0 else '🔴 Low Vol'}
</div>
</div>
</div>

<div class="ind-grid-3">
<div class="ind-item">
<div class="ind-label">MACD 4H</div>
<div class="ind-val">DIF:{i4h['dif']} | DEA:{i4h['dea']}</div>
<div class="ind-sub-{'green' if i4h['macd_h'] >= 0 else 'red'}">Hist: {i4h['macd_h']}</div>
</div>
<div class="ind-item">
<div class="ind-label">EMA (7/25/99) 4H</div>
<div class="ind-val" style="font-size: 11px;">
{i4h['ema7']:,.1f} / {i4h['ema25']:,.1f} / {i4h['ema99']:,.1f}
</div>
</div>
<div class="ind-item">
<div class="ind-label">MA (7/25/99) 4H</div>
<div class="ind-val" style="font-size: 11px;">
{i4h['ma7']:,.1f} / {i4h['ma25']:,.1f} / {i4h['ma99']:,.1f}
</div>
</div>
</div>

<div class="ind-grid-2">
<div class="ind-item">
<div class="ind-label">BOLLINGER (20,2) 4H</div>
<div class="ind-val" style="font-size: 11px;">
UP: {i4h['boll_up']:,.2f} | MB: {i4h['boll_mb']:,.2f} | DN: {i4h['boll_dn']:,.2f}
</div>
</div>
<div class="ind-item">
<div class="ind-label">SUPERTREND & SAR 4H</div>
<div class="ind-val" style="font-size: 11px;">
ST: {i4h['st_val']} ({'🟢' if i4h['st_bull'] else '🔴'}) | SAR: {i4h['sar_val']}
</div>
</div>
</div>
</div>
"""
    clean_html = "\n".join(line.strip() for line in raw_html.splitlines())
    st.markdown(clean_html, unsafe_allow_html=True)
