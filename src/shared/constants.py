"""
Constants - Shared constants used across the plugin
"""

# Plugin metadata
PLUGIN_NAME = "astrbot_plugin_qq_group_daily_analysis"
PLUGIN_VERSION = "2.0.0"

# Platform identifiers
PLATFORM_ONEBOT = "onebot"
PLATFORM_TELEGRAM = "telegram"
PLATFORM_DISCORD = "discord"
PLATFORM_SLACK = "slack"
PLATFORM_LARK = "lark"

SUPPORTED_PLATFORMS = [
    PLATFORM_ONEBOT,
    # Future platforms
    # PLATFORM_TELEGRAM,
    # PLATFORM_DISCORD,
    # PLATFORM_SLACK,
    # PLATFORM_LARK,
]

# Analysis defaults
DEFAULT_MAX_TOPICS = 5
DEFAULT_MAX_USER_TITLES = 10
DEFAULT_MAX_GOLDEN_QUOTES = 5
DEFAULT_MIN_MESSAGES = 50
DEFAULT_MAX_TOKENS = 2000

# Time periods
HOUR_RANGES = {
    "morning": (6, 12),
    "afternoon": (12, 18),
    "evening": (18, 24),
    "night": (0, 6),
}

# Report formats
REPORT_FORMAT_TEXT = "text"
REPORT_FORMAT_MARKDOWN = "markdown"
REPORT_FORMAT_IMAGE = "image"
REPORT_FORMAT_HTML = "html"

# Message content types
CONTENT_TYPE_TEXT = "text"
CONTENT_TYPE_IMAGE = "image"
CONTENT_TYPE_EMOJI = "emoji"
CONTENT_TYPE_STICKER = "sticker"
CONTENT_TYPE_FILE = "file"
CONTENT_TYPE_AUDIO = "audio"
CONTENT_TYPE_VIDEO = "video"
CONTENT_TYPE_REPLY = "reply"
CONTENT_TYPE_AT = "at"
CONTENT_TYPE_UNKNOWN = "unknown"

# Analysis task states
TASK_STATE_PENDING = "pending"
TASK_STATE_RUNNING = "running"
TASK_STATE_COMPLETED = "completed"
TASK_STATE_FAILED = "failed"
TASK_STATE_CANCELLED = "cancelled"

# Error codes
ERROR_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
ERROR_LLM_FAILED = "LLM_FAILED"
ERROR_PLATFORM_ERROR = "PLATFORM_ERROR"
ERROR_CONFIG_ERROR = "CONFIG_ERROR"
ERROR_TIMEOUT = "TIMEOUT"

# Cache TTL (in seconds)
CACHE_TTL_SHORT = 60  # 1 minute
CACHE_TTL_MEDIUM = 300  # 5 minutes
CACHE_TTL_LONG = 3600  # 1 hour
CACHE_TTL_DAY = 86400  # 24 hours

# Rate limiting defaults
RATE_LIMIT_LLM_CALLS = 10  # calls per minute
RATE_LIMIT_API_CALLS = 60  # calls per minute
RATE_LIMIT_BURST = 5  # burst size

# Retry defaults
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 1.0
RETRY_MAX_DELAY = 30.0

# File paths
HISTORY_DIR = "history"
CACHE_DIR = "cache"
TEMP_DIR = "temp"
