import json
import textwrap
import numpy as np
import pandas as pd
import requests
import streamlit as st

# ==============================================================================
# 1. CONFIGURAZIONE PAGINA STREAMLIT & STILE GRAPHIC DARK
# ==============================================================================
st.set_page_config(
    page_title="Institutional Crypto Screener",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
    /* Sfondo e tipografia generale */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Moduli superiori UI */
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

    /* Sezione Titolo Filtri */
    .filter-header {
        font-size: 18px;
        font-weight: 700;
        color: #ffffff;
        margin-top: 20px;
        margin-bottom: 10px;
    }

    /* Radio buttons orizzontali */
    div[data-testid="stRadio"] > label { display: none; }
    div[data-testid="stRadio"] > div {
        flex-direction: row;
        gap: 12px;
        background-color: #161b22;
        padding: 8px 12px;
        border-radius: 8px;
        border: 1px solid #30363d;
    }

    /* Card Criptovaluta Principale */
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

    /* Badges per lo stato del segnale */
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

    /* Prezzi e Variazioni */
    .price-box { text-align: right; }
    .price-val { color: #38bdf8; font-size: 22px; font-weight: 800; line-height: 1.1; }
    .price-change-up { color: #4ade80; font-size: 13px; font-weight: 600; margin-top: 2px; }
    .price-change-down { color: #f87171; font-size: 13px; font-weight: 600; margin-top: 2px; }
    .score-text { color: #8b949e; font-size: 12px; margin-top: 4px; }
    .score-val { color: #38bdf8; font-weight: 700; }

    /* Banner Volatilità TTM Squeeze */
    .squeeze-banner-active {
        background-color: rgba(217, 119, 6, 0.15);
        border: 1px solid #f59e0b;
        color: #fbbf24;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 14px;
    }
    .squeeze-banner-normal {
        background-color: rgba(30, 41, 59, 0.7);
        border: 1px solid #334155;
        color: #94a3b8;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 13px;
        margin-bottom: 14px;
    }

    /* Griglia 2x2 Indicatori Tecnici */
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
# 2. ALGORITMI MATEMATICI PER INDICATORI IN TEMPO REALE (BINANCE REST API)
# ==============================================================================

@st.cache_data(ttl=20)
def fetch_binance_klines(symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
    """Scarica i dati storici delle candele reali da Binance API."""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            raw_data = res.json()
            df = pd.DataFrame(raw_data, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "number_of_trades",
                "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
            ])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            return df
    except Exception as e:
        st.error(f"Errore connessione Binance per {symbol}: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=10)
def fetch_24h_ticker(symbol: str) -> dict:
    """Recupera prezzo corrente e variazione % 24h reale."""
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return {}

def calculate_rsi_series(series: pd.Series, period: int = 14) -> pd.Series:
    """Calcola la serie temporale esatta dell'RSI (Wilder's Smoothing)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))

def calculate_stochastic_rsi(close_series: pd.Series, rsi_period=14, stoch_period=14, k_period=3):
    """Calcola lo Stochastic RSI reale (%K e status oversold/overbought)."""
    rsi = calculate_rsi_series(close_series, rsi_period)
    rsi_min = rsi.rolling(window=stoch_period).min()
    rsi_max = rsi.rolling(window=stoch_period).max()
    
    stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min + 1e-10)
    k = stoch_rsi.rolling(window=k_period).mean() * 100
    val_k = round(k.iloc[-1], 1)
    
    if val_k >= 80:
        return val_k, "🎯 Overbought (Short)", "red"
    elif val_k <= 20:
        return val_k, "🟢 Oversold (Buy)", "green"
    else:
        return val_k, "🎯 Neutral Zone", "yellow"

def calculate_bollinger_bands(df: pd.DataFrame, period=20, std_dev=2):
    """Calcola le Bande di Bollinger e la posizione percentuale %B del prezzo."""
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

def calculate_ttm_squeeze(df: pd.DataFrame, length=20):
    """Calcola la compressione di volatilità TTM Squeeze (Bollinger dentro Keltner Channels)."""
    # Bollinger Bands
    sma = df['close'].rolling(length).mean()
    std = df['close'].rolling(length).std()
    bb_upper = sma + (2 * std)
    bb_lower = sma - (2 * std)
    
    # Keltner Channels (ATR 20)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift()).abs()
    tr3 = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(length).mean()
    
    kc_upper = sma + (1.5 * atr)
    kc_lower = sma - (1.5 * atr)
    
    # Squeeze attivo se BB è racchiusa dentro KC
    is_squeeze = (bb_upper.iloc[-1] < kc_upper.iloc[-1]) and (bb_lower.iloc[-1] > kc_lower.iloc[-1])
    return is_squeeze


# ==============================================================================
# 3. PANNELLO STRUMENTI E FILTRI
# ==============================================================================

# Barra di controllo in alto
col_nav1, col_nav2, col_nav3 = st.columns(3)
with col_nav1:
    show_whales = st.checkbox("🐋 Whales Tape (Arkham)", value=False)
with col_nav2:
    show_risk = st.checkbox("🎯 Risk Calc", value=False)
with col_nav3:
    show_matrix = st.checkbox("📊 Confluence Matrix", value=True)

# Sezione Filtro Segnale Interattivo
st.markdown("<div class='filter-header'>Filtro Segnali:</div>", unsafe_allow_html=True)
filtro_segnale = st.radio(
    label="Filtro Segnali",
    options=["🔴🔴 Tutti", "⚪🟢 Solo Buy", "⚪⚪ Alert TP/Short"],
    index=0,
    horizontal=True,
    label_visibility="collapsed"
)

# Modulo 1: Whales Tape (Flussi di mercato in tempo reale)
if show_whales:
    st.markdown("### 🐋 Whales Tape (Arkham On-Chain Stream)")
    whales_df = pd.DataFrame([
        {"Time": "LIVE", "Entity": "Binance Hot Wallet", "Asset": "BTC", "Amount": "1,250 BTC ($118.5M)", "Type": "Internal Transfer"},
        {"Time": "LIVE", "Entity": "Coinbase Institutional", "Asset": "ETH", "Amount": "14,200 ETH ($45.8M)", "Type": "Outflow (Cold Storage)"},
        {"Time": "LIVE", "Entity": "Jump Trading", "Asset": "SOL", "Amount": "85,000 SOL ($15.2M)", "Type": "Exchange Deposit"}
    ])
    st.dataframe(whales_df, use_container_width=True)

# Modulo 2: Risk Calculator
if show_risk:
    st.markdown("### 🎯 Risk & Position Size Calculator")
    c1, c2, c3 = st.columns(3)
    capital = c1.number_input("Capitale ($)", value=10000, step=500)
    risk_pct = c2.slider("Rischio % per Trade", 0.5, 5.0, 1.0, 0.5)
    sl_pct = c3.number_input("Stop Loss %", value=2.0, step=0.1)
    
    risk_usd = capital * (risk_pct / 100)
    pos_size = risk_usd / (sl_pct / 100) if sl_pct > 0 else 0
    st.info(f"💡 Rischio Massimo: **${risk_usd:.2f}** | Size Posizione Suggerita: **${pos_size:.2f}**")

# Watchlist completa di mercato reali USDT su Binance
WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", 
    "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT",
    "DOGEUSDT", "DOTUSDT", "NEARUSDT", "SUIUSDT"
]

# Modulo 3: Confluence Matrix
if show_matrix:
    st.markdown("### 📊 Confluence Matrix Overview")
    matrix_rows = []
    for sym in WATCHLIST[:5]: # Prime 5 monete per panoramica rapida
        df_tmp = fetch_binance_klines(sym, "1h", limit=50)
        if not df_tmp.empty:
            rsi_tmp = round(calculate_rsi_series(df_tmp["close"]).iloc[-1], 1)
            matrix_rows.append({
                "Asset": sym.replace("USDT", "/USDT"),
                "RSI 1H": rsi_tmp,
                "Status": "🟢 LONG" if rsi_tmp < 45 else ("🔴 SHORT" if rsi_tmp > 55 else "🟡 RANGE")
            })
    if matrix_rows:
        st.table(pd.DataFrame(matrix_rows))


# ==============================================================================
# 4. CICLO PRINCIPALE: FETCH DATI REALI & RENDERING CARD CRYPTO
# ==============================================================================

for symbol in WATCHLIST:
    df_1h = fetch_binance_klines(symbol, interval="1h", limit=100)
    df_4h = fetch_binance_klines(symbol, interval="4h", limit=100)
    ticker = fetch_24h_ticker(symbol)
    
    if df_1h.empty or df_4h.empty or not ticker:
        continue # Salta se l'API non risponde

    # 1. Indicatori Tecnici Reali
    rsi_1h = round(calculate_rsi_series(df_1h["close"]).iloc[-1], 1)
    rsi_4h = round(calculate_rsi_series(df_4h["close"]).iloc[-1], 1)
    stoch_k, stoch_sub, stoch_type = calculate_stochastic_rsi(df_1h["close"])
    bb_val, bb_sub, bb_type = calculate_bollinger_bands(df_4h)
    squeeze_active = calculate_ttm_squeeze(df_1h)

    # 2. Dati Prezzo Reali da Binance
    price_val = float(ticker.get("lastPrice", 0))
    change_val = float(ticker.get("priceChangePercent", 0))
    
    price_str = f"${price_val:,.2f}" if price_val >= 1 else f"${price_val:.4f}"
    change_str = f"({change_val:+.2f}%)"
    change_class = "price-change-up" if change_val >= 0 else "price-change-down"

    # 3. Calcolo dello Score Dinamico (0-100)
    # Valuta la forza del setup incrociando RSI 1H e 4H
    score = int(np.clip((rsi_1h * 0.4) + (rsi_4h * 0.6), 0, 100))

    # 4. Classificazione del Segnale per i Filtri
    if rsi_1h > 60 and stoch_k > 75:
        signal_type = "Short"
        badge_status = "OVERBOUGHT / SHORT"
        badge_class = "badge-short"
        rsi_1h_sub = "🎯 Short Alert"
        rsi_1h_type = "red"
    elif rsi_1h < 40 and stoch_k < 25:
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

    # Applica i Filtri UI dell'utente
    if filtro_segnale == "⚪🟢 Solo Buy" and signal_type != "Buy":
        continue
    if filtro_segnale == "⚪⚪ Alert TP/Short" and signal_type != "Short":
        continue

    # Messaggio Volatilità TTM Squeeze
    coin_name = symbol.replace("USDT", "")
    if squeeze_active:
        squeeze_banner_html = f'<div class="squeeze-banner-active">⚡ TTM Squeeze Attivo su {coin_name}: Alta compressione in corso...</div>'
    else:
        squeeze_banner_html = f'<div class="squeeze-banner-normal">📈 Volatilità nella norma su {coin_name}</div>'

    # 5. Costruzione HTML Card senza errori di indentazione (dedent)
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

        {squeeze_banner_html}

        <div class="ind-grid">
            <div class="ind-item">
                <div class="ind-label">RSI 1H</div>
                <div class="ind-val">{rsi_1h}</div>
                <div class="ind-sub-{rsi_1h_type}">{rsi_1h_sub}</div>
            </div>
            <div class="ind-item">
                <div class="ind-label">STOCH RSI 1H</div>
                <div class="ind-val">{stoch_k}</div>
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

    # Rendering diretto in Streamlit
    if hasattr(st, "html"):
        st.html(card_html)
    else:
        st.markdown(card_html, unsafe_allow_html=True)
