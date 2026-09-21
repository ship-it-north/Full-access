"""Sélection de l'univers tradable avec 200 $ CAD.

La sélection est faite par le code, pas à la main : liquidité, prix, et
capacité à porter un risque de 2 à 4 $ sans dépasser le plafond de 5 $ frais
inclus. Le brief laisse la décision finale à ces critères.
"""

from __future__ import annotations

import pandas as pd

from . import config as C

# Taux de change utilisé pour juger l'éligibilité. Approximatif et assumé comme
# tel : la conversion réelle, unique et datée, est un sujet de la phase B.
USD_PER_CAD_HINT = 0.73


def affordability(data: dict[str, pd.DataFrame], cash_cad: float = C.STARTING_CASH_CAD,
                  fx_usd_per_cad: float = USD_PER_CAD_HINT) -> pd.DataFrame:
    """Combien d'actions entières 200 $ CAD permettent d'acheter, et à quel risque.

    `risque_min_2pct` : la perte en $ CAD si le stop est à 2 % du prix d'entrée,
    pour la plus petite position possible (1 action). Si ce montant dépasse déjà
    le plafond de 5 $, le symbole n'est pas tradable en actions entières.
    """
    rows = []
    for symbol, df in data.items():
        if df.empty:
            continue
        last = float(df["close"].iloc[-1])
        currency = C.CURRENCY.get(symbol, "USD")
        price_cad = last if currency == "CAD" else last / fx_usd_per_cad
        shares = int(cash_cad // price_cad)
        dollar_volume = float((df["close"] * df["volume"]).tail(60).median())
        rows.append({
            "symbole": symbol,
            "devise": currency,
            "prix": round(last, 2),
            "prix_cad": round(price_cad, 2),
            "actions_pour_200cad": shares,
            "risque_1action_stop2pct_cad": round(price_cad * 0.02, 2),
            "volume_dollar_median_60j": round(dollar_volume),
            "liquide": dollar_volume >= C.MIN_DAILY_DOLLAR_VOLUME,
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["fractionnement_requis"] = out["actions_pour_200cad"] < 1
    # Avec 1 action, un stop à 2 % coûte moins que le plafond de 5 $ ?
    out["tradable_actions_entieres"] = (
        (out["actions_pour_200cad"] >= 1)
        & (out["risque_1action_stop2pct_cad"] <= 5.0)
        & out["liquide"]
    )
    return out.sort_values(["tradable_actions_entieres", "symbole"], ascending=[False, True])


def selected(affordability_table: pd.DataFrame) -> list[str]:
    if affordability_table.empty:
        return []
    return affordability_table.loc[
        affordability_table["tradable_actions_entieres"], "symbole"
    ].tolist()
