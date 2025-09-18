# ==============================================================================
# GalaDex Trading Bot Configuration
# ==============================================================================
# This is the main configuration file for your trading bot.
# You can change the bot's behavior by editing the values here.
# For any setting that uses `os.getenv(...)`, you can also set it as an
# environment variable in your system, which is a safer practice for secrets.
# ==============================================================================

from decimal import Decimal
import os

# ==============================================================================
# SECTION 1: NETWORK SETTINGS
# ==============================================================================
API_BASE_URL = os.getenv("GALA_API_BASE_URL", "https://dex-backend-test1.defi.gala.com")
BUNDLE_WS_URL = os.getenv("GALA_BUNDLE_WS_URL", "wss://bundle-backend-test1.defi.gala.com")

# ==============================================================================
# SECTION 2: WALLET AND SECURITY
# ==============================================================================
PRIVATE_KEY_HEX = os.getenv("GALA_PRIVATE_KEY", "")
USER_ADDRESS = os.getenv("GALA_USER_ADDR", "")

# ==============================================================================
# SECTION 3: TOKEN DEFINITIONS
# ==============================================================================
TOKEN_KEYS = {
    "GALA":  "GALA$Unit$none$none",
    "GUSDC": "GUSDC$Unit$none$none",
    "USDC":  "GUSDC$Unit$none$none",
    "GUSDT": "GUSDT$Unit$none$none",
    "USDT":  "GUSDT$Unit$none$none",
    "GWETH": "GWETH$Unit$none$none",
}

# ==============================================================================
# SECTION 4: TRADING POOLS
# ==============================================================================
POOLS = [
    ("GUSDC", "GALA"),
    ("GALA", "GWETH"),
    ("GWETH", "GUSDC"),
    ("GUSDT", "GWETH"),   # newly added pair
]

# ==============================================================================
# SECTION 5: FEE TIERS
# ==============================================================================
FALLBACK_FEE_TIERS = [500, 3000, 10000]

POOL_FEE_OVERRIDE = {
    # Prefer 1.00% (10000) for GALA ↔ GWETH since that’s the tier we’ve seen active
    ("GALA", "GWETH"): [10000],
    ("GWETH", "GALA"): [10000],

    # Force 1.00% tier for GWETH ↔ GUSDC so the bot probes this edge properly
    ("GWETH", "GUSDC"): [10000],
    ("GUSDC", "GWETH"): [10000],

    # Optional: if you want to scan GUSDT ↔ GWETH too, pin to 1.00%
    ("GUSDT", "GWETH"): [10000],
    ("GWETH", "GUSDT"): [10000],
}

# ==============================================================================
# SECTION 6: RISK MANAGEMENT
# ==============================================================================
SLIPPAGE_BPS = int(os.getenv("ARB_SLIPPAGE_BPS", "40"))  # 40 = 0.40%
MIN_PROFIT_BPS = int(os.getenv("ARB_MIN_PROFIT_BPS", "20"))  # 20 = 0.20%
PROFIT_BUFFER_BPS = int(os.getenv("ARB_PROFIT_BUFFER_BPS", "10"))  # 10 = 0.10%

# ==============================================================================
# SECTION 7: STRATEGY AND AMOUNTS
# ==============================================================================
START_TOKEN = os.getenv("ARB_START_TOKEN", "GUSDC")
START_AMOUNT = Decimal(os.getenv("ARB_START_AMOUNT", "100"))

# When probing pool “activeness”
LIQUIDITY_CHECK_AMOUNT = Decimal(os.getenv("ARB_LIQUIDITY_CHECK_AMOUNT", "0.1"))

# NEW: Max input size per hop (0 = no cap). Used by strategies.py to clamp quotes.
MAX_HOP_INPUT = Decimal(os.getenv("ARB_MAX_HOP_INPUT", "0"))

# ==============================================================================
# SECTION 8: PERFORMANCE AND EXECUTION
# ==============================================================================
DRY_RUN = os.getenv("ARB_DRY_RUN", "true").lower() in ("1", "true", "yes")
MAX_CYCLES_PER_SCAN = 12
HTTP_TIMEOUT = int(os.getenv("GALA_HTTP_TIMEOUT", "15"))
SCAN_INTERVAL_SECONDS = int(os.getenv("ARB_SCAN_INTERVAL_SECONDS", "15"))
POOL_REFRESH_INTERVAL = int(os.getenv("ARB_POOL_REFRESH_INTERVAL", "10"))
