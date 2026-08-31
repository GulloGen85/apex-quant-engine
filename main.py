import textwrap
import pandas as pd
import streamlit as st

# ==============================================================================
# 1. CONFIGURAZIONE PAGINA STREAMLIT
# ==============================================================================
st.set_page_config(
    page_title="Crypto Confluence & Signal Screener",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ==============================================================================
# 2. CSS PERSONALIZZATO (DARK TRADING VIEW THEME)
# ==============================================================================
CUSTOM_CSS = """
<style>
    /* Sfondo generale e font di sistema */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Riconfigurazione checkbox superiori */
    div[data-testid="stCheckbox"] {
        background-color: #161b22;
        padding: 6px 12px;
        border-radius: 8px;
        border: 1px solid #30363d;
    }
    div[data-testid="stCheckbox"] label {
        color: #8b949e !important;
        font-weight: 600;
        font-size: 13px;
    }

    /* Titolo sezione Filtri */
    .filter-header {
        font-size: 18px;
        font-weight: 700;
        color: #ffffff;
        margin-top: 20px;
        margin-bottom: 10px;
    }

    /* Radio buttons orizzontali personalizzati */
    div[data-testid="stRadio"] > label {
        display: none;
    }
    div[data-testid="stRadio"] > div {
        flex-direction: row;
        gap: 15px;
        background-color: #161b22;
        padding: 10px 14px;
        border-radius: 8px;
        border: 1px solid #30363d;
    }

    /* Card Principale Criptovaluta */
    .crypto-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 20px;
        margin-top: 15px;
        margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
    }

    /* Card Header: Ticker & Status */
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 16px;
    }
    .ticker-box {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .ticker-title {
        font-size: 22px;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: 0.5px;
    }
    .badge-range {
        background-color: rgba(217, 119, 6, 0.2);
        color: #f59e0b;
        border: 1px solid #f59e0b;
        font-size: 10px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 4px;
        text-transform: uppercase;
    }
    .badge-buy {
        background-color: rgba(34, 197, 94, 0.2);
        color: #4ade80;
        border: 1px solid #4ade80;
        font-size: 10px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 4px;
        text-transform: uppercase;
    }

    /* Prezzo & Performance */
    .price-box {
        text-align: right;
    }
    .price-val {
        color: #38bdf8;
        font-size: 22px;
        font-weight: 800;
        line-height: 1.1;
    }
    .price-change-down {
        color: #f87171;
        font-size: 13px;
        font-weight: 600;
        margin-top: 2px;
    }
    .price-change-up {
        color: #4ade80;
        font-size: 13px;
        font-weight: 600;
        margin-top: 2px;
    }
    .score-text {
        color: #8b949e;
        font-size: 12px;
        margin-top: 4px;
    }
    .score-val {
        color: #38bdf8;
        font-weight: 700;
    }

    /* Banner TTM Squeeze */
    .squeeze-banner {
        background-color: rgba(30, 41, 59, 0.85);
        border: 1px solid #334155;
        color: #f3f4f6;
        padding: 12px 14px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        margin-bottom: 16px;
    }

    /* Griglia Indicatori */
    .ind-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
    }
    .ind-item {
        background-color: #0d1117;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 12px;
    }
    .ind-label {
        color: #8b949e;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
    }
    .ind-val {
        color: #ffffff;
        font-size: 19px;
        font-weight: 700;
        margin: 4px 0;
    }
    .ind-sub-red {
        color: #f87171;
        font-size: 11px;
        font-weight: 600;
    }
    .ind-sub-green {
        color: #4ade80;
        font-size: 11px;
        font-weight: 600;
    }
    .ind-sub-yellow {
        color: #f59e0b;
        font-size: 11px;
        font-weight: 600;
    }

    /* Box Strumenti Aggiuntivi */
    .tool-container {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 20px;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ==============================================================================
# 3. DATABASE DATI MOCK / SEGNALI CRYPTO
# ==============================================================================
CRYPTO_SIGNALS = [
    {
        "ticker": "BTC/USDT",
        "status": "NEUTRALE / RANGE",
        "status_type": "range",
        "price": "$78,999.99",
        "change": "(-0.51%)",
        "is_positive": False,
        "score": "48/100",
        "squeeze_msg": "⚡ TTM Squeeze Attivo su BTC: Compressione in corso...",
        "signal_category": "Short",
        "indicators": [
            {
                "label": "RSI 1H",
                "val": "62.9",
                "sub": "🎯 Short Alert",
                "sub_type": "red",
            },
            {
                "label": "RSI 4H",
                "val": "54.2",
                "sub": "🎯 Neutral",
                "sub_type": "green",
            },
            {
                "label": "MACD 1H",
                "val": "+14.2",
                "sub": "Bullish Cross",
                "sub_type": "green",
            },
            {
                "label": "BOLLINGER 4H",
                "val": "SQUEEZE",
                "sub": "High Volatility",
                "sub_type": "yellow",
            },
        ],
    },
    {
        "ticker": "ETH/USDT",
        "status": "BULLISH BREAKOUT",
        "status_type": "buy",
        "price": "$3,420.50",
        "change": "(+3.84%)",
        "is_positive": True,
        "score": "82/100",
        "squeeze_msg": "🚀 Expansion Phase: Breakout confermato su ETH!",
        "signal_category": "Buy",
        "indicators": [
            {
                "label": "RSI 1H",
                "val": "42.1",
                "sub": "🟢 Strong Buy",
                "sub_type": "green",
            },
            {
                "label": "RSI 4H",
                "val": "48.9",
                "sub": "🟢 Buy Signal",
                "sub_type": "green",
            },
            {
                "label": "MACD 1H",
                "val": "+45.8",
                "sub": "Strong Uptrend",
                "sub_type": "green",
            },
            {
                "label": "BOLLINGER 4H",
                "val": "UPPER BAND",
                "sub": "Breakout",
                "sub_type": "green",
            },
        ],
    },
    {
        "ticker": "SOL/USDT",
        "status": "OVERBOUGHT / TP",
        "status_type": "range",
        "price": "$184.20",
        "change": "(-1.82%)",
        "is_positive": False,
        "score": "29/100",
        "squeeze_msg": "⚠️ TTM Squeeze Raggiunto: Posibile Inversione di Trend",
        "signal_category": "Short",
        "indicators": [
            {
                "label": "RSI 1H",
                "val": "74.8",
                "sub": "🎯 Take Profit / Short",
                "sub_type": "red",
            },
            {
                "label": "RSI 4H",
                "val": "69.1",
                "sub": "🎯 Overbought",
                "sub_type": "red",
            },
            {
                "label": "MACD 1H",
                "val": "-8.4",
                "sub": "Bearish Divergence",
                "sub_type": "red",
            },
            {
                "label": "BOLLINGER 4H",
                "val": "REJECTION",
                "sub": "Pullback Likely",
                "sub_type": "red",
            },
        ],
    },
]

# ==============================================================================
# 4. FUNZIONE RENDER CARD (CON TEXTWRAP PER EVITARE I BLOCCHI DI CODICE HTML)
# ==============================================================================


def render_crypto_card(data):
    # Determinazione delle classi CSS dinamiche
    badge_class = (
        "badge-buy" if data["status_type"] == "buy" else "badge-range"
    )
    change_class = (
        "price-change-up" if data["is_positive"] else "price-change-down"
    )

    # Costruzione dinamica della griglia indicatori
    ind_html_items = ""
    for ind in data["indicators"]:
        ind_html_items += f"""
        <div class="ind-item">
            <div class="ind-label">{ind['label']}</div>
            <div class="ind-val">{ind['val']}</div>
            <div class="ind-sub-{ind['sub_type']}">{ind['sub']}</div>
        </div>
        """

    # Assemblaggio dell'HTML principale SENZA rientri vuoti (dedent)
    card_html = textwrap.dedent(f"""
    <div class="crypto-card">
        <div class="card-header">
            <div class="ticker-box">
                <span class="ticker-title">{data['ticker']}</span>
                <span class="{badge_class}">{data['status']}</span>
            </div>
            <div class="price-box">
                <div class="price-val">{data['price']}</div>
                <div class="{change_class}">{data['change']}</div>
                <div class="score-text">Score: <span class="score-val">{data['score']}</span></div>
            </div>
        </div>

        <div class="squeeze-banner">
            {data['squeeze_msg']}
        </div>

        <div class="ind-grid">
            {ind_html_items}
        </div>
    </div>
    """)

    # Renderizzazione sicura tramite st.html o st.markdown
    if hasattr(st, "html"):
        st.html(card_html)
    else:
        st.markdown(card_html, unsafe_allow_html=True)


# ==============================================================================
# 5. MODULI ACCESSORI (ARKHAM WHALES, RISK CALC, CONFLUENCE MATRIX)
# ==============================================================================


def render_whales_tape():
    st.markdown("### 🐋 Whales Tape (Arkham Intelligence)")
    df_whales = pd.DataFrame(
        [
            {
                "Time": "00:01:14",
                "Entity": "Jump Trading",
                "Asset": "BTC",
                "Amount": "450 BTC ($35.5M)",
                "Type": "Exchange Deposit (Binance)",
            },
            {
                "Time": "23:58:02",
                "Entity": "Cumberland",
                "Asset": "USDT",
                "Amount": "12,000,000 USDT",
                "Type": "Minted & Transferred",
            },
            {
                "Time": "23:45:21",
                "Entity": "Unknown Whale",
                "Asset": "ETH",
                "Amount": "8,500 ETH ($29.0M)",
                "Type": "Withdrawal (Coinbase)",
            },
        ]
    )
    st.dataframe(df_whales, use_container_width=True)


def render_risk_calculator():
    st.markdown("### 🎯 Risk & Position Size Calculator")
    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1:
        capital = st.number_input(
            "Capitale Totale ($)", value=10000, step=500
        )
    with col_r2:
        risk_pct = st.slider("Rischio % per Trade", 0.5, 5.0, 1.0, 0.5)
    with col_r3:
        stop_loss_pct = st.number_input(
            "Stop Loss %", value=2.5, step=0.1
        )

    risk_amount = capital * (risk_pct / 100)
    position_size = (
        risk_amount / (stop_loss_pct / 100) if stop_loss_pct > 0 else 0
    )

    st.info(
        f"💡 **Rischio Max per Trade:** `${risk_amount:.2f}` | **Size Posizione Consigliata:** `${position_size:.2f}`"
    )


def render_confluence_matrix():
    st.markdown("### 📊 Confluence Matrix Overview")
    matrix_data = {
        "Asset": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        "15M Trend": ["🔴 Short", "🟢 Long", "🔴 Short"],
        "1H Trend": ["🟡 Range", "🟢 Long", "🔴 Short"],
        "4H Trend": ["🟢 Long", "🟢 Long", "🟡 Range"],
        "1D Trend": ["🟢 Long", "🟢 Long", "🟢 Long"],
        "Confluence Score": ["48%", "82%", "29%"],
    }
    st.table(pd.DataFrame(matrix_data))


# ==============================================================================
# 6. MAIN APP BARRA DI NAVIGAZIONE E FILTRI INTERATTIVI
# ==============================================================================

# Toolbar Superiore Checkboxes
col_nav1, col_nav2, col_nav3 = st.columns(3)
with col_nav1:
    show_whales = st.checkbox("🐋 Whales Tape (Arkham)", value=False)
with col_nav2:
    show_risk = st.checkbox("🎯 Risk Calc", value=False)
with col_nav3:
    show_matrix = st.checkbox("📊 Confluence Matrix", value=True)

# Visualizzazione dei Moduli Selezionati
if show_whales:
    with st.container():
        render_whales_tape()

if show_risk:
    with st.container():
        render_risk_calculator()

if show_matrix:
    with st.container():
        render_confluence_matrix()

# Sezione Filtri Segnali
st.markdown("<div class='filter-header'>Filtro Segnali:</div>", unsafe_allow_html=True)

filtro_segnale = st.radio(
    label="Filtro Segnali",
    options=["🔴🔴 Tutti", "⚪🟢 Solo Buy", "⚪⚪ Alert TP/Short"],
    index=0,
    horizontal=True,
    label_visibility="collapsed",
)

# Rendering Sequenziale delle Card filtrate
for crypto in CRYPTO_SIGNALS:
    if filtro_segnale == "🔴🔴 Tutti":
        render_crypto_card(crypto)
    elif filtro_segnale == "⚪🟢 Solo Buy" and crypto["signal_category"] == "Buy":
        render_crypto_card(crypto)
    elif (
        filtro_segnale == "⚪⚪ Alert TP/Short"
        and crypto["signal_category"] == "Short"
    ):
        render_crypto_card(crypto)
