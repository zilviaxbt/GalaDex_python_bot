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
# These URLs point to the GalaSwap Decentralized Exchange (DEX) API.
# The bot uses these to get price quotes and send trades.
# You generally should not need to change these unless instructed to.
# ------------------------------------------------------------------------------
API_BASE_URL = os.getenv("GALA_API_BASE_URL", "https://dex-backend-test1.defi.gala.com")
BUNDLE_WS_URL = os.getenv("GALA_BUNDLE_WS_URL", "wss://bundle-backend-test1.defi.gala.com")


# ==============================================================================
# SECTION 2: WALLET AND SECURITY
# ==============================================================================
# These are your personal wallet details. This is the most sensitive part
# of the configuration.
#
# IMPORTANT: NEVER share your private key with anyone or commit it to a public
# GitHub repository. Anyone with your private key has full control of your funds.
# The safest way to use this is by setting it as an environment variable.
# ------------------------------------------------------------------------------

# Your private key is like the password to your bank account.
# It should start with "0x".
# Example: PRIVATE_KEY_HEX = "0xAbc123..."
PRIVATE_KEY_HEX = os.getenv("GALA_PRIVATE_KEY", "")

# Your public wallet address on the GalaChain.
# This is like your bank account number; it's safe to share.
# It should start with "eth|".
# Example: USER_ADDRESS = "eth|0x123abc..."
USER_ADDRESS = os.getenv("GALA_USER_ADDR", "")


# ==============================================================================
# SECTION 3: TOKEN DEFINITIONS
# ==============================================================================
# Here, we give simple names (like "GALA" or "GUSDC") to the complex, full
# token identifiers used by the GalaChain API.
# You can add more tokens here if you want the bot to trade them.
# ------------------------------------------------------------------------------
TOKEN_KEYS = {
    # Simple Name: "Full API Identifier"
    "GALA":  "GALA$Unit$none$none",
    "GUSDC": "GUSDC$Unit$none$none",
    "USDC":  "GUSDC$Unit$none$none",  # "USDC" is an alias, or nickname, for GUSDC
    "GUSDT": "GUSDT$Unit$none$none",
    "USDT":  "GUSDT$Unit$none$none",  # "USDT" is an alias for GUSDT
    "GWETH": "GWETH$Unit$none$none",
}


# ==============================================================================
# SECTION 4: TRADING POOLS
# ==============================================================================
# This list defines the trading pairs the bot will look at.
# A "pool" is a pair of tokens you can swap between, like GALA and GUSDC.
# The bot will try to find arbitrage opportunities (like GALA -> GUSDC -> GWETH -> GALA)
# using the pairs you list here.
#
# To add a new pair, add a new line like: `("TOKEN_A", "TOKEN_B"),`
# Use the "Simple Names" you defined in the TOKEN_KEYS section above.
# ------------------------------------------------------------------------------
POOLS = [
    ("GUSDC", "GALA"),
    ("GUSDT", "GALA"),
    ("GALA",  "GWETH"),
    ("GWETH", "GUSDC"),
]


# ==============================================================================
# SECTION 5: FEE TIERS
# ==============================================================================
# On a DEX, every trade has a small fee. Some pools have different fee "tiers"
# (e.g., 0.05%, 0.30%, 1.00%). The bot needs to check the right fee tier to get
# the correct price.
#
# `FALLBACK_FEE_TIERS` is the default list of fees the bot will check for each pool.
# The numbers are in "hundredths of a bip". 500 means 0.05%, 3000 means 0.30%.
# You can also specify exact fees for a specific pool using `POOL_FEE_OVERRIDE`.
# ------------------------------------------------------------------------------
FALLBACK_FEE_TIERS = [500, 3000, 10000]

# Use this if you know a specific pool only uses one fee tier. This can speed
# up the bot by reducing the number of checks it has to do.
# Example: To tell the bot that the GUSDC/GALA pool only uses the 0.30% fee:
# POOL_FEE_OVERRIDE = {
#     ("GUSDC", "GALA"): [3000],
# }
POOL_FEE_OVERRIDE = {}


