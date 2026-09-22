"""Frais IBKR : commissions, frais tiers et conversion de devises.

Toutes les grilles ci-dessous ont été relevées sur le site d'IBKR le
2026-09-22 (voir `reports/phase_b_couts.md` pour les extraits et les URL).
Le brief interdit de se fier aux chiffres qu'il cite lui-même : ce sont ces
valeurs relevées qui font foi.

Ordre d'application d'une commission, conforme aux exemples publiés par IBKR
(« 1 000 actions à 0,25 $ = 2,50 $ » sous Fixed : 1 000 × 0,005 = 5,00 $,
ramené au plafond de 1 % de 250 $) :
    commission = min( max(par_action × actions, minimum_par_ordre),
                      plafond_pourcentage × valeur )
"""

from __future__ import annotations

from dataclasses import dataclass

# Date du relevé des grilles. À rafraîchir si les tarifs changent.
GRID_AS_OF = "2026-09-22"
SOURCES = {
    "US": "https://www.interactivebrokers.com/en/pricing/commissions-stocks.php",
    "CA": "https://www.interactivebrokers.ca/en/pricing/commissions-stocks.php",
    "FX": "https://www.interactivebrokers.ca/en/pricing/commissions-spot-currencies.php",
}


@dataclass(frozen=True)
class Grid:
    per_share: float
    min_per_order: float
    max_pct_of_value: float
    currency: str


# Premier palier de volume mensuel (≤ 300 000 actions) : le seul atteignable ici.
GRIDS: dict[tuple[str, str], Grid] = {
    ("US", "tiered"): Grid(0.0035, 0.35, 0.01, "USD"),
    ("US", "fixed"): Grid(0.0050, 1.00, 0.01, "USD"),
    ("CA", "tiered"): Grid(0.0080, 1.00, 0.005, "CAD"),
    ("CA", "fixed"): Grid(0.0100, 1.00, 0.005, "CAD"),
}

# Frais tiers, répercutés sur le profil Tiered uniquement (Fixed les absorbe).
US_SEC_FEE_RATE = 0.0000206      # sur la valeur, à la vente seulement
US_FINRA_TAF_PER_SHARE = 0.000195  # à la vente seulement
US_FINRA_TAF_CAP = 8.30
US_CAT_PER_SHARE = 0.000003      # achat et vente
CA_CLEARING_PER_SHARE = 0.00017
CA_CLEARING_CAP = 2.00
CA_REG_PER_SHARE = 0.00011
CA_REG_CAP = 3.30
# Retrait de liquidité : variable selon la place, de l'ordre de 0,003 $/action.
# Négligeable ici (quelques actions) face au minimum par ordre, mais modélisé.
EXCHANGE_REMOVE_PER_SHARE = 0.0030

# Actions fractionnées : « the greater of 1% of the trade value or USD 0.01 ».
FRACTIONAL_PCT = 0.01
FRACTIONAL_MIN = 0.01

# Conversion de devises (IDEALPRO), palier I.
FX_COMMISSION_BPS = 0.20
FX_MIN_PER_ORDER_USD = 2.00


def venue_of(symbol: str) -> str:
    return "CA" if symbol.endswith(".TO") else "US"


def commission(
    shares: float,
    price: float,
    symbol: str,
    plan: str = "tiered",
    side: str = "buy",
    fractional: bool = False,
    include_third_party: bool | None = None,
) -> float:
    """Commission d'un ordre, dans la devise de la place (USD pour les É.-U.)."""
    if shares <= 0 or price <= 0:
        return 0.0
    venue = venue_of(symbol)
    grid = GRIDS[(venue, plan)]
    value = shares * price

    if fractional:
        # Règle publiée : le plus grand entre 1 % de la valeur et 0,01 $.
        base = max(FRACTIONAL_PCT * value, FRACTIONAL_MIN)
    else:
        base = max(grid.per_share * shares, grid.min_per_order)
        base = min(base, grid.max_pct_of_value * value)

    if include_third_party is None:
        include_third_party = plan == "tiered"
    if include_third_party:
        base += third_party_fees(shares, price, symbol, side)
    return base


def third_party_fees(shares: float, price: float, symbol: str, side: str) -> float:
    """Frais réglementaires, de compensation et de place, répercutés par IBKR."""
    value = shares * price
    fees = EXCHANGE_REMOVE_PER_SHARE * shares
    if venue_of(symbol) == "US":
        fees += US_CAT_PER_SHARE * shares
        if side == "sell":
            fees += US_SEC_FEE_RATE * value
            fees += min(US_FINRA_TAF_PER_SHARE * shares, US_FINRA_TAF_CAP)
    else:
        fees += min(CA_CLEARING_PER_SHARE * shares, CA_CLEARING_CAP)
        fees += min(CA_REG_PER_SHARE * shares, CA_REG_CAP)
    return fees


def round_trip_cost(shares: float, entry: float, exit_price: float, symbol: str,
                    plan: str = "tiered", fractional: bool = False) -> float:
    """Commissions aller-retour, dans la devise de la place."""
    return (commission(shares, entry, symbol, plan, "buy", fractional)
            + commission(shares, exit_price, symbol, plan, "sell", fractional))


@dataclass(frozen=True)
class FxConversion:
    amount_source: float
    amount_target: float
    commission_usd: float
    rate: float


def convert(amount_cad: float, usd_per_cad: float) -> FxConversion:
    """Conversion CAD -> USD, une seule fois, minimum IBKR compris.

    Le minimum de 2 $ US par ordre pèse lourd sur un compte de 200 $ : c'est
    1 % du capital, payé d'un coup avant le premier trade.
    """
    value_usd = amount_cad * usd_per_cad
    fee = max(FX_COMMISSION_BPS / 10_000 * value_usd, FX_MIN_PER_ORDER_USD)
    return FxConversion(
        amount_source=amount_cad,
        amount_target=value_usd - fee,
        commission_usd=fee,
        rate=usd_per_cad,
    )


def to_cad(amount: float, currency: str, usd_per_cad: float) -> float:
    if currency == "CAD":
        return amount
    return amount / usd_per_cad
