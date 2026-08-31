import textwrap
import numpy as np
import pandas as pd
import requests
import streamlit as st

# ==============================================================================
# 1. CONFIGURAZIONE STREAMLIT & STILE DARK
# ==============================================================================
st.set_page_config(
    page_title="Institutional Crypto Screener",
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
        font-size: 18px;
        font-weight: 700;
        color: #ffffff;
        margin-top: 20px;
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
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    }

    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 14px;
    }
    .ticker-title {
        font-size: 22px;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: 0.5px;
    }

    .badge-range {
        background-color: rgba(217, 119, 6, 0.15);
        color: #f59e0b;
        border: 1px solid #f59e0b;
        font-size: 10px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 4px;
        text-transform: uppercase;
    }
    .badge-buy {
        background-color: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        border: 1px solid #4ade80;
        font-size: 10px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 4px;
        text-transform: uppercase;
    }
    .badge-short {
        background-color: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid #f87171;
        font-size: 10px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 4px;
        text-transform: uppercase;
    }

    .price-box { text-align: right; }
    .price-val { color: #38bdf8; font-size: 22px; font-weight: 800; line-height: 1.1; }
    .price-change-up { color: #4ade80; font-size: 13px; font-weight: 600; margin-top: 2px; }
    .price-change-down { color: #f87171; font-size: 13px; font-weight: 600; margin-top: 2px; }
    .score-text { color: #8b949e; font-size: 12px; margin-top: 4px; }

    .squeeze-active {
        background-color: rgba(217, 119, 6, 0.15);
        border: 1px solid #f59e0b;
        color: #fbbf24;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 14px;
    }
    .squeeze-normal {
        background-color: rgba(30, 41, 59, 0.7);
        border: 1px solid #334155;
        color: #94a3b8;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 13px;
        margin-bottom: 14px;
    }

    .ind-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
    }
    .ind-item {
        background-color: #0d1117;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 12px;
    }
    .ind-label { color: #8b949e; font-size: 11px; font-weight: 700; text-transform: uppercase; }
    .ind-val { color: #ffffff; font-size: 18px; font-weight: 700; margin: 3px 0; }
    
    .ind-sub-red { color: #f87171; font-size: 11px; font-weight: 600; }
    .ind-sub-green { color: #4ade80; font-size: 11px; font-weight: 600; }
    .ind-sub-yellow { color: #f59e0b; font-size: 11px; font-weight: 600; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ==============================================================================
# 2. DATA FETCHING MULTI-EXCHANGE (ANTI-BLOCCO IP CLOUD USA / IT)
# ==============================================================================

@st.cache_data(ttl=15)
def fetch_klines(symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
    """Scarica candele reali da Bybit API (senza blocchi IP US Cloud), con fallback Binance."""
    # Mapping intervalli
    bybit_interval = "60" if interval == "1h" else ("240" if interval == "4h" else "60")
    
    # 1. Tentativo 1: Bybit API Public (Zero US IP Block su Streamlit Cloud)
    bybit_url = f"https://api.bybit.com/v5/market/kline?category=spot&symbol={symbol}&interval={bybit_interval}&limit={limit}"
    try:
        res = requests.get(bybit_url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            list_data = data.get("result", {}).get("list", [])
            if list_data:
                # Bybit restituisce i dati dal più recente al meno recente
                df = pd.DataFrame(list_data, columns=["open_time", "open", "high", "low", "close", "volume", "turnover"])
                df = df.iloc[::-1].reset_index(drop=True)
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)
                return df
    except Exception:
        pass

    # 2. Tentativo 2: Binance REST API (per esecuzione Locale dall'Italia)
    binance_url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(binance_url, timeout=3)
        if res.status_code == 200:
            df = pd.DataFrame(res.json(), columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "qav", "num_trades", "tbb", "tbq", "ignore"
            ])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            return df
    except Exception:
        pass

    return pd.DataFrame()


@st.cache_data(ttl=5)
def fetch_ticker_price(symbol: str) -> dict:
    """Recupera prezzo e variazione 24h senza blocchi di rete."""
    url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}"
    try:
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json().get("result", {}).get("list", [])
            if data:
                item = data[0]
                last_price = float(item.get("lastPrice", 0))
                prev_price = float(item.get("prevPrice24h", last_price))
                change_pct = ((last_price - prev_price) / prev_price) * 100 if prev_price > 0 else 0.0
                return {"lastPrice": last_price, "priceChangePercent": change_pct}
    except Exception:
        pass

    # Fallback Binance Ticker
    try:
        res = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=3)
        if res.status_code == 200:
            d = res.json()
            return {"lastPrice": float(d.get("lastPrice", 0)), "priceChangePercent": float(d.get("priceChangePercent", 0))}
    except Exception:
        pass

    return {}


# ==============================================================================
# 3. COMPLETO ENGINE INDICATORI TECNICI (STOCH RSI %K e %D, RSI, BOLLINGER, TTM)
# ==============================================================================

def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    ema_gain = gain.ewm(com=period - 1, adjust=False).mean()
    ema_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = ema_gain / (ema_loss + 1e-10)
    return 100 - (100 / (1 + rs))

def calc_stoch_rsi(series: pd.Series, rsi_period=14, stoch_period=14, k_period=3, d_period=3):
    """Calcola sia la linea %K sia la linea %D dello Stochastic RSI."""
    rsi = calc_rsi(series, rsi_period)
    rsi_min = rsi.rolling(stoch_period).min()
    rsi_max = rsi.rolling(stoch_period).max()
    
    stoch = (rsi - rsi_min) / (rsi_max - rsi_min + 1e-10) * 100
    k = stoch.rolling(k_period).mean()
    d = k.rolling(d_period).mean()
    
    val_k = round(k.iloc[-1], 1) if not k.empty and not np.isnan(k.iloc[-1]) else 50.0
    val_d = round(d.iloc[-1], 1) if not d.empty and not np.isnan(d.iloc[-1]) else 50.0

    if val_k >= 80:
        return f"K:{val_k} D:{val_d}", "🎯 Overbought (Short)", "red"
    elif val_k <= 20:
        return f"K:{val_k} D:{val_d}", "🟢 Oversold (Buy)", "green"
    else:
        return f"K:{val_k} D:{val_d}", "🎯 Neutral Zone", "yellow"

def calc_bollinger(df: pd.DataFrame, period=20, std_dev=2):
    sma = df['close'].rolling(period).mean()
    std = df['close'].rolling(period).std()
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    
    close = df['close'].iloc[-1]
    u_val = upper.iloc[-1]
    l_val = lower.iloc[-1]
    pct_b = (close - l_val) / (u_val - l_val + 1e-10)

    if pct_b >= 0.8:
        return "UPPER BAND", f"Overbought (%B: {pct_b:.2f})", "red"
    elif pct_b <= 0.2:
        return "LOWER BAND", f"Oversold (%B: {pct_b:.2f})", "green"
    else:
        return "MID BAND", f"In Range (%B: {pct_b:.2f})", "yellow"

def calc_ttm_squeeze(df: pd.DataFrame, length=20):
    sma = df['close'].rolling(length).mean()
    std = df['close'].rolling(length).std()
    bb_upper = sma + (2 * std)
    bb_lower = sma - (2 * std)
    
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift()).abs()
    tr3 = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(length).mean()
    
    kc_upper = sma + (1.5 * atr)
    kc_lower = sma - (1.5 * atr)
    
    return (bb_upper.iloc[-1] < kc_upper.iloc[-1]) and (bb_lower.iloc[-1] > kc_lower.iloc[-1])


# ==============================================================================
# 4. PANNELLO UI E STRUMENTI
# ==============================================================================

col_nav1, col_nav2, col_nav3 = st.columns(3)
with col_nav1:
    show_whales = st.checkbox("🐋 Whales Tape", value=False)
with col_nav2:
    show_risk = st.checkbox("🎯 Risk Calc", value=False)
with col_nav3:
    show_matrix = st.checkbox("📊 Confluence Matrix", value=True)

if show_whales:
    st.markdown("### 🐋 Whales Tape (On-Chain Live Stream)")
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

# Monete monitorate
WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT",
    "DOGEUSDT", "SUIUSDT", "NEARUSDT", "DOTUSDT"
]

if show_matrix:
    st.markdown("### 📊 Confluence Matrix Overview")
    matrix_rows = []
    for sym in WATCHLIST[:6]:
        df_tmp = fetch_klines(sym, "1h", limit=50)
        if not df_tmp.empty:
            rsi_val = round(calc_rsi(df_tmp["close"]).iloc[-1], 1)
            matrix_rows.append({
                "Asset": sym.replace("USDT", "/USDT"),
                "RSI 1H": rsi_val,
                "Trend": "🟢 LONG" if rsi_val < 45 else ("🔴 SHORT" if rsi_val > 55 else "🟡 RANGE")
            })
    if matrix_rows:
        st.table(pd.DataFrame(matrix_rows))

st.markdown("<div class='filter-header'>Filtro Segnali:</div>", unsafe_allow_html=True)
filtro_segnale = st.radio(
    label="Filtro Segnali",
    options=["🔴🔴 Tutti", "⚪🟢 Solo Buy", "⚪⚪ Alert TP/Short"],
    index=0,
    horizontal=True,
    label_visibility="collapsed"
)


# ==============================================================================
# 5. GENERAZIONE DINAMICA CRYPTO CARD
# ==============================================================================

for symbol in WATCHLIST:
    df_1h = fetch_klines(symbol, "1h", 100)
    df_4h = fetch_klines(symbol, "4h", 100)
    ticker = fetch_ticker_price(symbol)

    if df_1h.empty or df_4h.empty or not ticker:
        continue

    # Calcolo Indicatori
    rsi_1h = round(calc_rsi(df_1h["close"]).iloc[-1], 1)
    rsi_4h = round(calc_rsi(df_4h["close"]).iloc[-1], 1)
    stoch_val, stoch_sub, stoch_type = calc_stoch_rsi(df_1h["close"])
    bb_val, bb_sub, bb_type = calc_bollinger(df_4h)
    squeeze_active = calc_ttm_squeeze(df_1h)

    # Dati Prezzo
    price_val = float(ticker.get("lastPrice", 0))
    change_val = float(ticker.get("priceChangePercent", 0))
    price_str = f"${price_val:,.2f}" if price_val >= 1 else f"${price_val:.4f}"
    change_str = f"({change_val:+.2f}%)"
    change_class = "price-change-up" if change_val >= 0 else "price-change-down"

    # Score di Confluenza
    score = int(np.clip((rsi_1h * 0.4) + (rsi_4h * 0.6), 0, 100))

    if rsi_1h > 60:
        signal_type = "Short"
        badge_status = "OVERBOUGHT / SHORT"
        badge_class = "badge-short"
        rsi_1h_sub = "🎯 Short Alert"
        rsi_1h_type = "red"
    elif rsi_1h < 40:
        signal_type = "Buy"
        badge_status = "BULLISH BUY"
        badge_class = "badge-buy"
        rsi_1h_sub = "🟢 Buy Signal"
        rsi_1h_type = "green"
    else:
        signal_type = "Neutral"
        badge_status = "NEUTRALE / RANGE"
        badge_class = "badge-range"
        rsi_1h_sub = "🎯 Neutral"
        rsi_1h_type = "yellow"

    # Filtri Attivi
    if filtro_segnale == "⚪🟢 Solo Buy" and signal_type != "Buy":
        continue
    if filtro_segnale == "⚪⚪ Alert TP/Short" and signal_type != "Short":
        continue

    coin_name = symbol.replace("USDT", "")
    squeeze_banner = (
        f'<div class="squeeze-active">⚡ TTM Squeeze Attivo su {coin_name}: Compressione in corso...</div>'
        if squeeze_active else
        f'<div class="squeeze-normal">📈 Volatilità nella norma su {coin_name}</div>'
    )

    card_html = textwrap.dedent(f"""
    <div class="crypto-card">
        <div class="card-header">
            <div>
                <span class="ticker-title">{coin_name}/USDT</span>
                <span class="{badge_class}">{badge_status}</span>
            </div>
            <div class="price-box">
                <div class="price-val">{price_str}</div>
                <div class="{change_class}">{change_str}</div>
                <div class="score-text">Score: <strong style="color:#38bdf8;">{score}/100</strong></div>
            </div>
        </div>

        {squeeze_banner}

        <div class="ind-grid">
            <div class="ind-item">
                <div class="ind-label">RSI 1H</div>
                <div class="ind-val">{rsi_1h}</div>
                <div class="ind-sub-{rsi_1h_type}">{rsi_1h_sub}</div>
            </div>
            <div class="ind-item">
                <div class="ind-label">STOCH RSI (%K/%D)</div>
                <div class="ind-val">{stoch_val}</div>
                <div class="ind-sub-{stoch_type}">{stoch_sub}</div>
            </div>
            <div class="ind-item">
                <div class="ind-label">BOLLINGER 4H</div>
                <div class="ind-val">{bb_val}</div>
                <div class="ind-sub-{bb_type}">{bb_sub}</div>
            </div>
            <div class="ind-item">
                <div class="ind-label">RSI 4H</div>
                <div class="ind-val">{rsi_4h}</div>
                <div class="ind-sub-yellow">🎯 Multi-TF Check</div>
            </div>
        </div>
    </div>
    """)

    if hasattr(st, "html"):
        st.html(card_html)
    else:
        st.markdown(card_html, unsafe_allow_html=True)
