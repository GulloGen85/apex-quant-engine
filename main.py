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
    "HYPEUSDT", "BTCUSDC", "KASUSDT", "NEARUSDC",
    "ETHUSDC", "FETUSDC", "XRPUSDC", "SOLUSDC",
    "BNBUSDC", "BCHUSDC", "LINKUSDC", "AAVEUSDC",
    "ZECUSDC", "RENDERUSDC", "TAOUSDC", "AKTUSDT",
    "ONDOUSDC", "SUIUSDC", "WLDUSDC", "INJUSDC",
    "ENAUSDC", "UNIUSDC", "ARBUSDC",
]

BASE = {
    "spot": "https://data-api.binance.vision/api/v3",
    "perp": "https://fapi.binance.com/fapi/v1",
}

INTERVALS = ("15m", "1h", "4h", "1d")


def get(market, route, **params):
    response = requests.get(
        BASE[market] + route,
        params=params,
        headers={"User-Agent": "CryptoScreenerV2/1.0"},
        timeout=3.5,
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=30, show_spinner=False)
def fetch(symbol, market):
    rows = {}

    for interval in INTERVALS:
        raw = get(
            market,
            "/klines",
            symbol=symbol,
            interval=interval,
            limit=210,
        )

        frame = pd.DataFrame(
            raw,
            columns=[
                "open_time", "open", "high", "low",
                "close", "volume", "close_time",
                "quote_volume", "trades", "taker_buy",
                "taker_quote", "ignore",
            ],
        )

        for column in (
            "open", "high", "low", "close",
            "volume", "taker_buy", "close_time",
        ):
            frame[column] = pd.to_numeric(
                frame[column],
                errors="coerce",
            )

        frame = frame.dropna(
            subset=[
                "open", "high", "low", "close",
                "volume", "taker_buy", "close_time",
            ]
        )

        if len(frame) < 100:
            raise ValueError(
                f"Storico insufficiente su {interval}"
            )

        rows[interval] = frame

    ticker = get(
        market,
        "/ticker/24hr",
        symbol=symbol,
    )

    return (
        rows,
        {
            "price": float(ticker["lastPrice"]),
            "change": float(
                ticker["priceChangePercent"]
            ),
        },
        datetime.now(timezone.utc),
    )


def rma(series, period):
    return series.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()


def supertrend(high, low, close, period=10, factor=3):
    true_range = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = rma(true_range, period)

    upper = (high + low) / 2 + factor * atr
    lower = (high + low) / 2 - factor * atr

    final_upper = upper.copy()
    final_lower = lower.copy()

    bullish = pd.Series(False, index=close.index)
    line = pd.Series(float("nan"), index=close.index)

    for i in range(period, len(close)):
        previous = i - 1

        if i > period:
            if not (
                upper.iloc[i]
                < final_upper.iloc[previous]
                or close.iloc[previous]
                > final_upper.iloc[previous]
            ):
                final_upper.iloc[i] = (
                    final_upper.iloc[previous]
                )

            if not (
                lower.iloc[i]
                > final_lower.iloc[previous]
                or close.iloc[previous]
                < final_lower.iloc[previous]
            ):
                final_lower.iloc[i] = (
                    final_lower.iloc[previous]
                )

            if bullish.iloc[previous]:
                bullish.iloc[i] = (
                    close.iloc[i]
                    >= final_lower.iloc[previous]
                )
            else:
                bullish.iloc[i] = (
                    close.iloc[i]
                    > final_upper.iloc[previous]
                )
        else:
            bullish.iloc[i] = (
                close.iloc[i]
                >= (
                    high.iloc[i]
                    + low.iloc[i]
                ) / 2
            )

        line.iloc[i] = (
            final_lower.iloc[i]
            if bullish.iloc[i]
            else final_upper.iloc[i]
        )

    return line, bullish, atr


