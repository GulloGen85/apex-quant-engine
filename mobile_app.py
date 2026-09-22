from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import math

import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="Crypto Screener V2",
    page_icon="⚡",
    layout="wide",
)

PAIRS = [
    "HYPEUSDT", "BTCUSDC", "KASUSDT", "NEARUSDC", "ETHUSDC",
    "FETUSDC", "XRPUSDC", "SOLUSDC", "BNBUSDC", "BCHUSDC",
    "LINKUSDC", "AAVEUSDC", "ZECUSDC", "RENDERUSDC", "TAOUSDC",
    "AKTUSDT", "ONDOUSDC", "SUIUSDC", "WLDUSDC", "INJUSDC",
    "ENAUSDC",
]

BASE_URL = {
    "spot": "https://data-api.binance.vision/api/v3",
    "perp": "https://fapi.binance.com/fapi/v1",
}

TIMEFRAMES = ("15m", "1h", "4h", "1d")


def api_get(market, endpoint, **params):
    response = requests.get(
        BASE_URL[market] + endpoint,
        params=params,
        timeout=8,
        headers={"User-Agent": "CryptoScreenerV2/1.0"},
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=20, show_spinner=False)
def fetch_pair(symbol, market):
    frames = {}

    for timeframe in TIMEFRAMES:
        raw = api_get(
            market,
            "/klines",
            symbol=symbol,
            interval=timeframe,
            limit=210,
        )

        frame = pd.DataFrame(
            raw,
            columns=[
                "open_time", "open", "high", "low", "close",
                "volume", "close_time", "quote_volume", "trades",
                "taker_buy", "taker_quote", "ignore",
            ],
        )

        for column in (
            "open", "high", "low", "close", "volume", "taker_buy"
        ):
            frame[column] = pd.to_numeric(
                frame[column],
                errors="coerce",
            )

        frame["close_time"] = pd.to_numeric(
            frame["close_time"],
            errors="coerce",
        )

        frames[timeframe] = frame.dropna(
            subset=[
                "open", "high", "low", "close",
                "volume", "taker_buy", "close_time",
            ]
        )

    ticker = api_get(market, "/ticker/24hr", symbol=symbol)

    return (
        frames,
        {
            "price": float(ticker["lastPrice"]),
            "change": float(ticker["priceChangePercent"]),
        },
        datetime.now(timezone.utc),
    )


def rma(series, period):
    return series.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()


def calculate_supertrend(high, low, close, period=10, factor=3):
    true_range = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = rma(true_range, period)
    midpoint = (high + low) / 2
    upper = midpoint + factor * atr
    lower = midpoint - factor * atr

    final_upper = upper.copy()
    final_lower = lower.copy()

    bullish = pd.Series(False, index=close.index)
    line = pd.Series(float("nan"), index=close.index)

    for i in range(period, len(close)):
        previous = i - 1

        if i > period:
            if not (
                upper.iloc[i] < final_upper.iloc[previous]
                or close.iloc[previous] > final_upper.iloc[previous]
            ):
                final_upper.iloc[i] = final_upper.iloc[previous]

            if not (
                lower.iloc[i] > final_lower.iloc[previous]
                or close.iloc[previous] < final_lower.iloc[previous]
            ):
                final_lower.iloc[i] = final_lower.iloc[previous]

            if bullish.iloc[previous]:
                bullish.iloc[i] = (
                    close.iloc[i] >= final_lower.iloc[previous]
                )
            else:
                bullish.iloc[i] = (
                    close.iloc[i] > final_upper.iloc[previous]
                )
        else:
            bullish.iloc[i] = (
                close.iloc[i] >= midpoint.iloc[i]
            )

        line.iloc[i] = (
            final_lower.iloc[i]
            if bullish.iloc[i]
            else final_upper.iloc[i]
        )

    return line, bullish, atr


