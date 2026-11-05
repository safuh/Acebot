
# ==========================================
# MARKET CONFIGURATION
# ==========================================

EXCHANGE_ID = "binance"

SYMBOL = "BTC/USDT"
TIMEFRAME = "1h"

# Number of historical candles to maintain.
N = 1800

# Poll exchange every 10 seconds.
POLL_INTERVAL = 30

# Maximum candles per CCXT request.
# Binance Spot supports up to 1000 OHLCV candles.
OHLCV_LIMIT = 1800


# ==========================================
# FEATURE CONFIGURATION
# ==========================================

RSI_PERIOD = 14

LIQUIDITY_LOOKBACK = 5


# ==========================================
# EXCHANGE CONFIGURATION
# ==========================================

EXCHANGE_OPTIONS = {
    "enableRateLimit": True,
    "timeout": 30000,
    "options": {
        "defaultType": "spot",
        "adjustForTimeDifference": True,
    }
}


# ==========================================
# DASH CONFIGURATION
# ==========================================

DASH_HOST = "127.0.0.1"
DASH_PORT = 8050
DASH_DEBUG = False


# ==========================================
# MARKET STRUCTURE CONFIGURATION
# ==========================================

SWING_LEFT_BARS = 2
SWING_RIGHT_BARS = 2
RSI_WINDOW_BARS = 2

# Reference days are calendar days before the current day.
# A one-day gap is excluded; eligible references are 2 through 21 days back.
MIN_DIVERGENCE_LOOKBACK_DAYS = 2
MAX_DIVERGENCE_LOOKBACK_DAYS = 21