def indicators(frame):
    close = frame["close"].astype(float)
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    volume = frame["volume"].astype(float)

    change = close.diff()
    gain = rma(
        change.clip(lower=0), 14
    )
    loss = rma(
        (-change).clip(lower=0), 14
    )

    denominator = gain + loss

    rsi = (
        100 * gain
        / denominator.replace(
            0, float("nan")
        )
    )

    rsi = rsi.mask(
        (gain == 0) & (loss == 0),
        50,
    )
    rsi = rsi.mask(
        (loss == 0) & (gain > 0),
        100,
    )
    rsi = rsi.mask(
        (gain == 0) & (loss > 0),
        0,
    )

    rsi_low = rsi.rolling(14).min()
    rsi_high = rsi.rolling(14).max()

    stoch = (
        100 * (rsi - rsi_low)
        / (rsi_high - rsi_low).replace(
            0, float("nan")
        )
    )

    stoch_k = stoch.rolling(3).mean()
    stoch_d = stoch_k.rolling(3).mean()

    ema7 = close.ewm(
        span=7, adjust=False
    ).mean()

    ema25 = close.ewm(
        span=25, adjust=False
    ).mean()

    ema99 = close.ewm(
        span=99, adjust=False
    ).mean()

    ema12 = close.ewm(
        span=12, adjust=False
    ).mean()

    ema26 = close.ewm(
        span=26, adjust=False
    ).mean()

    macd = ema12 - ema26

    macd_signal = macd.ewm(
        span=9, adjust=False
    ).mean()

    macd_histogram = (
        macd - macd_signal
    )

    bb_middle = close.rolling(20).mean()
    bb_std = (
        close.rolling(20).std(ddof=0)
    )

    trend, bullish, atr = supertrend(
        high, low, close
    )

    upward_move = high.diff()
    downward_move = -low.diff()

    plus_dm = upward_move.where(
        (upward_move > downward_move)
        & (upward_move > 0),
        0,
    )

    minus_dm = downward_move.where(
        (downward_move > upward_move)
        & (downward_move > 0),
        0,
    )

    atr_safe = atr.replace(
        0, float("nan")
    )

    plus_di = (
        100 * rma(plus_dm, 14)
        / atr_safe
    )

    minus_di = (
        100 * rma(minus_dm, 14)
        / atr_safe
    )

    dx = (
        100 * (plus_di - minus_di).abs()
        / (plus_di + minus_di).replace(
            0, float("nan")
        )
    )

    adx = rma(dx, 14)

    volume_average = (
        volume.shift(1)
        .rolling(20)
        .mean()
    )

    taker_buy = frame[
        "taker_buy"
    ].astype(float)

    return {
        "close": close,
        "rsi": rsi,
        "k": stoch_k,
        "d": stoch_d,
        "hist": macd_histogram,
        "ema7": ema7,
        "ema25": ema25,
        "ema99": ema99,
        "bb_upper": (
            bb_middle + 2 * bb_std
        ),
        "bb_lower": (
            bb_middle - 2 * bb_std
        ),
        "supertrend": trend,
        "bull": bullish,
        "atr": atr,
        "adx": adx,
        "recent_low": (
            low.rolling(8).min()
        ),
        "recent_high": (
            high.rolling(8).max()
        ),
        "rvol": (
            volume
            / volume_average.replace(
                0, float("nan")
            )
        ),
        "taker_delta": (
            100
            * (2 * taker_buy - volume)
            / volume.replace(
                0, float("nan")
            )
        ),
    }


def safe(value):
    try:
        value = float(value)
        return (
            value
            if math.isfinite(value)
            else None
        )
    except (ValueError, TypeError):
        return None


def snapshot(calculated, position):
    return {
        key: safe(
            series.iloc[position]
        )
        for key, series
        in calculated.items()
    }