# ==============================================================================
# SECTION 6: RISK MANAGEMENT
# ==============================================================================
# These settings are your safety controls. They help protect you from losing
# money due to rapid price changes or making unprofitable trades.
# ------------------------------------------------------------------------------

# `SLIPPAGE` is the price change you are willing to tolerate between the moment
# you submit a trade and the moment it is confirmed on the blockchain.
# A value of 40 means you accept a price change of up to 0.40%.
# Higher values increase the chance of your trade succeeding in a volatile
# market, but also increase the risk of getting a worse price.
SLIPPAGE_BPS = int(os.getenv("ARB_SLIPPAGE_BPS", "40")) # 40 = 0.40%

# The minimum profit required for the bot to even consider making a trade.
# The profit is calculated in "basis points" (bps), where 100 bps = 1%.
# A value of 20 means the bot will only execute a trade if it expects to make
# at least 0.20% gross profit.
MIN_PROFIT_BPS = int(os.getenv("ARB_MIN_PROFIT_BPS", "20")) # 20 = 0.20%

# An extra safety buffer. The bot will only trade if the expected profit is
# greater than `MIN_PROFIT_BPS` + `PROFIT_BUFFER_BPS`.
# This helps cover network fees or unexpected price movements.
PROFIT_BUFFER_BPS = int(os.getenv("ARB_PROFIT_BUFFER_BPS", "10")) # 10 = 0.10%


# ==============================================================================
# SECTION 7: STRATEGY AND AMOUNTS
# ==============================================================================
# These settings define the core of the arbitrage strategy.
# ------------------------------------------------------------------------------

# The token the bot will start and end with for its arbitrage cycles.
# For example, if you set this to "GUSDC", the bot will look for trades like
# GUSDC -> GALA -> GWETH -> GUSDC.
START_TOKEN = os.getenv("ARB_START_TOKEN", "GUSDC")

# The amount of `START_TOKEN` the bot will use for each trade attempt.
# The bot will simulate trades with this amount to find opportunities.
# If `DRY_RUN` is false, this is the actual amount it will trade.
START_AMOUNT = Decimal(os.getenv("ARB_START_AMOUNT", "100"))

# When the bot checks if a pool has money in it ("liquidity"), it uses this
# amount. If a pool can't handle a trade of this size, the bot will ignore it.
# This helps avoid "ghost" opportunities in pools with very little money.
LIQUIDITY_CHECK_AMOUNT = Decimal(os.getenv("ARB_LIQUIDITY_CHECK_AMOUNT", "100"))


# ==============================================================================
# SECTION 8: PERFORMANCE AND EXECUTION
# ==============================================================================
# These settings control how the bot runs, how fast it scans, and how it
# interacts with the API.
# ------------------------------------------------------------------------------

# THE MOST IMPORTANT SAFETY SWITCH.
# If `DRY_RUN` is `true`, the bot will only *simulate* trades and print what it
# *would* do. It will NEVER execute a real trade or spend any of your funds.
# Set this to `false` ONLY when you are confident the bot is working correctly
# and you are ready to perform live trades.
DRY_RUN = os.getenv("ARB_DRY_RUN", "true").lower() in ("1", "true", "yes")

# The maximum number of arbitrage cycles (e.g., A->B->C->A) the bot will
# simulate in a single scan. This prevents the bot from spending too much time
# on simulations if there are many possible paths.
MAX_CYCLES_PER_SCAN = 12

# How long (in seconds) the bot will wait for a response from the GalaSwap API
# before giving up and timing out.
HTTP_TIMEOUT = int(os.getenv("GALA_HTTP_TIMEOUT", "15"))

# How many seconds the bot will wait between each scan for arbitrage opportunities.
# A lower number means the bot scans more frequently, which is better for
# catching fast-moving opportunities, but uses more API requests.
SCAN_INTERVAL_SECONDS = int(os.getenv("ARB_SCAN_INTERVAL_SECONDS", "15"))

# To save API requests, the bot caches the list of active pools. This setting
# controls how many scans it performs before it re-checks all the pools to see
# which ones are active. For example, a value of 10 means it will refresh the
# list of active pools every 10 scans.
POOL_REFRESH_INTERVAL = int(os.getenv("ARB_POOL_REFRESH_INTERVAL", "10"))