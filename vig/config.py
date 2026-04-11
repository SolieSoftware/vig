import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API keys
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.environ.get("REDDIT_USER_AGENT", "vig/0.1")

# Betfair
BETFAIR_API_KEY = os.environ.get("BETFAIR_API_KEY", "")
BETFAIR_USERNAME = os.environ.get("BETFAIR_USERNAME", "")
BETFAIR_PASSWORD = os.environ.get("BETFAIR_PASSWORD", "")

# Odds API
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
ODDS_API_REGIONS = "eu"
ODDS_API_ODDS_FORMAT = "decimal"

# Cache
CACHE_DIR = Path(__file__).parent.parent / ".vig_cache"
CACHE_TTL_SECONDS = 7200  # 2 hours

# Staleness threshold for UI warning (same as cache TTL)
STALE_THRESHOLD_SECONDS = 7200

# Confidence thresholds (based on value_signal_pct)
CONFIDENCE_THRESHOLDS = {
    "HIGH": 0.05,    # gap > 5%
    "MEDIUM": 0.02,  # gap 2–5%
    # LOW = anything below MEDIUM
}