def classify(data, btc_bullish):
    daily = data["1d"]
    four_hour = data["4h"]
    one_hour = data["1h"]
    entry = data["15m"]

    if any(
        item["close"] is None
        or item["ema25"] is None
        for item in data.values()
    ):
        return (
            "DATI INSUFFICIENTI",
            0,
            "Indicatori non disponibili",
        )

    conditions = [
        daily["close"]
        > daily["ema25"],

        four_hour["close"]
        > four_hour["ema25"],

        four_hour["bull"] == 1,

        one_hour["ema7"]
        > one_hour["ema25"],

        one_hour["hist"] is not None
        and one_hour["hist"] > 0,

        entry["k"] is not None
        and entry["d"] is not None
        and entry["k"] > entry["d"],

        entry["close"]
        > entry["ema7"],

        entry["taker_delta"] is not None
        and entry["taker_delta"] > 0,

        entry["rvol"] is not None
        and entry["rvol"] >= 1.2,

        btc_bullish,
    ]

    score = sum(conditions)

    if (
        four_hour["close"]
        < four_hour["ema25"]
        and one_hour["close"]
        < one_hour["ema25"]
        and entry["close"]
        < entry["ema7"]
    ):
        return (
            "PRESSIONE RIBASSISTA",
            score,
            "Struttura 4H e 1H debole",
        )

    if (
        one_hour["rsi"] is not None
        and one_hour["rsi"] < 30
        and score < 6
    ):
        return (
            "IPERVENDUTO · ATTENDI",
            score,
            "RSI basso da solo "
            "non conferma un rimbalzo",
        )

    trigger = (
        score >= 7
        and entry["close"]
        > entry["ema7"]
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
            "Conferme tecniche presenti",
        )

    if score >= 6:
        return (
            "SETUP LONG · ATTENDI",
            score,
            "Confluenza parziale: "
            "attendi conferma",
        )

    return (
        "NEUTRALE",
        score,
        "Nessun trigger confermato",
    )


def trade_plan(
    frame,
    calculated_15m,
    position,
    ticker_price,
    fee_percent,
):
    point = snapshot(
        calculated_15m,
        position,
    )

    required = (
        "recent_high",
        "recent_low",
        "atr",
        "ema7",
    )

    if any(
        point[key] is None
        for key in required
    ):
        return None

    if (
        point["atr"] <= 0
        or ticker_price <= 0
    ):
        return None

    candle = frame.iloc[position]

    entry = max(
        float(candle["high"]),
        point["ema7"],
    ) + 0.05 * point["atr"]

    stop = min(
        point["recent_low"],
        entry - 1.5 * point["atr"],
    )

    risk = entry - stop

    if (
        risk <= 0
        or risk / entry > 0.10
    ):
        return None

    targets = [
        entry + risk * multiple
        for multiple in (1, 2, 3)
    ]

    net_returns = [
        100 * (
            (
                target
                * (1 - fee_percent / 100)
            )
            / (
                entry
                * (1 + fee_percent / 100)
            )
            - 1
        )
        for target in targets
    ]

    return {
        "entry": entry,
        "stop": stop,
        "risk_pct": (
            risk / entry * 100
        ),
        "targets": targets,
        "net": net_returns,
        "distance_pct": (
            100 * (
                entry / ticker_price - 1
            )
        ),
    }


def fmt(value):
    if value is None:
        return "—"

    if abs(value) >= 1000:
        return f"{value:,.2f}"

    if abs(value) >= 1:
        return f"{value:.3f}"

    return f"{value:.5f}"


st.title("⚡ Crypto Screener V2")

st.caption(
    "Dati pubblici Binance · "
    "segnali descrittivi, non ordini"
)

with st.sidebar:
    st.header("Impostazioni")

    raw = st.text_area(
        "Watchlist: simboli separati "
        "da virgole",
        ", ".join(PAIRS),
        height=160,
    )

    watch = list(
        dict.fromkeys(
            symbol.strip().upper()
            for symbol in raw.split(",")
            if symbol.strip()
        )
    )[:40]

    default_market = st.selectbox(
        "Mercato predefinito",
        ["spot", "perp"],
    )

    markets_for_pair = {
        symbol: st.selectbox(
            symbol,
            ["spot", "perp"],
            index=(
                0 if default_market == "spot"
                else 1
            ),
            key=f"market_{symbol}",
        )
        for symbol in watch
    }

    confirmed = st.toggle(
        "Segnali su candele chiuse",
        value=True,
    )

    refresh = st.selectbox(
        "Aggiornamento automatico",
        [30, 60, 120],
        index=1,
    )

    fee_percent = st.number_input(
        "Commissione stimata "
        "per lato (%)",
        min_value=0.0,
        max_value=2.0,
        value=0.1,
        step=0.01,
    )