def calculate_indicators(frame):
    close = frame["close"].astype(float)
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    volume = frame["volume"].astype(float)

    change = close.diff()
    gain = rma(change.clip(lower=0), 14)
    loss = rma((-change).clip(lower=0), 14)

    rsi = 100 * gain / (gain + loss)
    rsi = rsi.where(loss.ne(0), 100)
    rsi = rsi.where(gain.ne(0), 0)
    rsi = rsi.where(gain.ne(0) | loss.ne(0), 50)

    rsi_low = rsi.rolling(14).min()
    rsi_high = rsi.rolling(14).max()

    stoch_rsi = (
        100
        * (rsi - rsi_low)
        / (rsi_high - rsi_low).replace(0, float("nan"))
    )

    stoch_k = stoch_rsi.rolling(3).mean()
    stoch_d = stoch_k.rolling(3).mean()

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_histogram = macd - macd_signal

    ema7 = close.ewm(span=7, adjust=False).mean()
    ema25 = close.ewm(span=25, adjust=False).mean()
    ema99 = close.ewm(span=99, adjust=False).mean()

    bb_middle = close.rolling(20).mean()
    bb_deviation = close.rolling(20).std(ddof=0)

    supertrend, bullish, atr = calculate_supertrend(
        high, low, close
    )

    upward_move = high.diff()
    downward_move = -low.diff()

    plus_dm = upward_move.where(
        (upward_move > downward_move) & (upward_move > 0),
        0,
    )

    minus_dm = downward_move.where(
        (downward_move > upward_move) & (downward_move > 0),
        0,
    )

    atr_nonzero = atr.replace(0, float("nan"))

    plus_di = 100 * rma(plus_dm, 14) / atr_nonzero
    minus_di = 100 * rma(minus_dm, 14) / atr_nonzero

    dx = (
        100
        * (plus_di - minus_di).abs()
        / (plus_di + minus_di).replace(0, float("nan"))
    )

    adx = rma(dx, 14)

    previous_volume_average = volume.shift(1).rolling(20).mean()
    taker_buy = frame["taker_buy"].astype(float)

    return {
        "close": close,
        "rsi": rsi,
        "k": stoch_k,
        "d": stoch_d,
        "hist": macd_histogram,
        "ema7": ema7,
        "ema25": ema25,
        "ema99": ema99,
        "bb_upper": bb_middle + 2 * bb_deviation,
        "bb_lower": bb_middle - 2 * bb_deviation,
        "supertrend": supertrend,
        "bull": bullish,
        "atr": atr,
        "adx": adx,
        "rvol": (
            volume
            / previous_volume_average.replace(0, float("nan"))
        ),
        "taker_delta": (
            100
            * (2 * taker_buy - volume)
            / volume.replace(0, float("nan"))
        ),
    }


def finite_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def snapshot(indicators, position):
    return {
        name: finite_number(series.iloc[position])
        for name, series in indicators.items()
    }


def classify(data, btc_bullish):
    daily = data["1d"]
    four_hour = data["4h"]
    one_hour = data["1h"]
    entry = data["15m"]

    if any(
        values["close"] is None or values["ema25"] is None
        for values in data.values()
    ):
        return (
            "DATI INSUFFICIENTI",
            0,
            "Indicatori non disponibili",
        )

    conditions = [
        daily["close"] > daily["ema25"],
        four_hour["close"] > four_hour["ema25"],
        four_hour["bull"] == 1,
        one_hour["ema7"] > one_hour["ema25"],
        one_hour["hist"] is not None
        and one_hour["hist"] > 0,
        entry["k"] is not None
        and entry["d"] is not None
        and entry["k"] > entry["d"],
        entry["close"] > entry["ema7"],
        entry["taker_delta"] is not None
        and entry["taker_delta"] > 0,
        entry["rvol"] is not None
        and entry["rvol"] >= 1.2,
        btc_bullish,
    ]

    score = sum(conditions)

    if (
        four_hour["close"] < four_hour["ema25"]
        and one_hour["close"] < one_hour["ema25"]
        and entry["close"] < entry["ema7"]
    ):
        return (
            "PRESSIONE RIBASSISTA",
            score,
            "Struttura 4H e 1H debole; nessun ingresso long",
        )

    if (
        one_hour["rsi"] is not None
        and one_hour["rsi"] < 30
        and score < 6
    ):
        return (
            "IPERVENDUTO · ATTENDI",
            score,
            "RSI basso da solo non conferma un rimbalzo",
        )

    trigger = (
        score >= 7
        and entry["close"] > entry["ema7"]
        and entry["k"] is not None
        and entry["d"] is not None
        and entry["k"] > entry["d"]
        and one_hour["hist"] is not None
        and one_hour["hist"] > 0
    )

    if trigger:
        return (
            "TRIGGER LONG",
            score,
            "Conferme presenti; valuta prezzo, stop e liquidità",
        )

    if score >= 6:
        return (
            "SETUP LONG · ATTENDI",
            score,
            "Confluenza parziale; attendi conferma 15m",
        )

    return (
        "NEUTRALE",
        score,
        "Nessun trigger sufficientemente confermato",
    )


