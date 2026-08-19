import os
import requests
import pandas as pd
import numpy as np
from fastapi import FastAPI, BackgroundTasks

app = FastAPI(title="Apex Quant, Arkham & Liquidity Terminal")

# CONFIGURAZIONI & KEYS
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
ARKHAM_API_KEY = os.getenv("ARKHAM_API_KEY", "YOUR_ARKHAM_KEY")

WATCHLIST = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'NEARUSDT', 'TAOUSDT', 'ZECUSDT', 'HYPEUSDT', 'WLDUSDT']

# ---------------------------------------------------------
# TELEGRAM NOTIFICATIONS
# ---------------------------------------------------------
def send_telegram(msg: str):
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN":
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")

# ---------------------------------------------------------
# LIQUIDITY & FUNDING ENGINE
# ---------------------------------------------------------
def get_liquidity_data(symbol: str):
    try:
        url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}"
        res = requests.get(url, timeout=4).json()
        funding_rate = float(res.get('lastFundingRate', 0)) * 100
        
        if funding_rate > 0.05:
            funding_status = "⚠️ LONG OVERCROWDED (Long Squeeze Risk)"
            liq_bias = -15
        elif funding_rate < -0.03:
            funding_status = "🔥 SHORT OVERCROWDED (Short Squeeze Risk)"
            liq_bias = 20
        else:
            funding_status = "BALANCED LIQUIDITY"
            liq_bias = 0
            
        return {"funding_rate": round(funding_rate, 4), "status": funding_status, "score_impact": liq_bias}
    except Exception:
        return {"funding_rate": 0, "status": "N/A", "score_impact": 0}

# ---------------------------------------------------------
# ARKHAM ON-CHAIN INTELLIGENCE
# ---------------------------------------------------------
def get_arkham_signals(symbol_base: str):
    if not ARKHAM_API_KEY or ARKHAM_API_KEY == "YOUR_ARKHAM_KEY":
        return {"whale_flow": "NEUTRAL", "score_impact": 0}
    
    target_base = "HYPERLIQUID" if symbol_base == "HYPE" else symbol_base
    headers = {"API-Key": ARKHAM_API_KEY}
    url = f"https://api.arkhamintelligence.com/transfers?base={target_base}&limit=10&sort=value_usd"
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            transfers = res.json().get('transfers', [])
            total_inflow = 0
            
            for t in transfers:
                val = float(t.get('historicalValueUsd', 0))
                if t.get('toAddress', {}).get('isExchange', False):
                    total_inflow -= val
                elif t.get('fromAddress', {}).get('isExchange', False):
                    total_inflow += val
            
            if total_inflow > 500_000:
                return {"whale_flow": "🐋 WHALE ACCUMULATION", "score_impact": 25}
            elif total_inflow < -500_000:
                return {"whale_flow": "🚨 EXCHANGE DUMP RISK", "score_impact": -25}
    except Exception:
        pass
        
    return {"whale_flow": "FLOW STABILE", "score_impact": 0}

# ---------------------------------------------------------
# MAIN ANALYZER ENGINE
# ---------------------------------------------------------
def analyze_crypto(symbol: str):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=100"
    res = requests.get(url, timeout=5).json()
    
    df = pd.DataFrame(res).iloc[:, :6]
    df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
        
    price = df['close'].iloc[-1]
    df['EMA_200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    rs = gain.ewm(alpha=1/14).mean() / (loss.ewm(alpha=1/14).mean() + 1e-8)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bandwidth Squeeze
    bb_mid = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['BBW'] = (((bb_mid + bb_std*2) - (bb_mid - bb_std*2)) / bb_mid) * 100

    last_rsi = df['RSI'].iloc[-1]
    last_bbw = df['BBW'].iloc[-1]
    
    # Base Quant Score
    score = 50
    if price > df['EMA_200'].iloc[-1]: score += 10
    if last_rsi <= 32: score += 20
    elif last_rsi >= 68: score -= 20
    if last_bbw < 3.5: score += 15
    
    # Liquidity & Arkham Modifiers
    base_sym = symbol.replace("USDT", "")
    liq_data = get_liquidity_data(symbol)
    arkham_data = get_arkham_signals(base_sym)
    
    score += liq_data['score_impact'] + arkham_data['score_impact']
    score = max(0, min(100, score))
    
    action = "🔥 ULTRA BUY" if score >= 75 else ("🚨 DUMP / SHORT" if score <= 25 else "💤 NEUTRAL")
    
    return {
        "symbol": symbol,
        "price": price,
        "score": score,
        "rsi": round(last_rsi, 1),
        "squeeze": last_bbw < 3.5,
        "funding_rate": f"{liq_data['funding_rate']}%",
        "liquidity_status": liq_data['status'],
        "whale_flow": arkham_data['whale_flow'],
        "action": action
    }

# ---------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------
@app.get("/api/v1/matrix")
def get_matrix():
    data = [analyze_crypto(sym) for sym in WATCHLIST]
    return {"status": "ok", "data": data}

@app.post("/api/v1/scan")
def trigger_scan(background_tasks: BackgroundTasks):
    def scan_task():
        for sym in WATCHLIST:
            item = analyze_crypto(sym)
            if "BUY" in item['action'] or "SHORT" in item['action']:
                msg = (
                    f"🎯 *DETECTIVE SIGNAL: {item['symbol']}*\n"
                    f"Action: *{item['action']}* (Score: `{item['score']}/100`)\n"
                    f"Price: `${item['price']}` | RSI: `{item['rsi']}`\n"
                    f"Funding Rate: `{item['funding_rate']}`\n"
                    f"Liquidity Status: *{item['liquidity_status']}*\n"
                    f"Arkham Whale: *{item['whale_flow']}*"
                )
                send_telegram(msg)
    background_tasks.add_task(scan_task)
    return {"status": "Scan started"}