@st.fragment(run_every=f"{refresh}s")
def dashboard():
    selected = [
        (
            symbol,
            markets_for_pair[symbol],
        )
        for symbol in watch
    ]

    if not selected:
        st.info(
            "Inserisci almeno una coppia."
        )
        return

    # Test rapido: se la prima richiesta fallisce,
    # evita oltre 100 richieste destinate a fallire.
    try:
        probe_symbol, probe_market = (
            selected[0]
        )

        get(
            probe_market,
            "/klines",
            symbol=probe_symbol,
            interval="15m",
            limit=2,
        )

    except requests.HTTPError as error:
        code = (
            error.response.status_code
            if error.response is not None
            else "?"
        )

        st.error(
            "Binance non risponde "
            "dal server dell'app: "
            f"HTTP {code} "
            f"({probe_market}, "
            f"{probe_symbol})."
        )
        return

    except requests.RequestException as error:
        st.error(
            "Connessione API non riuscita: "
            f"{type(error).__name__}. "
            "La scansione è stata fermata."
        )
        return

    packs = {}
    errors = {}

    progress = st.progress(
        0,
        text="Caricamento coppie...",
    )

    with ThreadPoolExecutor(
        max_workers=12
    ) as executor:
        futures = {
            executor.submit(
                fetch,
                symbol,
                market,
            ): (symbol, market)
            for symbol, market
            in selected
        }

        for count, future in enumerate(
            as_completed(futures),
            1,
        ):
            progress.progress(
                count / len(futures),
                text=(
                    f"Caricate "
                    f"{count}/{len(futures)} "
                    "coppie"
                ),
            )

            symbol, market = (
                futures[future]
            )

            try:
                packs[symbol] = (
                    market,
                    *future.result(),
                )

            except requests.HTTPError as error:
                code = (
                    error.response.status_code
                    if error.response is not None
                    else "?"
                )

                errors[symbol] = (
                    f"HTTP {code} "
                    f"({market})"
                )

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

    progress.empty()

    if errors:
        with st.expander(
            "⚠️ Dati non disponibili: "
            f"{len(errors)} coppie",
            expanded=not packs,
        ):
            for symbol, error in (
                errors.items()
            ):
                st.write(
                    f"**{symbol}:** "
                    f"{error}"
                )

    if not packs:
        st.error(
            "Nessuna coppia caricata. "
            "Leggi gli errori mostrati "
            "qui sopra."
        )
        return

    position = (
        -2 if confirmed
        else -1
    )

    btc_bullish = False

    if "BTCUSDC" in packs:
        (
            _,
            btc_frames,
            _,
            _,
        ) = packs["BTCUSDC"]

        btc_values = snapshot(
            indicators(
                btc_frames["4h"]
            ),
            position,
        )

        btc_bullish = bool(
            btc_values["close"]
            is not None
            and btc_values["ema25"]
            is not None
            and btc_values["close"]
            > btc_values["ema25"]
        )

    rows = []
    details = {}

    for symbol in watch:
        if symbol not in packs:
            continue

        (
            market,
            frames,
            ticker,
            updated,
        ) = packs[symbol]

        try:
            calculated = {
                timeframe: indicators(
                    frame
                )
                for timeframe, frame
                in frames.items()
            }

            values = {
                timeframe: snapshot(
                    calculated[timeframe],
                    position,
                )
                for timeframe
                in INTERVALS
            }

            (
                state,
                score,
                explanation,
            ) = classify(
                values,
                btc_bullish,
            )

            plan = trade_plan(
                frames["15m"],
                calculated["15m"],
                position,
                ticker["price"],
                fee_percent,
            )

            candle_time = (
                pd.to_datetime(
                    frames["15m"][
                        "close_time"
                    ].iloc[position],
                    unit="ms",
                    utc=True,
                )
            )

            rows.append(
                {
                    "Coppia": symbol,
                    "Mercato": market,
                    "Prezzo ticker":
                        ticker["price"],
                    "24h %":
                        ticker["change"],
                    "Stato": state,
                    "Score /10": score,
                    "RSI 1H":
                        values["1h"]["rsi"],
                    "ADX 4H":
                        values["4h"]["adx"],
                    "Delta taker 1H %":
                        values["1h"][
                            "taker_delta"
                        ],
                    "RVOL 1H":
                        values["1h"]["rvol"],
                    "Entry":
                        plan["entry"]
                        if plan else None,
                    "Stop":
                        plan["stop"]
                        if plan else None,
                    "TP1":
                        plan["targets"][0]
                        if plan else None,
                    "TP2":
                        plan["targets"][1]
                        if plan else None,
                    "TP3":
                        plan["targets"][2]
                        if plan else None,
                    "TP1 netto %":
                        plan["net"][0]
                        if plan else None,
                    "TP2 netto %":
                        plan["net"][1]
                        if plan else None,
                    "TP3 netto %":
                        plan["net"][2]
                        if plan else None,
                    "Rischio stop %":
                        plan["risk_pct"]
                        if plan else None,
                }
            )

            details[symbol] = (
                values,
                explanation,
                candle_time,
                market,
                updated,
                plan,
            )

        except (
            ValueError,
            KeyError,
            IndexError,
        ):
            errors[symbol] = (
                "Indicatori incompleti"
            )

    st.caption(
        "Ultima lettura: "
        + datetime.now(
            timezone.utc
        ).strftime(
            "%Y-%m-%d "
            "%H:%M:%S UTC"
        )
        + (
            " · candele chiuse"
            if confirmed
            else (
                " · candele aperte: "
                "segnali provvisori"
            )
        )
    )

    if not rows:
        st.error(
            "Dati ricevuti, "
            "ma indicatori "
            "non calcolabili."
        )
        return

    ranking = pd.DataFrame(
        rows
    )

    priority = {
        "TRIGGER LONG": 3,
        "SETUP LONG · ATTENDI": 2,
        "NEUTRALE": 1,
    }

    ranking["Priorità"] = (
        ranking["Stato"]
        .map(priority)
        .fillna(0)
    )

    ranking = (
        ranking
        .sort_values(
            [
                "Priorità",
                "Score /10",
                "24h %",
            ],
            ascending=False,
        )
        .drop(
            columns="Priorità"
        )
    )

    st.subheader(
        "📊 Classifica"
    )

    st.dataframe(
        ranking,
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "La classifica dà "
        "precedenza ai trigger, "
        "poi allo score. Entry, "
        "stop e target sono "
        "scenari calcolati: "
        "lo score non è una "
        "probabilità di profitto."
    )

    chosen = st.selectbox(
        "Analisi coppia",
        ranking[
            "Coppia"
        ].tolist(),
    )

    (
        values,
        explanation,
        candle_time,
        market,
        updated,
        plan,
    ) = details[chosen]

    current_state = (
        ranking.loc[
            ranking["Coppia"]
            == chosen,
            "Stato",
        ].iloc[0]
    )

    st.subheader(
        f"{chosen} · "
        f"{market} · "
        f"{current_state}"
    )

    st.write(
        explanation
    )

    if plan:
        st.info(
            f"Ingresso sopra "
            f"{fmt(plan['entry'])}"
            " · Stop "
            f"{fmt(plan['stop'])}"
            " ("
            f"{-plan['risk_pct']:.2f}%"
            ") · TP1 "
            f"{fmt(plan['targets'][0])}"
            " ("
            f"{plan['net'][0]:+.2f}%"
            " netto) · TP2 "
            f"{fmt(plan['targets'][1])}"
            " ("
            f"{plan['net'][1]:+.2f}%"
            " netto) · TP3 "
            f"{fmt(plan['targets'][2])}"
            " ("
            f"{plan['net'][2]:+.2f}%"
            " netto)"
        )

        if (
            current_state
            != "TRIGGER LONG"
        ):
            st.warning(
                "Livelli di scenario: "
                "ingresso non confermato. "
                f"Stato: {current_state}"
            )

        st.caption(
            "Distanza trigger "
            "dal ticker: "
            f"{plan['distance_pct']:+.2f}%"
            ". Target a 1R/2R/3R, "
            "al netto delle "
            "commissioni stimate. "
            "Slippage escluso."
        )

    st.caption(
        "Candela 15m usata: "
        f"{candle_time}"
        " · Dati scaricati: "
        f"{updated.strftime('%H:%M:%S UTC')}"
    )

    metric_rows = []

    for timeframe in (
        INTERVALS
    ):
        point = values[
            timeframe
        ]

        metric_rows.append(
            {
                "TF": timeframe,
                "Chiusura":
                    fmt(
                        point["close"]
                    ),
                "RSI14":
                    fmt(
                        point["rsi"]
                    ),
                "Stoch K/D":
                    f"{fmt(point['k'])}"
                    " / "
                    f"{fmt(point['d'])}",
                "EMA7/25/99":
                    f"{fmt(point['ema7'])}"
                    " / "
                    f"{fmt(point['ema25'])}"
                    " / "
                    f"{fmt(point['ema99'])}",
                "MACD hist":
                    fmt(
                        point["hist"]
                    ),
                "Supertrend":
                    fmt(
                        point[
                            "supertrend"
                        ]
                    ),
                "ATR10":
                    fmt(
                        point["atr"]
                    ),
                "ADX14":
                    fmt(
                        point["adx"]
                    ),
                "Bollinger L/U":
                    f"{fmt(point['bb_lower'])}"
                    " / "
                    f"{fmt(point['bb_upper'])}",
                "RVOL20":
                    fmt(
                        point["rvol"]
                    ),
                "Delta taker %":
                    fmt(
                        point[
                            "taker_delta"
                        ]
                    ),
            }
        )

    st.dataframe(
        pd.DataFrame(
            metric_rows
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "Delta taker: pressione "
        "degli scambi aggressivi "
        "nella candela. Non è "
        "un dato sui wallet o "
        "sulle liquidazioni."
    )

    with st.expander(
        "Calcolatore rischio "
        "spot, senza leva"
    ):
        capital = st.number_input(
            "Capitale in "
            "valuta quotata",
            min_value=0.0,
            value=10000.0,
            step=500.0,
        )

        risk_percent = (
            st.number_input(
                "Rischio massimo %",
                min_value=0.1,
                max_value=10.0,
                value=1.0,
                step=0.1,
            )
        )

        current_price = float(
            ranking.loc[
                ranking["Coppia"]
                == chosen,
                "Prezzo ticker",
            ].iloc[0]
        )

        entry_price = (
            st.number_input(
                "Prezzo ingresso",
                min_value=0.0,
                value=current_price,
                format="%.6f",
            )
        )

        stop_price = (
            st.number_input(
                "Prezzo stop",
                min_value=0.0,
                value=(
                    entry_price
                    * 0.98
                ),
                format="%.6f",
            )
        )

        fee = st.number_input(
            "Commissione % "
            "per lato",
            min_value=0.0,
            max_value=2.0,
            value=0.1,
            step=0.01,
        )

        if (
            entry_price > 0
            and 0 < stop_price
            < entry_price
        ):
            loss_per_unit = (
                entry_price
                - stop_price
                + (
                    entry_price
                    * fee / 100
                )
                + (
                    stop_price
                    * fee / 100
                )
            )

            units = min(
                capital
                / entry_price,
                (
                    capital
                    * risk_percent
                    / 100
                    / loss_per_unit
                ),
            )

            st.info(
                "Quantità: "
                f"{units:.6f}"
                " · Impiego: "
                f"{units * entry_price:,.2f}"
                " · Perdita stimata "
                "allo stop: "
                f"{units * loss_per_unit:,.2f}"
                " (commissioni "
                "incluse; slippage "
                "escluso)"
            )
        else:
            st.warning(
                "Per un long spot "
                "inserisci ingresso "
                "> stop > 0."
            )


dashboard()