def format_price(value):
    if value is None:
        return "—"
    if abs(value) >= 1000:
        return f"{value:,.2f}"
    if abs(value) >= 1:
        return f"{value:.3f}"
    return f"{value:.5f}"


st.title("⚡ Crypto Screener V2")

st.caption(
    "Dati pubblici Binance · segnali descrittivi, non ordini"
)

with st.sidebar:
    st.header("Impostazioni")

    raw_watchlist = st.text_area(
        "Watchlist: simboli separati da virgole",
        ", ".join(PAIRS),
        height=160,
    )

    watchlist = list(
        dict.fromkeys(
            symbol.strip().upper()
            for symbol in raw_watchlist.split(",")
            if symbol.strip()
        )
    )[:40]

    default_market = st.selectbox(
        "Mercato predefinito",
        ["spot", "perp"],
    )

    selected_markets = {
        symbol: st.selectbox(
            symbol,
            ["spot", "perp"],
            index=0 if default_market == "spot" else 1,
            key=f"market_{symbol}",
        )
        for symbol in watchlist
    }

    closed_candles = st.toggle(
        "Segnali su candele chiuse",
        value=True,
    )

    refresh_seconds = st.selectbox(
        "Aggiornamento automatico (secondi)",
        [20, 30, 60],
        index=1,
    )

    st.caption(
        "Il mercato scelto si applica a tutte le candele "
        "e al ticker della coppia."
    )


