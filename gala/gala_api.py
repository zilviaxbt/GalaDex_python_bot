# gala_api.py
from __future__ import annotations
import json
from dataclasses import dataclass
from decimal import Decimal, getcontext
getcontext().prec = 40  # high precision for chained quotes
from typing import Dict, List, Optional, Tuple
import time
from . import config
import requests

from eth_hash.auto import keccak as keccak256  # keccak-256 (Ethereum) via eth-hash
from eth_keys import keys


def _ckey_obj(ckey: str) -> Dict[str, str]:
    """ "GALA$Unit$none$none" -> {"value": "GALA", ...} """
    parts = ckey.split("$")
    return {"value": parts[0], "type": parts[1], "collection": parts[2], "category": parts[3]}


@dataclass
class Quote:
    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out: Decimal
    fee_used: Optional[int]


class GalaSwapAPI:
    def __init__(self, base_url: str | None = None, session: Optional[requests.Session] = None):
        self.base_url = base_url or config.API_BASE_URL
        self.session = session or requests.Session()

    # ---- Helpers ----
    def _ckey(self, symbol: str) -> str:
        try:
            return config.TOKEN_KEYS[symbol]
        except KeyError:
            raise KeyError(f"No composite key configured for token symbol '{symbol}'. Add it to TOKEN_KEYS.")

    def _fees_for_pair(self, a: str, b: str) -> List[int]:
        key = (a, b)
        rkey = (b, a)
        return config.POOL_FEE_OVERRIDE.get(key) or config.POOL_FEE_OVERRIDE.get(rkey) or config.FALLBACK_FEE_TIERS

    # ---- Quotes ----
    def get_quote(self, token_in_sym: str, token_out_sym: str, amount_in: Decimal, fee: Optional[int] = None) -> Quote:
        """
        Fetches a single quote for a given pair, amount, and fee.
        Raises HTTPError on API error (e.g. no liquidity).
        """
        params = {
            "tokenIn": self._ckey(token_in_sym),
            "tokenOut": self._ckey(token_out_sym),
            "amountIn": str(amount_in),
        }
        if fee is not None:
            params["fee"] = fee
        url = f"{self.base_url}/v1/trade/quote"
        r = self.session.get(url, params=params, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        j = r.json()
        data = j.get("data") or {}
        amount_out = Decimal(str(data.get("amountOut", "0")))
        fee_used = data.get("fee") if data.get("fee") is not None else fee

        if amount_out == 0:
            raise ValueError("Quote returned zero amount out, indicating no liquidity.")

        return Quote(token_in_sym, token_out_sym, Decimal(str(amount_in)), amount_out, fee_used)

    def best_quote(self, token_in_sym: str, token_out_sym: str, amount_in: Decimal) -> Quote:
        best: Optional[Quote] = None
        for f in self._fees_for_pair(token_in_sym, token_out_sym):
            try:
                q = self.get_quote(token_in_sym, token_out_sym, amount_in, fee=f)
                if best is None or q.amount_out > best.amount_out:
                    best = q
            except (requests.HTTPError, ValueError):
                continue
        if best is None:
            raise RuntimeError(f"No quote available for {token_in_sym}->{token_out_sym}")
        return best

    # ---- Swap payloads ----
    def build_swap_payload(
        self,
        token_in_sym: str,
        token_out_sym: str,
        amount_in: Decimal,
        quoted_out: Decimal,
        fee: int,
        slippage_bps: int,
    ) -> dict:
        # slippage protections
        out_min = quoted_out * (Decimal(1) - Decimal(slippage_bps) / Decimal(10_000))
        in_max = amount_in * (Decimal(1) + Decimal(slippage_bps) / Decimal(10_000))

        body = {
            "tokenIn": _ckey_obj(self._ckey(token_in_sym)),
            "tokenOut": _ckey_obj(self._ckey(token_out_sym)),
            "amountIn": str(amount_in),
            # Provide amountOutMinimum for protection; also provide amountOut echo for compatibility
            "amountOut": str(quoted_out),
            "fee": fee,
            "sqrtPriceLimit": "0",  # no explicit price limit
            "amountInMaximum": str(in_max),
            "amountOutMinimum": str(out_min),
        }

        url = f"{self.base_url}/v1/trade/swap"
        r = self.session.post(url, json=body, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        j = r.json()
        data = j.get("data") or {}
        # API returns a payload with a uniqueKey to sign
        return data

    # ---- Signing & bundle submission ----
    def sign_payload(self, payload: dict, private_key_hex: str) -> str:
        if not private_key_hex:
            raise ValueError("PRIVATE_KEY_HEX is empty. Set GALA_PRIVATE_KEY.")

        # strip any transient fields and encode deterministically
        sanitized = dict(payload)
        sanitized.pop("signature", None)
        sanitized.pop("trace", None)

        encoded = json.dumps(sanitized, sort_keys=True, separators=(",", ":")).encode()
        digest = keccak256(encoded)  # 32-byte keccak-256

        key_bytes = bytes.fromhex(private_key_hex.replace("0x", ""))
        priv = keys.PrivateKey(key_bytes)
        sig = priv.sign_msg_hash(digest)  # r, s ints; v in {27, 28}

        r = sig.r.to_bytes(32, "big")
        s = sig.s.to_bytes(32, "big")
        v = bytes([sig.v])

        return (r + s + v).hex()


    def send_bundle(self, payload: dict, op_type: str, signature_hex: str, user: str) -> str:
        url = f"{self.base_url}/v1/trade/bundle"
        body = {
            "payload": payload,
            "type": op_type,   # try "swap" first (configurable at call-site)
            "signature": signature_hex,
            "user": user,
        }
        r = self.session.post(url, json=body, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        j = r.json()
        return (j.get("data") or {}).get("data", "")  # transaction id

    def check_tx_status(self, tx_id: str) -> dict:
        url = f"{self.base_url}/v1/trade/transaction-status"
        r = self.session.get(url, params={"id": tx_id}, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json().get("data") or {}


def _ckey_obj(composite_key: str) -> dict:
    # "GALA$Unit$none$none" => {collection, category, type, additionalKey}
    parts = composite_key.split("$")
    if len(parts) != 4:
        raise ValueError(f"Unexpected composite key format: {composite_key}")
    return {
        "collection": parts[0],
        "category": parts[1],
        "type": parts[2],
        "additionalKey": parts[3],
    }

