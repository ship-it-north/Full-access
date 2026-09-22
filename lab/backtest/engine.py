"""Moteur de backtest : orchestration simplifiée Phase D."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

import pandas as pd

from lab.core.costs import commission, convert, to_cad
from lab.core.portfolio import Portfolio
from lab.core.risk import RiskState, size_position
from lab.strategies.base import Context, Strategy, OrderType


@dataclass(frozen=True)
class Trade:
    """Un trade complètement exécuté (entrée + sortie)."""
    symbol: str
    entry_date: pd.Timestamp
    entry_price: float
    entry_reason: str
    shares: float
    stop: float
    exit_date: pd.Timestamp
    exit_price: float
    exit_reason: str
    pnl_local: float  # en devise locale
    pnl_cad: float
    risk_cad: float
    commission_round_trip: float
    risk_used: float  # % du plafond 5$ utilisé


@dataclass
class BacktestContext:
    """État du backtest à chaque pas de temps."""
    current_date: pd.Timestamp
    bar: pd.DataFrame  # historique jusquà current_date pour le symbole actuel
    portfolio: Portfolio
    risk_state: RiskState
    usd_per_cad: float
    fx_converted: bool = False
    initial_cash: float = 200.0  # CAD


@dataclass
class BacktestResult:
    """Résultats d'un backtest."""
    strategy_name: str
    timeframe: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    trades: list[Trade] = field(default_factory=list)
    final_equity_cad: float = 0.0
    total_pnl_cad: float = 0.0
    num_trades: int = 0
    num_winning: int = 0
    num_losing: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    max_drawdown_pct: float = 0.0


def _is_market_hours(timestamp: pd.Timestamp, timeframe: str) -> bool:
    """
    Vérifier si un timestamp est dans les heures de marché (9h30-16h00 ET).

    Args:
        timestamp: timestamp potentiellement timezone-aware
        timeframe: "1d" ou "5m"

    Returns:
        True si la barre est dans les heures de marché
    """
    # Convertir vers ET si nécessaire
    if timestamp.tz is not None:
        ts_et = timestamp.tz_convert("America/New_York")
    else:
        # Suppose UTC par défaut si pas de tz
        ts_et = timestamp.tz_localize("UTC").tz_convert("America/New_York")

    hour = ts_et.hour
    minute = ts_et.minute

    if timeframe == "1d":
        # Daily bars should be at/after 16:00 ET (market close)
        return (hour > 16) or (hour == 16 and minute >= 0)
    elif timeframe == "5m":
        # 5-min bars: 9:30-16:00 ET
        start_ok = (hour > 9) or (hour == 9 and minute >= 30)
        end_ok = (hour < 16) or (hour == 16 and minute == 0)
        return start_ok and end_ok
    else:
        return True


