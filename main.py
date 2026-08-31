import streamlit as st

# 1. Configurazione della pagina
st.set_page_config(page_title="Crypto Dashboard", layout="centered")

# 2. Iniezione del CSS Personalizzato (Stili per la Card e la Griglia)
st.markdown(
    """
    <style>
        /* Contenitore Principale Card */
        .crypto-card {
            background-color: #0d1117;
            border: 1px solid #21262d;
            border-radius: 12px;
            padding: 20px;
            color: #c9d1d9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 500px;
            margin: auto;
        }

        /* Header: Ticker & Prezzo */
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
        }
        .ticker-name {
            font-size: 22px;
            font-weight: 800;
            color: #ffffff;
        }
        .badge-range {
            background-color: rgba(217, 119, 6, 0.2);
            color: #f59e0b;
            border: 1px solid #f59e0b;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            margin-left: 6px;
            vertical-align: middle;
        }
        .price-container {
            text-align: right;
        }
        .price-val {
            color: #38bdf8;
            font-size: 22px;
            font-weight: 700;
        }
        .price-change {
            color: #f87171;
            font-size: 13px;
            font-weight: 600;
        }
        .score-val {
            color: #8b949e;
            font-size: 12px;
            margin-top: 4px;
        }
        .score-val strong {
            color: #38bdf8;
        }

        /* Banner TTM Squeeze */
        .squeeze-banner {
            background-color: rgba(30, 41, 59, 0.7);
            border: 1px solid #334155;
            color: #f3f4f6;
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            margin-bottom: 16px;
        }

        /* Griglia Indicatori */
        .ind-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        .ind-item {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 10px 12px;
        }
        .ind-label {
            color: #8b949e;
            font-size: 12px;
            font-weight: 600;
        }
        .ind-val {
            color: #f0f6fc;
            font-size: 18px;
            font-weight: 700;
            margin: 4px 0;
        }
        .ind-sub-red {
            color: #f87171;
            font-size: 11px;
            font-weight: 600;
        }
    </style>
""",
    unsafe_allow_html=True,
)

# 3. Variabili Dati (Sostituibili con chiamate API in tempo reale)
ticker = "BTC/USDT"
prezzo = "$78,999.99"
variazione = "(-0.51%)"
score = "48/100"
rsi_1h = "62.9"

# 4. Generazione del blocco HTML assemblato
card_html = f"""
<div class="crypto-card">
    <div class="card-header">
        <div>
            <span class="ticker-name">{ticker}</span>
            <span class="badge-range">NEUTRALE / RANGE</span>
        </div>
        <div class="price-container">
            <div class="price-val">{prezzo}</div>
            <div class="price-change">{variazione}</div>
            <div class="score-val">Score: <strong>{score}</strong></div>
        </div>
    </div>

    <div class="squeeze-banner">
        ⚡ TTM Squeeze Attivo su BTC: Compressione in corso...
    </div>

    <div class="ind-grid">
        <div class="ind-item">
            <div class="ind-label">RSI 1H</div>
            <div class="ind-val">{rsi_1h}</div>
            <div class="ind-sub-red">🎯 Short Alert</div>
        </div>
        <div class="ind-item">
            <div class="ind-label">RSI 4H</div>
            <div class="ind-val">54.2</div>
            <div class="ind-sub-red">🎯 Neutral</div>
        </div>
    </div>
</div>
"""

# 5. Rendering finale su Streamlit
st.markdown(card_html, unsafe_allow_html=True)
