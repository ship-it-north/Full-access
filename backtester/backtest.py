"""Moteur de backtest événementiel barre par barre.

Ordre de traitement d'une barre (garantit l'absence de look-ahead) :
  1. gestion des positions ouvertes avec l'OHLC de la barre courante ;
  2. tentative d'exécution des ordres en attente posés à une barre ANTÉRIEURE ;
  3. sélection des entrées dans la limite des slots libres ;
  4. au close seulement, (re)calcul des setups qui arment les ordres de la barre suivante.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from config import MAX_LEVERAGE, StrategyConfig
from rules import Setup, check_entry_levels, scan_setups


@dataclass
class Trade:
    pair: str
    variant: str
    entry_time: pd.Timestamp
    entry_index: int
    entry_price: float
    initial_stop: float
    target: float
    b_price: float
    a_price: float
    l1: float
    l2: float
    rr_planned: float
    qty: float
    risk_amount: float
    notional: float
    size_capped: bool
    exit_time: pd.Timestamp | None = None
    exit_index: int | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    bars_held: int = 0
    gross_pnl: float = 0.0
    fees: float = 0.0
    funding: float = 0.0
    net_pnl: float = 0.0
    r_multiple: float = 0.0
    moved_to_breakeven: bool = False
    equity_after: float = 0.0


@dataclass
class _Position:
    trade: Trade
    stop: float
    breakeven: bool = False


@dataclass
class _Pending:
    """Ordre armé au close de `armed_index`, exploitable à partir de armed_index+1."""

    setup: Setup
    armed_index: int
    touch_index: int | None = None  # variante B : barre de la touche de L1


@dataclass
class BacktestResult:
    config: StrategyConfig
    trades: pd.DataFrame
    equity_curve: pd.DataFrame
    ruined: bool = False
    skip_stats: dict = field(default_factory=dict)


def prepare_pair_frames(
    raw: dict[str, pd.DataFrame],
    cfg: StrategyConfig,
) -> tuple[dict[str, dict], pd.DatetimeIndex, dict[str, int]]:
    """Précalcule les setups par paire (indépendants du niveau de risque)."""
    prepared: dict[str, dict] = {}
    skip_stats: dict[str, int] = {}
    all_ts: list[pd.DatetimeIndex] = []
    for pair, df in raw.items():
        if len(df) < cfg.trend_lookback + cfg.support_lookback:
            continue
        df = df.sort_index()
        setups, trend, stats = scan_setups(
            df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy(), cfg
        )
        for k, v in stats.items():
            skip_stats[k] = skip_stats.get(k, 0) + v
        prepared[pair] = {
            "index": df.index,
            "open": df["open"].to_numpy(float),
            "high": df["high"].to_numpy(float),
            "low": df["low"].to_numpy(float),
            "close": df["close"].to_numpy(float),
            "setups": setups,
            "trend": trend,
            "pos": {ts: i for i, ts in enumerate(df.index)},
        }
        all_ts.append(df.index)
    if not all_ts:
        return {}, pd.DatetimeIndex([]), skip_stats
    timeline = all_ts[0]
    for idx in all_ts[1:]:
        timeline = timeline.union(idx)
    return prepared, timeline.sort_values(), skip_stats


def _fill_variant_a(bar: dict, setup: Setup) -> float | None:
    """Limite à L1 : remplie si le low touche L1 (prix d'exécution = L1)."""
    if bar["low"] <= setup.l1:
        # Gap sous L1 à l'ouverture : exécution à l'open, plus défavorable pour nous.
        return min(setup.l1, bar["open"]) if bar["open"] < setup.l1 else setup.l1
    return None


def _fill_variant_b(bar: dict, pending: _Pending, i: int, cfg: StrategyConfig) -> float | None:
    """Touche de L1 puis clôture haussière au-dessus de L1 dans les 3 barres suivantes."""
    setup = pending.setup
    if pending.touch_index is None:
        if bar["low"] <= setup.l1:
            pending.touch_index = i
        return None
    if i <= pending.touch_index:
        return None
    if i - pending.touch_index > cfg.breakout_confirm_bars:
        pending.touch_index = i if bar["low"] <= setup.l1 else None
        return None
    if bar["close"] > bar["open"] and bar["close"] > setup.l1:
        return float(bar["close"])
    return None


def run_backtest(
    prepared: dict[str, dict],
    timeline: pd.DatetimeIndex,
    cfg: StrategyConfig,
) -> BacktestResult:
    equity = cfg.initial_capital
    open_positions: dict[str, _Position] = {}
    pendings: dict[str, _Pending] = {}
    closed: list[Trade] = []
    curve: list[tuple[pd.Timestamp, float, int]] = []
    ruined = False

    entry_fee = cfg.maker_fee if cfg.entry_variant == "A" else cfg.taker_fee

    for ts in timeline:
        if ruined:
            break

        # --- Phase 1 : gestion des positions ouvertes ---------------------- #
        for pair in list(open_positions):
            data = prepared[pair]
            i = data["pos"].get(ts)
            if i is None:
                continue
            pos = open_positions[pair]
            bar = {k: data[k][i] for k in ("open", "high", "low", "close")}
            equity, trade = _manage_bar(pos, bar, i, ts, equity, entry_fee, cfg)
            if trade is not None:
                closed.append(trade)
                del open_positions[pair]
                curve.append((ts, equity, len(open_positions)))
                if equity <= 0:
                    ruined = True
                    break

        if ruined:
            break

        # --- Phase 2 : exécution des ordres armés aux barres précédentes ---- #
        candidates: list[tuple[float, str, float, _Pending, int]] = []
        for pair, pending in list(pendings.items()):
            if pair in open_positions:
                continue
            data = prepared[pair]
            i = data["pos"].get(ts)
            if i is None or i <= pending.armed_index:
                continue
            bar = {k: data[k][i] for k in ("open", "high", "low", "close")}
            if cfg.entry_variant == "A":
                price = _fill_variant_a(bar, pending.setup)
            else:
                price = _fill_variant_b(bar, pending, i, cfg)
            if price is None:
                continue
            setup = pending.setup
            target = price + setup.leg
            if check_entry_levels(price, setup.stop, target, cfg) is not None:
                continue
            rr = (target - price) / (price - setup.stop)
            candidates.append((rr, pair, price, pending, i))

        # --- Phase 3 : ouverture dans la limite des slots libres ------------ #
        candidates.sort(key=lambda c: (-c[0], c[1]))
        for rr, pair, price, pending, i in candidates:
            if len(open_positions) >= cfg.max_concurrent:
                break
            setup = pending.setup
            trade = _open_trade(pair, cfg, ts, i, price, setup, rr, equity)
            if trade is None:
                continue
            pos = _Position(trade=trade, stop=setup.stop)
            open_positions[pair] = pos
            pendings.pop(pair, None)
            if cfg.entry_variant == "A":
                # Entrée intra-barre : le reste de la bougie peut déjà toucher le stop.
                data = prepared[pair]
                bar = {k: data[k][i] for k in ("open", "high", "low", "close")}
                equity, closed_trade = _manage_bar(pos, bar, i, ts, equity, entry_fee, cfg)
                if closed_trade is not None:
                    closed.append(closed_trade)
                    del open_positions[pair]
                    if equity <= 0:
                        ruined = True
                        break

        if ruined:
            break

        # --- Phase 4 : armement des ordres pour les barres suivantes -------- #
        for pair, data in prepared.items():
            i = data["pos"].get(ts)
            if i is None:
                continue
            if pair in open_positions:
                pendings.pop(pair, None)
                continue
            setup = data["setups"][i]
            existing = pendings.get(pair)
            if setup is None:
                # Pas de setup valide à ce close : l'ordre déjà armé survit tant que
                # la tendance tient et qu'il n'a pas expiré (cf. PENDING_EXPIRY_BARS).
                if existing is not None and (
                    not data["trend"][i]
                    or i - existing.armed_index >= cfg.pending_expiry_bars
                ):
                    pendings.pop(pair, None)
                continue
            if (
                existing is not None
                and abs(existing.setup.l1 - setup.l1) / setup.l1 < 1e-9
                and abs(existing.setup.stop - setup.stop) / setup.stop < 1e-9
            ):
                existing.setup = setup  # mêmes niveaux : l'ordre et son état restent
            else:
                pendings[pair] = _Pending(setup=setup, armed_index=i)

        curve.append((ts, equity, len(open_positions)))

    trades_df = pd.DataFrame([asdict(t) for t in closed])
    curve_df = pd.DataFrame(curve, columns=["timestamp", "equity", "open_positions"])
    if not curve_df.empty:
        curve_df = curve_df.drop_duplicates("timestamp", keep="last").set_index("timestamp")
    return BacktestResult(config=cfg, trades=trades_df, equity_curve=curve_df, ruined=ruined)


def _manage_bar(
    pos: _Position,
    bar: dict,
    i: int,
    ts: pd.Timestamp,
    equity: float,
    entry_fee: float,
    cfg: StrategyConfig,
) -> tuple[float, Trade | None]:
    """Applique stop / cible / time stop / breakeven sur une barre. Retourne (equity, trade fermé)."""
    trade = pos.trade
    bars_held = i - trade.entry_index
    hit_stop = bar["low"] <= pos.stop
    hit_target = bar["high"] >= trade.target

    exit_price = exit_reason = None
    if hit_stop and hit_target:
        # Chemin intra-barre inconnu : hypothèse conservatrice = perte.
        exit_price = _stop_exec_price(bar, pos.stop, cfg)
        exit_reason = "stop_and_target_same_bar"
    elif hit_stop:
        exit_price = _stop_exec_price(bar, pos.stop, cfg)
        exit_reason = "breakeven_stop" if pos.breakeven else "stop"
    elif hit_target:
        exit_price = trade.target
        exit_reason = "target"
    elif bars_held >= cfg.time_stop_bars:
        exit_price = float(bar["close"])
        exit_reason = "time_stop"

    if exit_price is None:
        if bar["close"] > trade.b_price and not pos.breakeven:
            # Armé au close : ne peut donc s'appliquer qu'aux barres suivantes.
            pos.stop = trade.entry_price
            pos.breakeven = True
            trade.moved_to_breakeven = True
        return equity, None

    exit_fee = cfg.maker_fee if exit_reason == "target" else cfg.taker_fee
    equity = _close_trade(
        trade, equity, i, ts, exit_price, exit_reason, bars_held, entry_fee, exit_fee, cfg
    )
    return equity, trade


def _stop_exec_price(bar: dict, stop: float, cfg: StrategyConfig) -> float:
    """Stop au marché : exécution au pire entre le stop et l'open, moins le slippage."""
    base = min(stop, float(bar["open"])) if bar["open"] < stop else stop
    return base * (1.0 - cfg.stop_slippage)


def _open_trade(
    pair: str,
    cfg: StrategyConfig,
    ts: pd.Timestamp,
    i: int,
    price: float,
    setup: Setup,
    rr: float,
    equity: float,
) -> Trade | None:
    risk_amount = equity * cfg.risk_per_trade
    stop_distance = price - setup.stop
    if stop_distance <= 0 or risk_amount <= 0:
        return None
    qty = risk_amount / stop_distance
    notional = qty * price
    max_notional = equity * MAX_LEVERAGE
    capped = notional > max_notional
    if capped:
        qty = max_notional / price
        notional = max_notional
        risk_amount = qty * stop_distance
    return Trade(
        pair=pair,
        variant=cfg.entry_variant,
        entry_time=ts,
        entry_index=i,
        entry_price=float(price),
        initial_stop=float(setup.stop),
        target=float(price + setup.leg),
        b_price=float(setup.b_price),
        a_price=float(setup.a_price),
        l1=float(setup.l1),
        l2=float(setup.l2),
        rr_planned=float(rr),
        qty=float(qty),
        risk_amount=float(risk_amount),
        notional=float(notional),
        size_capped=bool(capped),
    )


def _close_trade(
    trade: Trade,
    equity: float,
    i: int,
    ts: pd.Timestamp,
    exit_price: float,
    reason: str,
    bars_held: int,
    entry_fee: float,
    exit_fee: float,
    cfg: StrategyConfig,
) -> float:
    gross = trade.qty * (exit_price - trade.entry_price)
    fees = trade.notional * entry_fee + trade.qty * exit_price * exit_fee
    funding = trade.notional * cfg.funding_rate_8h * (bars_held / cfg.funding_interval_bars)
    net = gross - fees - funding
    trade.exit_time = ts
    trade.exit_index = i
    trade.exit_price = float(exit_price)
    trade.exit_reason = reason
    trade.bars_held = int(bars_held)
    trade.gross_pnl = float(gross)
    trade.fees = float(fees)
    trade.funding = float(funding)
    trade.net_pnl = float(net)
    trade.r_multiple = float(net / trade.risk_amount) if trade.risk_amount else 0.0
    equity += net
    trade.equity_after = float(equity)
    return equity
