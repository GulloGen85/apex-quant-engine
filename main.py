import os
import requests
import pandas as pd
import numpy as np
from fastapi import FastAPI, BackgroundTasks

app = FastAPI(title="Apex Quant & Liquidity Terminal")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Pair confermati e sempre validi su Binance
WATCHLIST = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'NEARUSDT', 'TAOUSDT', 'ZECUSDT', 'WLDUSDT']

def send_telegram(msg: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_liquidity_data(symbol: str):
    try:
        url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            funding_rate = float(data.get('lastFundingRate', 0)) * 100
            
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
        pass
    return {"funding_rate": 0, "status": "BALANCED LIQUIDITY", "score_impact": 0}

def analyze_crypto(symbol: str):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=100"
        res = requests.get(url, timeout=5)
        if res.status_code != 200:
            return None
            
        data_json = res.json()
        df = pd.DataFrame(data_json).iloc[:, :6]
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
        
        # Bollinger Squeeze
        bb_mid = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['BBW'] = (((bb_mid + bb_std*2) - (bb_mid - bb_std*2)) / bb_mid) * 100

        last_rsi = df['RSI'].iloc[-1]
        last_bbw = df['BBW'].iloc[-1]
        
        score = 50
        if price > df['EMA_200'].iloc[-1]: score += 10
        if last_rsi <= 32: score += 20
        elif last_rsi >= 68: score -= 20
        if last_bbw < 3.5: score += 15
        
        liq_data = get_liquidity_data(symbol)
        score += liq_data['score_impact']
        score = max(0, min(100, score))
        
        action = "🔥 ULTRA BUY" if score >= 75 else ("🚨 DUMP / SHORT" if score <= 25 else "💤 NEUTRAL")
        
        return {
            "symbol": symbol,
            "price": price,
            "score": score,
            "rsi": round(last_rsi, 1),
            "squeeze": bool(last_bbw < 3.5),
            "funding_rate": f"{liq_data['funding_rate']}%",
            "liquidity_status": liq_data['status'],
            "action": action
        }
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

@app.get("/")
def root():
    return {"status": "online", "message": "Apex Quant Engine active"}

@app.get("/api/v1/matrix")
def get_matrix():
    results = []
    for sym in WATCHLIST:
        item = analyze_crypto(sym)
        if item:
            results.append(item)
    return {"status": "ok", "data": results}

@app.post("/api/v1/scan")
def trigger_scan(background_tasks: BackgroundTasks):
    def scan_task():
        for sym in WATCHLIST:
            item = analyze_crypto(sym)
            if item and ("BUY" in item['action'] or "SHORT" in item['action']):
                msg = (
                    f"🎯 *DETECTIVE SIGNAL: {item['symbol']}*\n"
                    f"Action: *{item['action']}* (Score: `{item['score']}/100`)\n"
                    f"Price: `${item['price']}` | RSI: `{item['rsi']}`\n"
                    f"Funding Rate: `{item['funding_rate']}`\n"
                    f"Liquidity Status: *{item['liquidity_status']}*"
                )
                send_telegram(msg)
    background_tasks.add_task(scan_task)
    return {"status": "Scan started"}
