# ==========================================
# file: main.py
# ==========================================
from decimal import Decimal
import sys
import time

import gala.config as config
from gala.gala_api import GalaSwapAPI
from gala.strategies import enumerate_triangles, simulate_cycle, prepare_payloads, discover_active_pools


BUNDLE_SWAP_TYPE_CANDIDATES = ["swap", "Swap"]


def main() -> int:
    if not config.USER_ADDRESS:
        print("[!] USER_ADDRESS missing (env GALA_USER_ADDR). Aborting.")
        return 2
    if not config.DRY_RUN and not config.PRIVATE_KEY_HEX:
        print("[!] PRIVATE_KEY_HEX missing (env GALA_PRIVATE_KEY). Aborting.")
        return 2

    api = GalaSwapAPI()

    scan_count = 0
    active_pools = []
    while True:
        print(f"\n--- Starting scan #{scan_count+1} ---")

        # 1) Find all active pools and fees, but only periodically
        if scan_count % config.POOL_REFRESH_INTERVAL == 0:
            active_pools = discover_active_pools(api, config.POOLS)
        
        if not active_pools:
            print("No active pools found; adjust config or check network.")
            scan_count += 1
            time.sleep(config.SCAN_INTERVAL_SECONDS)
            continue

        # 2) Build all triangles from active pools
        triangles = enumerate_triangles(active_pools)
        if not triangles:
            print("No triangles available from active pools; adjust config.")
            scan_count += 1
            time.sleep(config.SCAN_INTERVAL_SECONDS)
            continue

        # 3) Simulate each triangle starting from START_TOKEN
        best = None
        print(f"Simulating {len(triangles)} triangles...")
        for cyc in triangles[: config.MAX_CYCLES_PER_SCAN]:
            if cyc[0] != config.START_TOKEN:
                continue
            try:
                res = simulate_cycle(api, cyc, config.START_TOKEN, config.START_AMOUNT)
            except Exception as e:
                # This can be noisy, enable for debugging
                # print(f"[warn] Simulation failed for cycle {cyc}: {e}")
                continue
            if res is None:
                continue
            if best is None or res.gross_profit_bps > best.gross_profit_bps:
                best = res

        if best is None:
            print("No viable cycle simulations found in this scan.")
            scan_count += 1
            time.sleep(config.SCAN_INTERVAL_SECONDS)
            continue

        print(f"Best cycle {best.path[0].token_in}->{best.path[0].token_out}->{best.path[1].token_out}->{best.path[2].token_out}->{best.start_token} | "
              f"in={best.start_amount} out={best.final_amount} profit={best.gross_profit_bps} bps")

        threshold = config.MIN_PROFIT_BPS + config.PROFIT_BUFFER_BPS
        if best.gross_profit_bps < threshold:
            print(f"[skip] Not profitable enough: need >= {threshold} bps, got {best.gross_profit_bps} bps.")
            scan_count += 1
            time.sleep(config.SCAN_INTERVAL_SECONDS)
            continue

        # 4) Build payloads with slippage protection
        prepared = prepare_payloads(api, best, config.SLIPPAGE_BPS)

        # 5) Execute or dry-run
        if config.DRY_RUN:
            print("[dry-run] Would execute hops:")
            for i, hop in enumerate(prepared, 1):
                print(f"  Hop {i}: {hop.token_in}->{hop.token_out} fee={hop.fee} in={hop.quote_in} minOut≈{hop.quote_out*(Decimal(1)-Decimal(config.SLIPPAGE_BPS)/Decimal(10_000))}")
            scan_count += 1
            time.sleep(config.SCAN_INTERVAL_SECONDS)
            continue

        # Otherwise, sequentially submit each swap. NOTE: This is not atomic. Use at your own risk.
        tx_ids = []
        for i, hop in enumerate(prepared, 1):
            print(f"[exec] Submitting hop {i}: {hop.token_in}->{hop.token_out} amountIn={hop.quote_in} fee={hop.fee}")
            sig = api.sign_payload(hop.payload, config.PRIVATE_KEY_HEX)

            tx_id = None
            last_err = None
            for t in BUNDLE_SWAP_TYPE_CANDIDATES:
                try:
                    tx_id = api.send_bundle(hop.payload, t, sig, config.USER_ADDRESS)
                    break
                except Exception as e:
                    last_err = e
                    continue
            if tx_id is None:
                print(f"[error] bundle submission failed for hop {i}: {last_err}")
                # Decide if you want to stop the whole bot on a single failure
                break  # break from the hop loop
            print(f"  -> tx id: {tx_id}")
            tx_ids.append(tx_id)

            # Optional: poll status (basic)
            time.sleep(2)
            try:
                status = api.check_tx_status(tx_id)
                print(f"  -> status: {status.get('status')} method={status.get('method')}")
            except Exception as e:
                print(f"  -> status check error: {e}")

        print("All hops submitted for this cycle.")
        scan_count += 1
        time.sleep(config.SCAN_INTERVAL_SECONDS)

if __name__ == "__main__":
    sys.exit(main())