class BacktestEngine:
    """Moteur de backtest simplifié pour Phase D."""

    def __init__(self, strategy: Strategy,
                 data: dict[str, pd.DataFrame],
                 usd_per_cad: float = 1.35,
                 initial_equity_cad: float = 200.0,
                 commission_profile: str = "tiered",
                 fractional: bool = False):
        """
        Args:
            strategy: instance Strategy
            data: dict symbol -> DataFrame (OHLCV)
            usd_per_cad: taux de change
            initial_equity_cad: capital initial en CAD
            commission_profile: "tiered" ou "fixed"
            fractional: actions fractionnées disponibles
        """
        self.strategy = strategy
        self.data = data
        self.usd_per_cad = usd_per_cad
        self.initial_equity_cad = initial_equity_cad
        self.commission_profile = commission_profile
        self.fractional = fractional

    def run(self) -> BacktestResult:
        """Exécuter le backtest complet."""
        result = BacktestResult(
            strategy_name=self.strategy.__class__.__name__,
            timeframe=self.strategy.timeframe,
            start_date=None,
            end_date=None,
        )

        if not self.data:
            return result

        # Convertir CAD en USD une seule fois
        fx_conv = convert(self.initial_equity_cad, self.usd_per_cad)
        cash_usd = fx_conv.amount_target
        portfolio = Portfolio(
            cash_settled=cash_usd,
            usd_per_cad=self.usd_per_cad,
            currency="USD"
        )
        risk_state = RiskState()

        # Déterminer les dates globales (filtrées par heures de marché)
        all_dates = []
        for df in self.data.values():
            for idx in df.index:
                if _is_market_hours(idx, self.strategy.timeframe):
                    all_dates.append(idx)

        all_dates = sorted(set(all_dates))

        if not all_dates:
            return result

        result.start_date = all_dates[0]
        result.end_date = all_dates[-1]

        # État des positions ouvertes
        open_positions = {}  # symbol -> position_data

        # Traiter chaque date
        for date_idx, date in enumerate(all_dates):
            # Libérer les produits de vente réglés
            portfolio.release_settled(date)

            # Vérifier les sorties des positions existantes
            symbols_to_check = list(open_positions.keys())
            for symbol in symbols_to_check:
                pos = open_positions[symbol]
                df = self.data[symbol]

                if date not in df.index:
                    continue

                current_bar = df.loc[date]

                # Vérifier stop
                if current_bar['low'] <= pos['stop']:
                    exit_price = min(current_bar['open'], pos['stop'])

                    pnl_local = (exit_price - pos['entry_price']) * pos['shares']
                    pnl_cad = pnl_local * (1 / self.usd_per_cad)

                    trade = Trade(
                        symbol=symbol,
                        entry_date=pos['entry_date'],
                        entry_price=pos['entry_price'],
                        entry_reason=pos['entry_reason'],
                        shares=pos['shares'],
                        stop=pos['stop'],
                        exit_date=date,
                        exit_price=exit_price,
                        exit_reason="stop",
                        pnl_local=pnl_local,
                        pnl_cad=pnl_cad,
                        risk_cad=pos['risk_cad'],
                        commission_round_trip=0.0,
                        risk_used=pos['risk_used']
                    )

                    result.trades.append(trade)
                    portfolio.sell(symbol, pos['shares'], exit_price, date)
                    risk_state.on_close(pnl_cad)
                    del open_positions[symbol]
                    continue

                # Vérifier target
                if pos['target'] is not None and current_bar['high'] >= pos['target']:
                    exit_price = max(current_bar['open'], pos['target'])

                    pnl_local = (exit_price - pos['entry_price']) * pos['shares']
                    pnl_cad = pnl_local * (1 / self.usd_per_cad)

                    trade = Trade(
                        symbol=symbol,
                        entry_date=pos['entry_date'],
                        entry_price=pos['entry_price'],
                        entry_reason=pos['entry_reason'],
                        shares=pos['shares'],
                        stop=pos['stop'],
                        exit_date=date,
                        exit_price=exit_price,
                        exit_reason="target",
                        pnl_local=pnl_local,
                        pnl_cad=pnl_cad,
                        risk_cad=pos['risk_cad'],
                        commission_round_trip=0.0,
                        risk_used=pos['risk_used']
                    )

                    result.trades.append(trade)
                    portfolio.sell(symbol, pos['shares'], exit_price, date)
                    risk_state.on_close(pnl_cad)
                    del open_positions[symbol]
                    continue

                # Vérifier sortie temporelle
                bars_held = date_idx - pos['entry_idx']
                if pos['max_bars'] is not None and bars_held >= pos['max_bars']:
                    exit_price = current_bar['close']

                    pnl_local = (exit_price - pos['entry_price']) * pos['shares']
                    pnl_cad = pnl_local * (1 / self.usd_per_cad)

                    trade = Trade(
                        symbol=symbol,
                        entry_date=pos['entry_date'],
                        entry_price=pos['entry_price'],
                        entry_reason=pos['entry_reason'],
                        shares=pos['shares'],
                        stop=pos['stop'],
                        exit_date=date,
                        exit_price=exit_price,
                        exit_reason="timeout",
                        pnl_local=pnl_local,
                        pnl_cad=pnl_cad,
                        risk_cad=pos['risk_cad'],
                        commission_round_trip=0.0,
                        risk_used=pos['risk_used']
                    )

                    result.trades.append(trade)
                    portfolio.sell(symbol, pos['shares'], exit_price, date)
                    risk_state.on_close(pnl_cad)
                    del open_positions[symbol]

            # Parcourir les symboles de l'univers pour les nouveaux signaux
            for symbol in self.data:
                if symbol in open_positions:
                    continue  # Déjà en position

                df = self.data[symbol]
                if date not in df.index:
                    continue

                # Construire l'historique jusqu'à cette date
                history = df[:date]
                if len(history) == 0:
                    continue

                # Vérifier éligibilité
                if not self.strategy.universe_filter(symbol, history):
                    continue

                # Créer le contexte
                ctx = Context(
                    symbol=symbol,
                    timeframe=self.strategy.timeframe,
                    bar=history.iloc[-1],
                    history=history,
                    usd_per_cad=self.usd_per_cad,
                    fractional=self.fractional,
                )

                # Demander un signal
                signal = self.strategy.on_bar_close(ctx)
                if signal is None:
                    continue

                # Vérifier limites de risque
                if risk_state.paused:
                    continue

                # Déterminer le prix d'entrée
                if signal.order_type == OrderType.MARKET:
                    entry_price = df.loc[date, 'open']
                else:
                    entry_price = signal.limit_price if signal.limit_price else df.loc[date, 'close']

                # Calculer la cible selon la règle de sortie
                target = None
                max_bars = signal.expiration_bars

                if signal.exit_rule.value == "target":
                    # exit_param est le multiplicateur de R (risque)
                    risk_per_share = entry_price - signal.stop
                    if risk_per_share > 0 and signal.exit_param:
                        target = entry_price + (risk_per_share * signal.exit_param)
                elif signal.exit_rule.value == "time_based":
                    # max_bars détermine la sortie
                    max_bars = signal.exit_param if isinstance(signal.exit_param, int) else signal.expiration_bars

                # Dimensionner la position
                sizing = size_position(
                    entry=entry_price,
                    stop=signal.stop,
                    symbol=symbol,
                    cash_local=portfolio.cash_settled,
                    usd_per_cad=self.usd_per_cad,
                    plan=self.commission_profile,
                    fractional=self.fractional
                )

                if sizing.shares <= 0:
                    continue

                # Débiter le portefeuille
                try:
                    portfolio.buy(symbol, sizing.shares, entry_price, date)
                except ValueError:
                    continue

                # Enregistrer la position
                open_positions[symbol] = {
                    'entry_date': date,
                    'entry_idx': date_idx,
                    'entry_price': entry_price,
                    'entry_reason': signal.reason,
                    'shares': sizing.shares,
                    'stop': signal.stop,
                    'target': target,
                    'max_bars': max_bars,
                    'risk_cad': sizing.risk_cad,
                    'risk_used': sizing.risk_cad / 5.0,
                    'currency': 'USD'
                }

        # Fermer les positions restantes à la fin
        if all_dates:
            final_date = all_dates[-1]
            for symbol in list(open_positions.keys()):
                pos = open_positions[symbol]
                df = self.data[symbol]
                if final_date in df.index:
                    final_price = df.loc[final_date, 'close']
                    pnl_local = (final_price - pos['entry_price']) * pos['shares']
                    pnl_cad = pnl_local * (1 / self.usd_per_cad)

                    trade = Trade(
                        symbol=symbol,
                        entry_date=pos['entry_date'],
                        entry_price=pos['entry_price'],
                        entry_reason=pos['entry_reason'],
                        shares=pos['shares'],
                        stop=pos['stop'],
                        exit_date=final_date,
                        exit_price=final_price,
                        exit_reason="end_of_backtest",
                        pnl_local=pnl_local,
                        pnl_cad=pnl_cad,
                        risk_cad=pos['risk_cad'],
                        commission_round_trip=0.0,
                        risk_used=pos['risk_used']
                    )

                    result.trades.append(trade)
                    portfolio.sell(symbol, pos['shares'], final_price, final_date)
                    risk_state.on_close(pnl_cad)

        # Calculer les métriques finales
        if result.trades:
            pnls = [t.pnl_cad for t in result.trades]
            result.num_trades = len(result.trades)
            result.num_winning = sum(1 for p in pnls if p > 0)
            result.num_losing = sum(1 for p in pnls if p <= 0)
            result.win_rate = result.num_winning / result.num_trades if result.num_trades > 0 else 0

            gross_wins = sum(p for p in pnls if p > 0)
            gross_losses = abs(sum(p for p in pnls if p < 0))
            result.profit_factor = gross_wins / gross_losses if gross_losses > 0 else float('inf') if gross_wins > 0 else 0

            result.largest_win = max(pnls) if pnls else 0
            result.largest_loss = min(pnls) if pnls else 0

            # Drawdown calculation
            equity_curve = np.cumsum([0] + pnls)
            running_max = np.maximum.accumulate(equity_curve)
            drawdown = equity_curve - running_max
            result.max_drawdown_pct = min(drawdown) / max(abs(min(equity_curve)), 1) if min(drawdown) < 0 else 0

        result.final_equity_cad = portfolio.equity_cad()
        result.total_pnl_cad = result.final_equity_cad - self.initial_equity_cad

        return result