@st.fragment(run_every=f"{refresh_seconds}s")
def dashboard():
    # Prova le coppie direttamente. Un errore su exchangeInfo
    # non deve bloccare l'intera dashboard.
    selected = [
        (symbol, selected_markets[symbol])
        for symbol in watchlist
    ]

    packs = {}
    errors = {}

    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {
            executor.submit(fetch_pair, symbol, market): (
                symbol,
                market,
            )
            for symbol, market in selected
        }

        for future in as_completed(futures):
            symbol, market = futures[future]

            try:
                packs[symbol] = (
                    market,
                    *future.result(),
                )

            except requests.HTTPError as error:
                status = (
                    error.response.status_code
                    if error.response is not None
                    else "?"
                )
                errors[symbol] = f"HTTP {status} ({market})"

            except (
                requests.RequestException,
                ValueError,
                KeyError,
                IndexError,
            ) as error:
                errors[symbol] = (
                    f"{type(error).__name__}: "
                    f"{str(error)[:80]}"
                )

    if errors:
        st.warning(
            "Dati non disponibili: "
            + "; ".join(
                f"{symbol}: {error}"
                for symbol, error in errors.items()
            )
        )

        if all(
            "HTTP 451" in error or "HTTP 403" in error
            for error in errors.values()
        ):
            st.error(
                "Il server che ospita l’app non riesce ad "
                "accedere alle API Binance. Prova a eseguirla "
                "in locale o usa un provider dati accessibile "
                "dal server."
            )

    if not packs:
        st.error(
            "Nessuna coppia caricata. Controlla gli errori "
            "mostrati sopra."
        )
        return

    position = -2 if closed_candles else -1

    btc_bullish = False

    if "BTCUSDC" in packs:
        _, btc_frames, _, _ = packs["BTCUSDC"]

        btc_data = snapshot(
            calculate_indicators(btc_frames["4h"]),
            position,
        )

        btc_bullish = bool(
            btc_data["close"] is not None
            and btc_data["ema25"] is not None
            and btc_data["close"] > btc_data["ema25"]
        )

    rows = []
    details = {}

    for symbol in watchlist:
        if symbol not in packs:
            continue

        market, frames, ticker, fetched_at = packs[symbol]

        if any(
            len(frame) < 100
            for frame in frames.values()
        ):
            continue

        try:
            data = {
                timeframe: snapshot(
                    calculate_indicators(frame),
                    position,
                )
                for timeframe, frame in frames.items()
            }

            state, score, note = classify(
                data,
                btc_bullish,
            )

            candle_time = pd.to_datetime(
                frames["15m"]["close_time"].iloc[position],
                unit="ms",
                utc=True,
            )

            rows.append(
                {
                    "Coppia": symbol,
                    "Mercato": market,
                    "Prezzo ticker": ticker["price"],
                    "24h %": ticker["change"],
                    "Stato": state,
                    "Score /10": score,
                    "RSI 1H": data["1h"]["rsi"],
                    "ADX 4H": data["4h"]["adx"],
                    "Delta taker 1H %":
                        data["1h"]["taker_delta"],
                    "RVOL 1H": data["1h"]["rvol"],
                }
            )

            details[symbol] = (
                data,
                note,
                candle_time,
                market,
                fetched_at,
            )

        except (ValueError, KeyError, IndexError):
            errors[symbol] = "indicatori incompleti"

    st.caption(
        "Ultima lettura: "
        + datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        + " · "
        + (
            "candele chiuse"
            if closed_candles
            else "candele in formazione: segnali provvisori"
        )
    )

    if not rows:
        st.error(
            "Storico insufficiente per calcolare gli indicatori."
        )
        return

    table = pd.DataFrame(rows).sort_values(
        ["Score /10", "24h %"],
        ascending=False,
    )

    st.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "Lo score conta 10 condizioni tecniche: "
        "non è una probabilità di profitto. "
        "Il filtro BTC richiede BTCUSDC nella watchlist."
    )

    chosen = st.selectbox(
        "Analisi coppia",
        table["Coppia"].tolist(),
    )

    data, note, candle_time, market, fetched_at = (
        details[chosen]
    )

    state = table.loc[
        table["Coppia"] == chosen,
        "Stato",
    ].iloc[0]

    st.subheader(f"{chosen} · {market} · {state}")
    st.write(note)

    st.caption(
        f"Candela 15m usata: {candle_time} · "
        f"dati scaricati: "
        f"{fetched_at.strftime('%H:%M:%S UTC')}"
    )

    metrics = []

    for timeframe in TIMEFRAMES:
        values = data[timeframe]

        metrics.append(
            {
                "TF": timeframe,
                "Chiusura": format_price(
                    values["close"]
                ),
                "RSI14": format_price(
                    values["rsi"]
                ),
                "Stoch K/D":
                    f"{format_price(values['k'])} / "
                    f"{format_price(values['d'])}",
                "EMA7/25/99":
                    f"{format_price(values['ema7'])} / "
                    f"{format_price(values['ema25'])} / "
                    f"{format_price(values['ema99'])}",
                "MACD hist": format_price(
                    values["hist"]
                ),
                "Supertrend": format_price(
                    values["supertrend"]
                ),
                "ATR10": format_price(
                    values["atr"]
                ),
                "ADX14": format_price(
                    values["adx"]
                ),
                "Bollinger L/U":
                    f"{format_price(values['bb_lower'])} / "
                    f"{format_price(values['bb_upper'])}",
                "RVOL20": format_price(
                    values["rvol"]
                ),
                "Delta taker %": format_price(
                    values["taker_delta"]
                ),
            }
        )

    st.dataframe(
        pd.DataFrame(metrics),
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "Delta taker = (2 × volume taker buy − volume totale) "
        "/ volume totale. RVOL confronta il volume con la media "
        "delle 20 candele precedenti. Non sono dati sui wallet "
        "o sulle liquidazioni."
    )

    with st.expander(
        "Calcolatore rischio: spot, senza leva"
    ):
        capital = st.number_input(
            "Capitale in valuta quotata",
            min_value=0.0,
            value=10000.0,
            step=500.0,
        )

        risk_percent = st.number_input(
            "Rischio massimo %",
            min_value=0.1,
            max_value=10.0,
            value=1.0,
            step=0.1,
        )

        current_price = float(
            table.loc[
                table["Coppia"] == chosen,
                "Prezzo ticker",
            ].iloc[0]
        )

        entry_price = st.number_input(
            "Prezzo ingresso",
            min_value=0.0,
            value=current_price,
            format="%.6f",
        )

        stop_price = st.number_input(
            "Prezzo stop",
            min_value=0.0,
            value=entry_price * 0.98,
            format="%.6f",
        )

        fee_percent = st.number_input(
            "Commissione stimata % per lato",
            min_value=0.0,
            max_value=2.0,
            value=0.1,
            step=0.01,
        )

        if entry_price > 0 and 0 < stop_price < entry_price:
            loss_per_unit = (
                entry_price
                - stop_price
                + entry_price * fee_percent / 100
                + stop_price * fee_percent / 100
            )

            units = min(
                capital / entry_price,
                capital * risk_percent
                / 100 / loss_per_unit,
            )

            st.info(
                f"Quantità: {units:.6f} · "
                f"Impiego: {units * entry_price:,.2f} · "
                f"Perdita stimata allo stop: "
                f"{units * loss_per_unit:,.2f} "
                "(commissioni incluse; slippage escluso)"
            )
        else:
            st.warning(
                "Per un long spot inserisci "
                "ingresso > stop > 0."
            )


dashboard()
