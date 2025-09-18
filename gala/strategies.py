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
                    # Use a configurable amount to check for real liquidity
                    api.get_quote(t_in, t_out, config.LIQUIDITY_CHECK_AMOUNT, fee)
                    active_pools.append(ActivePool(t_in, t_out, fee))
                    print(f"  [ok] {t_in}-{t_out} (fee: {fee}) is active.")
                except Exception:
                    print(f"  [--] {t_in}-{t_out} (fee: {fee}) is inactive.")
                    continue
    print(f"Found {len(active_pools)} active pool-fee combinations.")

    # >>> Step 3 debug: show which triangle edge(s) are missing for GUSDC–GALA–GWETH
    def _has_edge(a: str, b: str, aps: List[ActivePool]) -> bool:
        return any(
            (p.token_a == a and p.token_b == b) or
            (p.token_a == b and p.token_b == a)
            for p in aps
        )

    _required = [('GUSDC', 'GALA'), ('GALA', 'GWETH'), ('GWETH', 'GUSDC')]
    _missing = [f"{a} ↔ {b}" for (a, b) in _required if not _has_edge(a, b, active_pools)]

    if _missing:
        print("🧩 Missing edge(s) for triangle:", ", ".join(_missing))
    else:
        print("✅ All three triangle edges are active — triangles should be possible now.")
    # <<< end debug

    return active_pools


def enumerate_triangles(active_pools: List[ActivePool]) -> List[Tuple[str, str, str]]:
    """
    Return directed triangles (a,b,c) meaning we will simulate a->b, b->c, c->a.
    Only include edges that are actually active in that direction.
    """
    # Build DIRECTED adjacency from the discovered active pools (direction matters!)
    adj: Dict[str, set] = {}
    for p in active_pools:
        adj.setdefault(p.token_a, set()).add(p.token_b)

    rotations: List[Tuple[str, str, str]] = []
    tokens = list(adj.keys())

    for a in tokens:
        for b in adj.get(a, ()):
            if b == a:
                continue
            for c in adj.get(b, ()):
                if c in (a, b):
                    continue
                # require closing edge c -> a to form a directed 3-cycle
                if a in adj.get(c, ()):
                    # return the three rotations so start_token alignment can work
                    rotations.extend([
                        (a, b, c),
                        (b, c, a),
                        (c, a, b),
                    ])

    # De-duplicate identical tuples that may appear due to multiple fees
    unique = list(dict.fromkeys(rotations))
    return unique


# -------- Quote helper with fallback/backoff ----------------------------------
def _best_quote_safe(api: GalaSwapAPI, t_in: str, t_out: str, amount: Decimal) -> Quote:
    """
    Try to get a quote. If the full amount fails, clamp to ARB_MAX_HOP_INPUT and back off.
    """
    try:
        from . import config
        max_in = Decimal(str(getattr(config, "MAX_HOP_INPUT", Decimal("0")) or Decimal("0")))
    except Exception:
        max_in = Decimal("0")

    amt0 = amount
    if max_in > 0 and amt0 > max_in:
        amt0 = max_in

    last_err = None
    for factor in [Decimal("1"), Decimal("0.5"), Decimal("0.2"), Decimal("0.1"), Decimal("0.05")]:
        amt_try = (amt0 * factor).quantize(Decimal("0.00000001"))
        try:
            return api.best_quote(t_in, t_out, amt_try)
        except Exception as e:
            last_err = e
    raise last_err  # type: ignore[misc]



def simulate_cycle(api: GalaSwapAPI, cycle: Tuple[str, str, str], start_token: str, amount: Decimal) -> CycleResult | None:
    a, b, c = cycle

    # If the start token isn't in this triangle, skip
    if start_token not in (a, b, c):
        return None

    # Rotate so the start_token comes first
    if start_token != a:
        seq = [a, b, c]
        i = seq.index(start_token)
        a, b, c = seq[i], seq[(i + 1) % 3], seq[(i + 2) % 3]

    hops: List[Hop] = []

    # --- DEBUGGED QUOTE SEQUENCE with fallback ---
    try:
        # Hop 1: a->b
        q1 = _best_quote_safe(api, a, b, amount)
        print(f"   ↪️  Hop1 {a}->{b} | in={q1.amount_in} | out={q1.amount_out} | fee={q1.fee_used}")
        if q1.amount_out <= 0:
            print(f"   ⚠️  Hop1 produced non-positive out; dropping cycle.")
            return None

        # Hop 2: b->c (use output of hop1)
        q2 = _best_quote_safe(api, b, c, q1.amount_out)
        print(f"   ↪️  Hop2 {b}->{c} | in={q2.amount_in} | out={q2.amount_out} | fee={q2.fee_used}")
        if q2.amount_out <= 0:
            print(f"   ⚠️  Hop2 produced non-positive out; dropping cycle.")
            return None

        # Hop 3: c->a (close the loop)
        q3 = _best_quote_safe(api, c, a, q2.amount_out)
        print(f"   ↪️  Hop3 {c}->{a} | in={q3.amount_in} | out={q3.amount_out} | fee={q3.fee_used}")
        if q3.amount_out <= 0:
            print(f"   ⚠️  Hop3 produced non-positive out; dropping cycle.")
            return None

    except Exception as e:
        print(f"   ❌ Quote error on cycle {a}->{b}->{c}->{a}: {e}")
        return None
    # --- END DEBUGGED QUOTE SEQUENCE ---

    hops.append(Hop(a, b, q1.fee_used or 0, q1.amount_in, q1.amount_out))
    hops.append(Hop(b, c, q2.fee_used or 0, q2.amount_in, q2.amount_out))
    hops.append(Hop(c, a, q3.fee_used or 0, q3.amount_in, q3.amount_out))

    final_amt = q3.amount_out
    gain = (final_amt - amount) / amount
    gross_bps = int(gain * Decimal(10_000))

    # DEBUG: print every simulated cycle and its profit in BPS
    print(f"🔎 Cycle {a}->{b}->{c}->{a} | in={amount} {a} | out={final_amt} {a} | gross={gross_bps} bps")

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

