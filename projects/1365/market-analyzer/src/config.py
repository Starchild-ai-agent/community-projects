import os
from pathlib import Path


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Load .env from market-analyzer directory
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

EXCHANGE = os.getenv("MA_EXCHANGE", "binance")

SYMBOLS = os.getenv("MA_SYMBOLS", "BTC/USDT,ETH/USDT,SOL/USDT").split(",")

TIMEFRAMES = os.getenv("MA_TIMEFRAMES", "1m,5m,15m,1h,4h").split(",")

# Higher timeframes summarized as bias context in Tier 2 prompts.
# Must be a subset of TIMEFRAMES to have data.
BIAS_TIMEFRAMES = os.getenv("MA_BIAS_TIMEFRAMES", "1h,4h").split(",")

BUFFER_SIZE = 200

SCREEN_THRESHOLD = float(os.getenv("MA_SCREEN_THRESHOLD", "0.6"))

# LLM settings
# MA_LLM_CALL_MODE:
# - auto: internal ai-agent route (if configured) -> sc-proxy -> direct OpenRouter key
# - internal: only internal ai-agent route
# - proxy: only sc-proxy to OpenRouter
# - direct: only direct OpenRouter key
LLM_CALL_MODE = os.getenv("MA_LLM_CALL_MODE", "proxy").strip().lower()
AI_AGENT_API_URL = os.getenv("AI_AGENT_API_URL", "").rstrip("/")
LLM_INTERNAL_PATH = os.getenv("MA_LLM_INTERNAL_PATH", "/api/clawd/llm/chat/completions")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODEL = os.getenv("MA_LLM_MODEL", "anthropic/claude-sonnet-4.6")
LLM_MAX_TOKENS = int(os.getenv("MA_LLM_MAX_TOKENS", "4096"))

# Brave Search
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")

# Derivatives data provider:
# - auto: try Coinglass first (when key exists), then exchange fallback
# - coinglass: only Coinglass
# - exchange: only exchange via ccxt
DERIV_PROVIDER = os.getenv("MA_DERIV_PROVIDER", "auto").strip().lower()
COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY", "")
COINGLASS_BASE_URL = os.getenv("COINGLASS_BASE_URL", "https://open-api-v4.coinglass.com")

# News enrichment
ENABLE_TWITTER_NEWS = _env_bool("MA_ENABLE_TWITTER_NEWS", False)
TWITTER_NEWS_POSTS = int(os.getenv("MA_TWITTER_NEWS_POSTS", "10"))

CHART_CANDLES = 60

CONTEXT_CANDLES = 20

VOLUME_SPIKE_MULT = 2.0

RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

ANALYSIS_COOLDOWN = int(os.getenv("MA_ANALYSIS_COOLDOWN", "60"))

# Minimum move (in %) for an outcome checkpoint to count as a win/loss.
# Covers fees/slippage/noise so a +0.01% drift isn't scored "CORRECT".
WIN_THRESHOLD_PCT = float(os.getenv("MA_WIN_THRESHOLD_PCT", "0.1"))

# Force-close virtual positions after this many hours.
MAX_HOLD_HOURS = float(os.getenv("MA_MAX_HOLD_HOURS", "24"))

DASHBOARD_HOST = os.getenv("MA_DASHBOARD_HOST", "127.0.0.1")

OUTPUT_MODE = os.getenv("MA_OUTPUT_MODE", "log")
