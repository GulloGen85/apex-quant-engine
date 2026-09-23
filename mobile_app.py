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

PERP_DEFAULT = {
    "HYPEUSDT",
    "KASUSDT",
    "AKTUSDT",
}

API = {
    "spot": "https://data-api.binance.vision/api/v3",
    "perp": "https://fapi.binance.com/fapi/v1",
}

TIMEFRAMES = ("15m", "1h", "4h", "1d")


def api_get(market, endpoint, **params):
    response = requests.get(
        API[market] + endpoint,
        params=params,
        headers={"User-Agent": "CryptoScreenerV2/1.0"},
        timeout=3.5,
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=30, show_spinner=False)
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
                f"Storico insufficiente su {timeframe}"
            )

        frames[timeframe] = frame

    ticker = api_get(
        market,
        "/ticker/24hr",
        symbol=symbol,
    )

    return {
        "frames": frames,
        "price": float(ticker["lastPrice"]),
        "change": float(ticker["priceChangePercent"]),
        "updated": datetime.now(timezone.utc),
    }


def rma(series, period):
    return series.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()


def calculate_supertrend(
    high,
    low,
    close,
    period=10,
    multiplier=3,
):
    true_range = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = rma(true_range, period)
    middle = (high + low) / 2

    basic_upper = middle + multiplier * atr
    basic_lower = middle - multiplier * atr

    upper = basic_upper.copy()
    lower = basic_lower.copy()

    bullish = pd.Series(False, index=close.index)
    line = pd.Series(float("nan"), index=close.index)

    for i in range(period, len(close)):
        previous = i - 1

        if i == period:
            bullish.iloc[i] = (
                close.iloc[i] >= middle.iloc[i]
            )
        else:
            if not (
                basic_upper.iloc[i] < upper.iloc[previous]
                or close.iloc[previous] > upper.iloc[previous]
            ):
                upper.iloc[i] = upper.iloc[previous]

            if not (
                basic_lower.iloc[i] > lower.iloc[previous]
                or close.iloc[previous] < lower.iloc[previous]
            ):
                lower.iloc[i] = lower.iloc[previous]

            if bullish.iloc[previous]:
                bullish.iloc[i] = (
                    close.iloc[i] >= lower.iloc[previous]
                )
            else:
                bullish.iloc[i] = (
                    close.iloc[i] > upper.iloc[previous]
                )

        line.iloc[i] = (
            lower.iloc[i]
            if bullish.iloc[i]
            else upper.iloc[i]
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

    rsi = (
        100 * gain
        / (gain + loss).replace(0, float("nan"))
    )
    rsi = rsi.mask((gain == 0) & (loss == 0), 50)
    rsi = rsi.mask((loss == 0) & (gain > 0), 100)
    rsi = rsi.mask((gain == 0) & (loss > 0), 0)

    rsi_low = rsi.rolling(14).min()
    rsi_high = rsi.rolling(14).max()

    stoch_rsi = (
        100 * (rsi - rsi_low)
        / (rsi_high - rsi_low).replace(
            0, float("nan")
        )
    )

    stoch_k = stoch_rsi.rolling(3).mean()
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
    macd_histogram = macd - macd_signal

    bollinger_middle = close.rolling(20).mean()
    bollinger_std = close.rolling(20).std(ddof=0)

    supertrend, bullish, atr = (
        calculate_supertrend(
            high, low, close
        )
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

    atr_safe = atr.replace(0, float("nan"))

    plus_di = (
        100 * rma(plus_dm, 14) / atr_safe
    )
    minus_di = (
        100 * rma(minus_dm, 14) / atr_safe
    )

    dx = (
        100 * (plus_di - minus_di).abs()
        / (plus_di + minus_di).replace(
            0, float("nan")
        )
    )
    adx = rma(dx, 14)

    average_volume = (
        volume.shift(1)
        .rolling(20)
        .mean()
    )

    taker_buy = frame["taker_buy"].astype(float)

    return pd.DataFrame(
        {
            "close": close,
            "rsi": rsi,
            "k": stoch_k,
            "d": stoch_d,
            "ema7": ema7,
            "ema25": ema25,
            "ema99": ema99,
            "hist": macd_histogram,
            "bb_lower": (
                bollinger_middle
                - 2 * bollinger_std
            ),
            "bb_upper": (
                bollinger_middle
                + 2 * bollinger_std
            ),
            "supertrend": supertrend,
            "bullish": bullish,
            "atr": atr,
            "adx": adx,
            "recent_low": low.rolling(8).min(),
            "recent_high": high.rolling(8).max(),
            "rvol": (
                volume
                / average_volume.replace(
                    0, float("nan")
                )
            ),
            "taker_delta": (
                100 * (2 * taker_buy - volume)
                / volume.replace(
                    0, float("nan")
                )
            ),
        }
    )


def calculate_state(points, btc_bullish):
    daily = points["1d"]
    four_hour = points["4h"]
    one_hour = points["1h"]
    entry = points["15m"]

    required = [
        daily["close"], daily["ema25"],
        four_hour["close"], four_hour["ema25"],
        one_hour["close"], one_hour["ema25"],
        one_hour["ema7"], one_hour["hist"],
        entry["close"], entry["ema7"],
    ]

    if any(pd.isna(value) for value in required):
        return "DATI INSUFFICIENTI", 0

    conditions = [
        daily["close"] > daily["ema25"],
        four_hour["close"] > four_hour["ema25"],
        bool(four_hour["bullish"]),
        one_hour["ema7"] > one_hour["ema25"],
        one_hour["hist"] > 0,
        pd.notna(entry["k"])
        and pd.notna(entry["d"])
        and entry["k"] > entry["d"],
        entry["close"] > entry["ema7"],
        pd.notna(entry["taker_delta"])
        and entry["taker_delta"] > 0,
        pd.notna(entry["rvol"])
        and entry["rvol"] >= 1.2,
        btc_bullish,
    ]

    score = sum(conditions)

    if (
        four_hour["close"] < four_hour["ema25"]
        and one_hour["close"] < one_hour["ema25"]
        and entry["close"] < entry["ema7"]
    ):
        return "PRESSIONE RIBASSISTA", score

    if (
        pd.notna(one_hour["rsi"])
        and one_hour["rsi"] < 30
        and score < 6
    ):
        return "IPERVENDUTO · ATTENDI", score

    if (
        score >= 7
        and entry["close"] > entry["ema7"]
        and pd.notna(entry["k"])
        and pd.notna(entry["d"])
        and entry["k"] > entry["d"]
        and one_hour["hist"] > 0
    ):
        return "TRIGGER LONG", score

    if score >= 6:
        return "SETUP LONG · ATTENDI", score

    return "NEUTRALE", score


def make_plan(
    frame,
    calculated,
    position,
    ticker_price,
    fee_percent,
):
    point = calculated.iloc[position]

    required = (
        "recent_high",
        "recent_low",
        "atr",
        "ema7",
    )

    if any(
        pd.isna(point[key])
        for key in required
    ):
        return None

    if point["atr"] <= 0 or ticker_price <= 0:
        return None

    candle = frame.iloc[position]

    entry = max(
        float(candle["high"]),
        float(point["ema7"]),
    ) + 0.05 * float(point["atr"])

    stop = min(
        float(point["recent_low"]),
        entry - 1.5 * float(point["atr"]),
    )

    risk = entry - stop

    if risk <= 0 or risk / entry > 0.10:
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
        "risk_pct": risk / entry * 100,
        "targets": targets,
        "net": net_returns,
        "distance_pct": (
            100 * (entry / ticker_price - 1)
        ),
    }


def fmt(value):
    if value is None or pd.isna(value):
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
        "Watchlist: simboli separati da virgole",
        value=", ".join(PAIRS),
        height=180,
    )

    watchlist = list(
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

    selected_markets = {}

    for symbol in watchlist:
        initial_market = (
            "perp"
            if symbol in PERP_DEFAULT
            else default_market
        )

        selected_markets[symbol] = st.selectbox(
            symbol,
            ["spot", "perp"],
            index=(
                1 if initial_market == "perp"
                else 0
            ),
            key=f"market_{symbol}",
        )

    use_closed_candles = st.toggle(
        "Segnali su candele chiuse",
        value=True,
    )

    refresh_seconds = st.selectbox(
        "Aggiornamento automatico",
        [30, 60, 120],
        index=1,
        format_func=lambda value: (
            f"{value} secondi"
        ),
    )

    fee_percent = st.number_input(
        "Commissione stimata per lato (%)",
        min_value=0.0,
        max_value=2.0,
        value=0.1,
        step=0.01,
    )


@st.fragment(
    run_every=f"{refresh_seconds}s"
)
def dashboard():
    if not watchlist:
        st.info(
            "Inserisci almeno una coppia."
        )
        return

    selected = [
        (symbol, selected_markets[symbol])
        for symbol in watchlist
    ]

    # Verifica una coppia spot nota.
    # Un simbolo perpetual non blocca la scansione.
    try:
        api_get(
            "spot",
            "/klines",
            symbol="BTCUSDC",
            interval="15m",
            limit=2,
        )

    except requests.HTTPError as error:
        status = (
            error.response.status_code
            if error.response is not None
            else "?"
        )

        st.error(
            "Test iniziale BTCUSDC spot: "
            f"HTTP {status}. "
            "La scansione è stata fermata; "
            "controlla i log dell'app."
        )
        return

    except requests.RequestException as error:
        st.error(
            "Connessione alle API non riuscita: "
            f"{type(error).__name__}. "
            "La scansione è stata fermata."
        )
        return

    results = {}
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
                fetch_pair,
                symbol,
                market,
            ): (symbol, market)
            for symbol, market in selected
        }

        for count, future in enumerate(
            as_completed(futures),
            start=1,
        ):
            symbol, market = futures[future]

            try:
                results[symbol] = future.result()

            except requests.HTTPError as error:
                status = (
                    error.response.status_code
                    if error.response is not None
                    else "?"
                )

                errors[symbol] = (
                    f"HTTP {status} ({market})"
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

            progress.progress(
                count / len(futures),
                text=(
                    f"Elaborate {count}/"
                    f"{len(futures)} coppie"
                ),
            )

    progress.empty()

    if errors:
        with st.expander(
            f"⚠️ Coppie non disponibili: "
            f"{len(errors)}",
            expanded=not results,
        ):
            for symbol, error in errors.items():
                st.write(
                    f"**{symbol}:** {error}"
                )

    if not results:
        st.error(
            "Nessuna coppia caricata. "
            "Leggi gli errori qui sopra."
        )
        return

    position = (
        -2 if use_closed_candles
        else -1
    )

    btc_bullish = False

    if "BTCUSDC" in results:
        btc_frame = results[
            "BTCUSDC"
        ]["frames"]["4h"]

        btc_point = (
            calculate_indicators(
                btc_frame
            ).iloc[position]
        )

        btc_bullish = bool(
            pd.notna(btc_point["ema25"])
            and btc_point["close"]
            > btc_point["ema25"]
        )

    rows = []
    details = {}

    for symbol in watchlist:
        if symbol not in results:
            continue

        pack = results[symbol]
        points = {}
        calculated = {}

        try:
            for timeframe in TIMEFRAMES:
                calculated[timeframe] = (
                    calculate_indicators(
                        pack["frames"][
                            timeframe
                        ]
                    )
                )

                points[timeframe] = (
                    calculated[
                        timeframe
                    ].iloc[position]
                )

            state, score = calculate_state(
                points,
                btc_bullish,
            )

            plan = make_plan(
                pack["frames"]["15m"],
                calculated["15m"],
                position,
                pack["price"],
                fee_percent,
            )

            candle_time = (
                pd.to_datetime(
                    pack["frames"][
                        "15m"
                    ]["close_time"]
                    .iloc[position],
                    unit="ms",
                    utc=True,
                )
            )

            rows.append(
                {
                    "Coppia": symbol,
                    "Mercato":
                        selected_markets[
                            symbol
                        ],
                    "Prezzo":
                        pack["price"],
                    "24h %":
                        pack["change"],
                    "Stato": state,
                    "Score /10": score,
                    "RSI 1H":
                        points["1h"][
                            "rsi"
                        ],
                    "ADX 4H":
                        points["4h"][
                            "adx"
                        ],
                    "Delta taker 1H %":
                        points["1h"][
                            "taker_delta"
                        ],
                    "RVOL 1H":
                        points["1h"][
                            "rvol"
                        ],
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

            details[symbol] = {
                "points": points,
                "plan": plan,
                "time": candle_time,
                "updated": pack[
                    "updated"
                ],
            }

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
            "%d/%m/%Y "
            "%H:%M:%S UTC"
        )
        + (
            " · candele chiuse"
            if use_closed_candles
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

    ranking = pd.DataFrame(rows)

    priorities = {
        "TRIGGER LONG": 3,
        "SETUP LONG · ATTENDI": 2,
        "NEUTRALE": 1,
    }

    ranking["Priorità"] = (
        ranking["Stato"]
        .map(priorities)
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
        .drop(columns="Priorità")
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
        "poi allo score. "
        "Entry, stop e target "
        "sono scenari tecnici, "
        "non ordini automatici."
    )

    chosen = st.selectbox(
        "Analisi coppia",
        ranking["Coppia"].tolist(),
    )

    detail = details[chosen]
    points = detail["points"]
    plan = detail["plan"]

    state = ranking.loc[
        ranking["Coppia"] == chosen,
        "Stato",
    ].iloc[0]

    st.subheader(
        f"{chosen} · "
        f"{selected_markets[chosen]} "
        f"· {state}"
    )

    if plan:
        st.info(
            f"Entry sopra "
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

        if state != "TRIGGER LONG":
            st.warning(
                "Livelli di scenario: "
                "ingresso non confermato. "
                f"Stato attuale: {state}"
            )

        st.caption(
            "Distanza dell'entry "
            "dal prezzo ticker: "
            f"{plan['distance_pct']:+.2f}%"
            ". TP a 1R/2R/3R. "
            "Rendimenti al netto "
            "delle commissioni "
            "impostate; slippage "
            "escluso."
        )

    st.caption(
        "Candela 15m usata: "
        f"{detail['time']}"
        " · Dati scaricati: "
        f"{detail['updated'].strftime('%H:%M:%S UTC')}"
    )

    metric_rows = []

    for timeframe in TIMEFRAMES:
        point = points[timeframe]

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
        pd.DataFrame(metric_rows),
        hide_index=True,
        use_container_width=True,
    )

    st.caption(
        "Lo score conta dieci "
        "condizioni tecniche: "
        "non è una probabilità "
        "di guadagno. Il delta "
        "taker misura gli scambi "
        "aggressivi della candela, "
        "non i wallet."
    )

    with st.expander(
        "🎯 Calcolatore rischio spot"
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
                "Prezzo",
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
                + entry_price
                * fee / 100
                + stop_price
                * fee / 100
            )

            quantity = min(
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
                f"{quantity:.6f}"
                " · Impiego: "
                f"{quantity * entry_price:,.2f}"
                " · Perdita stimata "
                "allo stop: "
                f"{quantity * loss_per_unit:,.2f}"
                " (commissioni "
                "incluse; slippage "
                "escluso)"
            )
        else:
            st.warning(
                "Inserisci ingresso "
                "> stop > 0."
            )


dashboard()
