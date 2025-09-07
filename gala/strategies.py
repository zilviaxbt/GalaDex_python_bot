# Trading strategies and logic for GalaSwap DEX bot.
# ==========================================
# file: strategies.py
# ==========================================
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Sequence, Tuple

from . import config
from .gala_api import GalaSwapAPI, Quote


@dataclass
class ActivePool:
    token_a: str
    token_b: str
    fee: int

    def __contains__(self, token: str):
        return token == self.token_a or token == self.token_b

    def get_other(self, token: str) -> str:
        if token == self.token_a:
            return self.token_b
        if token == self.token_b:
            return self.token_a
        raise ValueError(f"Token {token} not in pool")


@dataclass
class Hop:
    token_in: str
    token_out: str
    fee: int
    quote_in: Decimal
    quote_out: Decimal
    payload: dict | None = None


@dataclass
class CycleResult:
    path: List[Hop]
    start_token: str
    start_amount: Decimal
    final_amount: Decimal
    gross_profit_bps: int


def discover_active_pools(api: GalaSwapAPI, pools: Sequence[Tuple[str, str]]) -> List[ActivePool]:
    print("Discovering active pools and fee tiers...")
    active_pools = []
    seen_fees = set()

    for a, b in pools:
        # Check both directions A->B and B->A
        for t_in, t_out in [(a, b), (b, a)]:
            fees = config.POOL_FEE_OVERRIDE.get((t_in, t_out)) or \
                   config.POOL_FEE_OVERRIDE.get((t_out, t_in)) or \
                   config.FALLBACK_FEE_TIERS

            for fee in fees:
                # Avoid re-checking the same pool/fee combination (e.g. A/B fee 3000 vs B/A fee 3000)
                pool_key = tuple(sorted((t_in, t_out)))
                if (pool_key, fee) in seen_fees:
                    continue
                seen_fees.add((pool_key, fee))

                try:
                    # Use a configurable, larger amount to check for real liquidity
                    api.get_quote(t_in, t_out, config.LIQUIDITY_CHECK_AMOUNT, fee)
                    active_pools.append(ActivePool(t_in, t_out, fee))
                    print(f"  [ok] {t_in}-{t_out} (fee: {fee}) is active.")
                except Exception:
                    print(f"  [--] {t_in}-{t_out} (fee: {fee}) is inactive.")
                    continue
    print(f"Found {len(active_pools)} active pool-fee combinations.")
    return active_pools


def enumerate_triangles(active_pools: List[ActivePool]) -> List[Tuple[str, str, str]]:
    # Build adjacency list from active, directed pools
    adj: Dict[str, set] = {}
    for pool in active_pools:
        adj.setdefault(pool.token_a, set()).add(pool.token_b)
        adj.setdefault(pool.token_b, set()).add(pool.token_a)

    tokens = sorted(adj.keys())
    seen = set()
    cycles: List[Tuple[str, str, str]] = []
    for a in tokens:
        for b in adj.get(a, set()):
            for c in adj.get(b, set()):
                if c in adj and a in adj.get(c, set()) and a != b and b != c and a != c:
                    cyc = tuple(sorted((a, b, c)))
                    if cyc not in seen:
                        seen.add(cyc)
                        # Return the cycle starting with the token that is first alphabetically
                        # This is just a canonical representation.
                        cycles.append(cyc)
    return [c for c in cycles for c in [(c[0], c[1], c[2]), (c[0], c[2], c[1])]]


def simulate_cycle(api: GalaSwapAPI, cycle: Tuple[str, str, str], start_token: str, amount: Decimal) -> CycleResult | None:
    a, b, c = cycle
    if start_token != a:
        # This logic assumes we always start the cycle enumeration from the start_token
        # The new enumerate_triangles returns all rotations, so we just find the one starting with our token
        return None

    hops: List[Hop] = []

    # Hop 1: a->b
    q1 = api.best_quote(a, b, amount)
    # Hop 2: b->c (use output of hop1)
    q2 = api.best_quote(b, c, q1.amount_out)
    # Hop 3: c->a (close the loop)
    q3 = api.best_quote(c, a, q2.amount_out)

    hops.append(Hop(a, b, q1.fee_used or 0, q1.amount_in, q1.amount_out))
    hops.append(Hop(b, c, q2.fee_used or 0, q2.amount_in, q2.amount_out))
    hops.append(Hop(c, a, q3.fee_used or 0, q3.amount_in, q3.amount_out))

    final_amt = q3.amount_out
    gain = (final_amt - amount) / amount
    gross_bps = int(gain * Decimal(10_000))
    return CycleResult(path=hops, start_token=a, start_amount=amount, final_amount=final_amt, gross_profit_bps=gross_bps)


def prepare_payloads(api: GalaSwapAPI, res: CycleResult, slippage_bps: int) -> List[Hop]:
    prepared: List[Hop] = []
    for hop in res.path:
        payload = api.build_swap_payload(
            token_in_sym=hop.token_in,
            token_out_sym=hop.token_out,
            amount_in=hop.quote_in,
            quoted_out=hop.quote_out,
            fee=hop.fee,
            slippage_bps=slippage_bps,
        )
        prepared.append(Hop(
            token_in=hop.token_in,
            token_out=hop.token_out,
            fee=hop.fee,
            quote_in=hop.quote_in,
            quote_out=hop.quote_out,
            payload=payload,
        ))
    return prepared