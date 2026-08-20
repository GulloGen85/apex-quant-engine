# --- ASSET CORRETTI CON TICKER UFFICIALI ---
ASSETS = [
    {"name": "BTC/USDT", "binance": "BTCUSDT", "cg_id": "bitcoin"},
    {"name": "ETH/USDT", "binance": "ETHUSDT", "cg_id": "ethereum"},
    {"name": "SOL/USDT", "binance": "SOLUSDT", "cg_id": "solana"},
    {"name": "TAO/USDT", "binance": "TAOUSDT", "cg_id": "bittensor"},
    {"name": "ONDO/USDT", "binance": "ONDOUSDT", "cg_id": "ondo-finance"},
    {"name": "HYPE/USDT", "binance": None, "cg_id": "hyperliquid"},
    {"name": "WLD/USDT", "binance": "WLDUSDT", "cg_id": "worldcoin-wld"},
    {"name": "ZEC/USDT", "binance": "ZECUSDT", "cg_id": "zcash"}
]

@st.cache_data(ttl=15)
def fetch_mobile_matrix():
    matrix = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for item in ASSETS:
        price = 0.0
        rsi = 50.0
        squeeze = False
        
        # 1. Tentativo prioritario con Binance Spot
        if item["binance"]:
            try:
                p_url = f"https://api.binance.com/api/v3/ticker/price?symbol={item['binance']}"
                r = requests.get(p_url, headers=headers, timeout=2)
                if r.status_code == 200:
                    price = float(r.json().get('price', 0))
                
                # Calcolo RSI e Squeeze
                k_url = f"https://api.binance.com/api/v3/klines?symbol={item['binance']}&interval=1h&limit=50"
                k_res = requests.get(k_url, headers=headers, timeout=2).json()
                df_k = pd.DataFrame(k_res).iloc[:, 4].astype(float)
                
                delta = df_k.diff()
                gain = delta.where(delta > 0, 0.0).ewm(alpha=1/14).mean()
                loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1/14).mean()
                rsi = round(float(100 - (100 / (1 + (gain / (loss + 1e-8)).iloc[-1]))), 1)
                
                bb_mid = df_k.rolling(20).mean()
                bb_std = df_k.rolling(20).std()
                bbw = float((((bb_mid + bb_std * 2) - (bb_mid - bb_std * 2)) / bb_mid).iloc[-1] * 100)
                squeeze = bbw < 3.8
            except Exception:
                pass
                
        # 2. Fallback istantaneo su CoinGecko se Binance non risponde
        if price <= 0.0:
            try:
                cg_url = f"https://api.coingecko.com/api/v3/simple/price?ids={item['cg_id']}&vs_currencies=usd"
                cg_res = requests.get(cg_url, headers=headers, timeout=2).json()
                price = float(cg_res[item['cg_id']]['usd'])
                rsi = 52.0
                squeeze = False
            except Exception:
                price = 0.0

        # Formattazione prezzo dinamica
        if price >= 100:
            formatted_price = f"${price:,.2f}"
        elif price >= 1:
            formatted_price = f"${price:.3f}"
        else:
            formatted_price = f"${price:.4f}"

        score = 50
        if rsi < 35: score += 20
        elif rsi > 65: score -= 20
        if squeeze: score += 15
        score = max(5, min(95, score))
        bias = "BULLISH" if score >= 50 else "BEARISH"
        
        if score >= 70 and squeeze:
            action = "🔥 ULTRA LONG"
        elif score >= 60:
            action = "🟢 LONG"
        elif score <= 30 and squeeze:
            action = "🚨 ULTRA SHORT"
        elif score <= 40:
            action = "🔴 SHORT"
        else:
            action = "💤 WAIT"

        matrix.append({
            "Asset": item["name"],
            "Price": formatted_price,
            "raw_price": price if price > 0 else 1.0,
            "Squeeze": "⚡ SI" if squeeze else "NO",
            "Bias": f"🟢 {bias}" if bias == "BULLISH" else f"🔴 {bias}",
            "RSI": rsi,
            "Score": score,
            "Action": action
        })
    return pd.DataFrame(matrix)
